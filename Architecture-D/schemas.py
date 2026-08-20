"""
schemas.py
==========

C'est le coeur de la solution au problème que vous décrivez :

    "seul l'agent 1 voit la commande de l'utilisateur, donc s'il rate
    quelque chose on n'aura pas exactement ce qui est demandé"

Le pipeline est une chaîne STRICTE (pas de retour en arrière), mais rien
n'empêche l'Agent 1 de produire un CONTRAT STRUCTURÉ et COMPLET
(`NormalizedSpec`) qui sert de "cahier des charges" figé et transmis
tel quel à tous les agents suivants, en plus de leur propre travail.

Trois mécanismes rendent ce contrat fiable :

1. Un schéma Pydantic strict (ci-dessous) qui force l'Agent 1 à remplir
   des champs précis plutôt que de résumer librement.
2. Une boucle d'auto-vérification INTERNE à l'Agent 1 (voir
   agents/agent1_analyse.py) : il relit la demande brute et compare
   champ par champ, AVANT de transmettre la main à l'Agent 2. C'est un
   aller-retour interne au noeud 1, pas un retour en arrière dans le
   graphe (l'architecture "sans retour en arrière" reste respectée).
3. Une matrice de traçabilité tenue à jour par CHAQUE agent suivant :
   quand un agent traite un champ de la spec, il le déclare "couvert"
   dans son propre rapport. L'Agent 5 (vérification finale) agrège tous
   les rapports et signale au a en clair, dans audit_report.md, tout
   champ demandé par l'utilisateur qui ne serait couvert nulle part.
   Le pipeline ne "boucle" pas automatiquement dessus (architecture
   stricte oblige) mais l'utilisateur voit immédiatement, noir sur
   blanc, si quelque chose a été perdu et peut relancer une exécution
   corrigée.
"""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


def _coerce_literal(value, allowed: tuple, default: str):
    """
    Coercion TOLÉRANTE pour les champs enum "administratifs" (ceux qui ont
    un défaut sûr et un faible impact si mal interprétés). Un LLM produit
    parfois une valeur proche mais pas exactement conforme (casse
    différente, `null` explicite, synonyme) — plutôt que de faire planter
    toute la validation Pydantic (et donc tout le run) pour ça, on retombe
    sur le défaut documenté.

    Volontairement PAS utilisé sur les champs à fort impact fonctionnel
    (ex: `workload_type`) : un défaut silencieux y serait plus dangereux
    qu'une erreur visible — ceux-là passent par le mécanisme de réparation/
    retrait explicite de `agents/agent1_analyse.py` à la place, qui laisse
    une trace dans les warnings plutôt que de deviner silencieusement.
    """
    if isinstance(value, str):
        for candidate in allowed:
            if value.strip().lower() == candidate.lower():
                return candidate
    return default


# ---------------------------------------------------------------------------
# Briques élémentaires
# ---------------------------------------------------------------------------

class PortSpec(BaseModel):
    name: str = Field(default="http")
    container_port: int
    protocol: Literal["TCP", "UDP"] = "TCP"
    expose_service: bool = True

    @field_validator("protocol", mode="before")
    @classmethod
    def _normalize_protocol(cls, v):
        return _coerce_literal(v, ("TCP", "UDP"), "TCP")


class EnvVar(BaseModel):
    name: str
    value: Optional[str] = None
    from_secret: Optional[str] = None
    from_configmap: Optional[str] = None
    secret_key: Optional[str] = Field(
        default=None,
        description="Clé exacte à lire DANS le Secret désigné par "
                    "`from_secret`, si l'utilisateur l'a précisée (ex: "
                    "'lire DB_PASSWORD depuis la clé db_pass du secret X'). "
                    "Laisser vide si non précisé : l'Agent 2 devra alors "
                    "faire une hypothèse et DOIT la documenter dans ses "
                    "avertissements — ne jamais deviner silencieusement.",
    )
    configmap_key: Optional[str] = Field(
        default=None,
        description="Équivalent de `secret_key` mais pour `from_configmap`.",
    )


class VolumeSpec(BaseModel):
    name: str
    mount_path: str
    kind: Literal["emptyDir", "configMap", "secret", "pvc"] = "emptyDir"
    source_name: Optional[str] = None
    size: Optional[str] = Field(
        default=None,
        description="Taille demandée si `kind='pvc'` (ex: '10Gi'). Si "
                    "l'utilisateur ne précise pas de taille, l'Agent 2 devra "
                    "en supposer une par défaut et le documenter dans "
                    "`warnings` — jamais silencieusement.",
    )
    storage_class_name: Optional[str] = Field(
        default=None,
        description="StorageClass explicitement demandée par l'utilisateur "
                    "pour un `kind='pvc'` (ex: 'fast-ssd'). Laisser vide pour "
                    "utiliser la StorageClass par défaut du cluster.",
    )


class TrafficWindow(BaseModel):
    """
    Une fenêtre horaire de trafic explicitement mentionnée par l'utilisateur
    (ex: "trafic très faible entre minuit et 6h"). Capturée à part de
    `energy_goals`/`resource_hints` (texte libre) car c'est une donnée
    exploitable directement par l'Agent 4 pour générer un scaler CRON
    (KEDA `ScaledObject`, trigger `cron`) plutôt qu'un simple HPA réactif
    au CPU — un HPA classique ne garantit PAS qu'on descend à N replicas
    à une heure précise, seulement en fonction de la charge observée.
    """
    start_time: str = Field(description="Heure de début au format HH:MM (24h)")
    end_time: str = Field(description="Heure de fin au format HH:MM (24h)")
    level: Literal["low", "high", "normal"]
    timezone: Optional[str] = Field(
        default=None,
        description="Fuseau horaire si mentionné (ex: 'Europe/Paris'). "
                    "Laisser vide si non précisé par l'utilisateur.",
    )
    target_replicas_hint: Optional[int] = Field(
        default=None,
        description="Nombre de réplicas souhaité pendant cette fenêtre, "
                    "si l'utilisateur l'a précisé (sinon laisser vide, "
                    "l'Agent 4 décidera dans les bornes min/max).",
    )


class Ambiguity(BaseModel):
    """Un point que l'Agent 1 n'a pas pu déterminer avec certitude."""
    field: str
    question: str
    assumption_made: str
    confidence: Literal["low", "medium", "high"] = "low"


class CoverageCheck(BaseModel):
    """
    Résultat de l'auto-vérification interne de l'Agent 1 : pour chaque
    "intention" détectée dans le texte utilisateur, a-t-elle été mappée
    dans la spec structurée ?
    """
    requirements_detected: list[str] = Field(default_factory=list)
    requirements_mapped: list[str] = Field(default_factory=list)
    requirements_unmapped: list[str] = Field(default_factory=list)
    repair_attempts: int = 0
    self_check_passed: bool = False


# ---------------------------------------------------------------------------
# Sidecar : conteneur additionnel dans le MÊME Pod qu'un composant
# ---------------------------------------------------------------------------

class SidecarContainer(BaseModel):
    """
    Pattern Sidecar Kubernetes : un conteneur additionnel packagé dans le
    MÊME Pod que le conteneur applicatif principal (partage réseau/volumes,
    même cycle de vie). Ex: proxy de service mesh, collecteur de logs,
    exportateur de métriques dédié.

    Ne remplit ce champ QUE si l'utilisateur demande explicitement un
    sidecar (ou un besoin qui s'implémente idiomatiquement ainsi, ex:
    "proxy Envoy à côté de l'appli"). Ne jamais l'inventer par défaut.
    """
    name: str
    image: str = Field(
        description="Image du sidecar. Si l'utilisateur ne précise pas "
                    "d'image exacte pour un besoin connu (ex: 'un sidecar "
                    "de logs'), propose une image standard reconnue du "
                    "domaine (ex: 'fluent/fluent-bit:latest' pour du "
                    "logging, 'envoyproxy/envoy:v1.29-latest' pour un "
                    "proxy) et documente ce choix comme une hypothèse "
                    "dans `ambiguities`.",
    )
    purpose: str = Field(
        description="Rôle du sidecar en une phrase (ex: 'proxy de service "
                    "mesh', 'collecteur de logs vers stdout partagé', "
                    "'exportateur de métriques dédié')."
    )
    ports: list["PortSpec"] = Field(default_factory=list)
    env_vars: list["EnvVar"] = Field(default_factory=list)
    resource_hints: Optional[str] = None


# ---------------------------------------------------------------------------
# Ingress : exposition HTTP(S) externe
# ---------------------------------------------------------------------------

class IngressSpec(BaseModel):
    """
    Exposition externe HTTP(S) d'un composant. Ne remplir que si
    l'utilisateur demande explicitement un accès depuis l'extérieur du
    cluster (nom de domaine, "accessible depuis internet", "expose-la en
    HTTPS"...) — une simple mention de port HTTP interne ne suffit pas.
    """
    enabled: bool = False
    host: Optional[str] = Field(
        default=None,
        description="Nom de domaine (ex: 'checkout.exemple.com'). Si "
                    "l'utilisateur veut une exposition externe sans préciser "
                    "de domaine, laisser vide et documenter dans `ambiguities` "
                    "que l'Agent 2 devra utiliser un placeholder à remplacer.",
    )
    path: str = "/"
    tls: bool = False
    tls_secret_name: Optional[str] = Field(
        default=None,
        description="Nom du Secret TLS si précisé. Sinon, l'Agent 2 en "
                    "suppose un par convention et le documente.",
    )
    ingress_class: Optional[str] = Field(
        default=None,
        description="IngressClass demandée (ex: 'nginx'). Laisser vide pour "
                    "utiliser la classe par défaut du cluster.",
    )
    api_style: Literal["ingress", "gateway_api"] = Field(
        default="ingress",
        description="'gateway_api' UNIQUEMENT si l'utilisateur mentionne "
                    "explicitement 'Gateway API', 'HTTPRoute', ou un "
                    "équivalent. Sinon reste 'ingress' (classique, comportement "
                    "par défaut inchangé).",
    )
    gateway_name: Optional[str] = Field(
        default=None,
        description="Nom d'une ressource `Gateway` EXISTANTE à laquelle "
                    "rattacher le `HTTPRoute` (pattern Gateway API standard : "
                    "la Gateway est généralement gérée par la plateforme/"
                    "l'équipe infra, l'équipe applicative ne crée que des "
                    "HTTPRoute). Si vide alors que `api_style='gateway_api'`, "
                    "l'Agent 2 génère un squelette de Gateway avec un "
                    "placeholder à documenter — voir prompt Agent 2.",
    )
    cert_manager_issuer: Optional[str] = Field(
        default=None,
        description="Nom d'un `Issuer`/`ClusterIssuer` cert-manager "
                    "EXISTANT, UNIQUEMENT si l'utilisateur mentionne "
                    "explicitement cert-manager ou une émission automatique "
                    "de certificat TLS. Si `tls=true` mais que ce champ est "
                    "vide, le Secret TLS reste simplement référencé (jamais "
                    "créé) comme avant — comportement par défaut inchangé.",
    )
    cert_manager_issuer_kind: Literal["Issuer", "ClusterIssuer"] = "ClusterIssuer"

    @field_validator("api_style", mode="before")
    @classmethod
    def _normalize_api_style(cls, v):
        return _coerce_literal(v, ("ingress", "gateway_api"), "ingress")

    @field_validator("cert_manager_issuer_kind", mode="before")
    @classmethod
    def _normalize_cert_manager_issuer_kind(cls, v):
        return _coerce_literal(v, ("Issuer", "ClusterIssuer"), "ClusterIssuer")


# ---------------------------------------------------------------------------
# RBAC : permissions d'accès à l'API Kubernetes
# ---------------------------------------------------------------------------

class RBACSpec(BaseModel):
    """
    Besoins d'accès à l'API Kubernetes du composant (ex: "l'app doit
    pouvoir lister les pods du namespace"). Un `ServiceAccount` dédié est
    TOUJOURS créé par défaut pour chaque composant (bonne pratique de
    moindre privilège — ne jamais utiliser le ServiceAccount `default`),
    que `rbac.enabled` soit vrai ou non. `rules_description` ne sert qu'à
    documenter des permissions API additionnelles explicitement demandées.
    """
    enabled: bool = False
    rules_description: list[str] = Field(
        default_factory=list,
        description="Permissions demandées en langage naturel (ex: 'lire "
                    "les ConfigMaps du namespace', 'lister les pods'). "
                    "L'Agent 2 les traduit du mieux possible en règles RBAC "
                    "et documente toute traduction incertaine.",
    )


# ---------------------------------------------------------------------------
# ConfigMap dédiée (données de configuration versionnées, pas juste des
# variables d'env inline)
# ---------------------------------------------------------------------------

class ConfigMapSpec(BaseModel):
    """
    Une ConfigMap à créer avec de vraies données, quand l'utilisateur donne
    un contenu de configuration explicite (fichier de conf, paramètres
    multiples...) plutôt qu'une simple variable d'environnement isolée.

    IMPORTANT — ce champ est réservé aux données NON SENSIBLES. Ne JAMAIS
    y placer un mot de passe, une clé API ou tout secret : pour ça,
    `EnvVar.from_secret` reste la seule voie (référence à un Secret
    supposé déjà présent dans le cluster, jamais de valeur en clair
    générée par le pipeline — c'est un choix de sécurité volontaire, pas
    un oubli).
    """
    name: str
    data: dict[str, str] = Field(
        default_factory=dict,
        description="Paires clé/valeur de configuration non sensible "
                    "explicitement fournies par l'utilisateur.",
    )


# ---------------------------------------------------------------------------
# NetworkPolicy fine (au-delà du simple "interne uniquement")
# ---------------------------------------------------------------------------

class NetworkPolicySpec(BaseModel):
    """
    Règles réseau plus fines que le hardening par défaut de l'Agent 2 (qui
    se contente d'un `Service.type: ClusterIP` + restriction d'ingress au
    namespace quand `security_requirements` mentionne "interne uniquement").
    Ne remplir que si l'utilisateur exprime un besoin de contrôle réseau
    précis (egress restreint, ports/composants spécifiques autorisés...).
    """
    restrict_egress: bool = Field(
        default=False,
        description="Si vrai, l'egress du composant est limité aux cibles "
                    "listées dans `allowed_egress_targets` (+ DNS, "
                    "nécessaire au fonctionnement du cluster). Si aucune "
                    "cible explicite n'est donnée, `depends_on` sert de "
                    "liste par défaut raisonnable.",
    )
    allowed_egress_targets: list[str] = Field(
        default_factory=list,
        description="Noms de composants (`component_name`) ou CIDR/domaines "
                    "externes explicitement autorisés en sortie.",
    )
    allowed_ingress_sources: list[str] = Field(
        default_factory=list,
        description="Noms de composants explicitement autorisés à "
                    "atteindre celui-ci. Vide = tout le namespace autorisé "
                    "(comportement par défaut de l'Agent 2).",
    )


# ---------------------------------------------------------------------------
# Stratégie de déploiement avancée (Argo Rollouts)
# ---------------------------------------------------------------------------

class DeploymentStrategySpec(BaseModel):
    """
    Stratégie de déploiement progressif (canary/blue-green), UNIQUEMENT si
    explicitement demandée. Implique de remplacer le `Deployment` standard
    par une ressource `Rollout` (CRD Argo Rollouts) — dépendance externe
    au même titre que KEDA/Istio, toujours documentée en warning.
    """
    strategy: Literal["canary", "blue_green"] = "canary"
    steps_description: list[str] = Field(
        default_factory=list,
        description="Étapes en langage naturel si précisées (ex: '10% de "
                    "trafic vers la nouvelle version pendant 5 minutes, "
                    "puis 100%'). Si vide, l'Agent 2 propose une "
                    "progression par défaut raisonnable et le documente.",
    )

    @field_validator("strategy", mode="before")
    @classmethod
    def _normalize_strategy(cls, v):
        return _coerce_literal(v, ("canary", "blue_green"), "canary")


# ---------------------------------------------------------------------------
# Exigence non mappable : le filet de sécurité générique
# ---------------------------------------------------------------------------

class UnmappedRequirement(BaseModel):
    """
    Une exigence exprimée par l'utilisateur qui ne correspond à AUCUN champ
    existant du schéma, même approximativement. Existe pour empêcher le
    piège inverse de tous les champs dédiés ajoutés jusqu'ici (sécurité,
    observabilité, Gateway API...) : sans cette soupape, l'Agent 1 est
    structurellement poussé à forcer une exigence inconnue dans le champ
    existant le plus proche (ex: Gateway API compris comme "Ingress avec
    une classe appelée gateway-api"), ce qui produit un audit qui affiche
    "Aucun point ouvert détecté ✅" alors que la demande a été mal comprise.
    C'est plus dangereux qu'un champ simplement vide : une fausse
    correspondance a l'air correcte.

    Le nom de ce champ ne change JAMAIS d'un cas à l'autre — seul son
    contenu texte varie. C'est ce qui le rend générique : il n'y a rien à
    étendre dans le schéma pour accueillir un prochain cas imprévu (un
    opérateur de base de données, un CRD maison...).
    """
    text: str = Field(
        description="L'exigence telle qu'exprimée par l'utilisateur, mot "
                    "pour mot ou reformulée fidèlement — jamais résumée au "
                    "point de perdre l'information utile à sa génération."
    )
    suggested_kind: Optional[str] = Field(
        default=None,
        description="Hypothèse du LLM sur le `kind` Kubernetes concerné "
                    "(ex: 'PostgresCluster'). Jamais généré automatiquement "
                    "— juste une indication pour la génération best-effort "
                    "et pour la lisibilité de l'audit.",
    )


# ---------------------------------------------------------------------------
# GlobalConstraint : le mécanisme central de l'Architecture C (blackboard).
#
# Contexte : dans le pipeline strict (Architecture B), une exigence comme
# "chiffrement au repos pour TOUS les volumes" finit rattachée aux
# security_requirements d'UN SEUL composant (celui que le LLM avait sous
# les yeux au moment de l'extraction), invisible pour tout agent qui
# travaille ensuite sur un autre composant. Vérifié empiriquement sur le
# scénario PCI-DSS/PostgresCluster : le manifeste de la base de données
# n'a hérité d'aucune configuration de chiffrement.
#
# GlobalConstraint casse cette dépendance à un composant unique : c'est
# une extraction SÉPARÉE, avec un `scope` explicite, stockée au niveau de
# la NormalizedSpec (pas dans un ServiceComponent) et donc lisible par
# TOUT agent qui filtre par scope/nom de composant — y compris les agents
# qui génèrent des ressources en dehors du schéma structuré.
# ---------------------------------------------------------------------------

class GlobalConstraint(BaseModel):
    """
    Une contrainte qui ne peut pas être rattachée à un seul composant sans
    perdre son sens — parce qu'elle s'applique à plusieurs composants, à
    toutes les ressources d'un certain type, ou à l'application entière.

    Ne PAS utiliser pour une exigence qui ne concerne qu'un seul composant
    nommé (ça reste un champ normal de ServiceComponent, ex:
    security_requirements). GlobalConstraint est réservé à ce qui doit
    survivre au-delà de la frontière d'un composant.
    """
    text: str = Field(
        description="La contrainte telle qu'exprimée par l'utilisateur, "
                    "fidèle au texte original — jamais résumée au point de "
                    "perdre le détail actionnable (ex: garder 'au repos', "
                    "'90 jours', pas juste 'sécurité renforcée')."
    )
    scope: Literal["all_components", "all_volumes", "all_containers", "specific"] = Field(
        description="'all_components' : s'applique à toute ressource "
                    "générée, quelle que soit sa nature. 'all_volumes' : "
                    "toute ressource qui déclare un volume/PVC/volumeMount. "
                    "'all_containers' : tout conteneur dans n'importe quel "
                    "pod template. 'specific' : seulement les composants "
                    "listés dans `applies_to` (utiliser ce cas avec "
                    "parcimonie — s'il n'y a qu'UN composant concerné et "
                    "qu'il existe dans `components`, cette exigence "
                    "appartient probablement à son security_requirements "
                    "normal, pas ici)."
    )
    applies_to: list[str] = Field(
        default_factory=list,
        description="Noms de composants concernés. Rempli UNIQUEMENT si "
                    "scope='specific' ET que ça concerne plusieurs "
                    "composants nommés (2+) — sinon laisser vide.",
    )
    category: Literal["security", "compliance", "network", "labeling", "other"] = Field(
        description="Catégorie large, pour le filtrage et l'audit — pas "
                    "pour la génération elle-même.",
    )


# ---------------------------------------------------------------------------
# RepairRequest : sortie structurée d'Agent 5 quand un gap est détecté.
#
# Avant : Agent 5 produisait des `unresolved_items` en texte libre,
# lisibles par un humain mais inexploitables par du code — le pipeline ne
# pouvait rien faire d'autre que les afficher ("le pipeline étant strict,
# pas de retour en arrière, ton travail est de les rendre VISIBLES", dixit
# le prompt original d'Agent 5). RepairRequest rend ce signal actionnable
# par l'orchestrateur : à QUELLE ressource ça s'applique, QUEL agent est
# compétent pour la corriger, et QUOI exactement corriger.
#
# Tout ce qui n'est pas structurellement réparable par un agent (ex: "la
# conformité PCI-DSS niveau 1 est un processus organisationnel, pas un
# artefact K8s") reste en `unresolved_items` texte libre — RepairRequest
# n'est émis QUE pour les gaps qu'un agent peut concrètement corriger.
# ---------------------------------------------------------------------------

class RepairRequest(BaseModel):
    target_resource: str = Field(
        description="Identifiant lisible de la ressource à corriger, ex: "
                    "'PostgresCluster/postgres-cluster' ou "
                    "'Deployment/analytics-api'.",
    )
    target_agent: Literal["agent2_template", "agent4_debate"] = Field(
        description="Quel agent est compétent pour ce type de correction : "
                    "agent2_template pour un champ structurel/sécurité "
                    "manquant sur un manifeste, agent4_debate pour un "
                    "problème de dimensionnement/scaling (issu du "
                    "sous-système de débat multi-agents énergie).",
    )
    missing_constraint: str = Field(
        description="Ce qui manque concrètement, assez précis pour qu'un "
                    "agent puisse agir dessus directement sans re-déduire "
                    "le problème (ex: 'chiffrement au repos absent sur les "
                    "volumes dataVolumeClaimSpec et repo1'), pas une "
                    "reformulation vague du symptôme.",
    )
    reason: str = Field(
        description="Pourquoi c'est un gap : quelle exigence de la demande "
                    "originale ou quelle GlobalConstraint n'est pas "
                    "respectée.",
    )
    attempt: int = Field(
        default=1,
        description="Numéro de tentative de réparation pour CETTE requête "
                    "précise — permet à l'orchestrateur d'abandonner "
                    "proprement après MAX_REPAIR_ATTEMPTS plutôt que de "
                    "boucler indéfiniment sur un gap non réparable.",
    )


# ---------------------------------------------------------------------------
# ServiceComponent : un composant déployable (un microservice, ou l'unique
# workload d'une architecture simple à un seul service)
# ---------------------------------------------------------------------------

class ServiceComponent(BaseModel):
    """
    Un composant individuel à déployer. Une architecture "simple" (un seul
    service) a exactement UN ServiceComponent dans `NormalizedSpec.components`.
    Une architecture "microservices" en a PLUSIEURS, chacun avec sa propre
    identité, ses propres ports/env/volumes, ses propres sidecars, et
    éventuellement des dépendances vers d'autres composants (`depends_on`,
    à but documentaire/traçabilité — le pipeline ne crée aucune
    orchestration de démarrage, juste des ressources K8s indépendantes).
    """

    component_name: str
    workload_type: Literal[
        "Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"
    ] = "Deployment"
    image: str
    replicas: int = 1
    labels: dict[str, str] = Field(default_factory=dict)

    # Réseau / config / stockage du conteneur PRINCIPAL de ce composant
    ports: list[PortSpec] = Field(default_factory=list)
    env_vars: list[EnvVar] = Field(default_factory=list)
    volumes: list[VolumeSpec] = Field(default_factory=list)

    # Pattern Sidecar : conteneurs additionnels dans le même Pod
    sidecars: list[SidecarContainer] = Field(default_factory=list)

    # Pattern Microservices : à quels autres composants celui-ci parle-t-il
    # (par `component_name`). Documentaire/traçabilité uniquement — n'affecte
    # pas l'ordre de génération (le pipeline reste une chaîne stricte).
    depends_on: list[str] = Field(default_factory=list)

    # Énergie (par composant : chaque microservice peut avoir un profil de
    # charge différent, ex: l'API scale sur horaires, le worker sur la queue)
    energy_goals: list[str] = Field(default_factory=list)
    resource_hints: Optional[str] = None
    traffic_windows: list[TrafficWindow] = Field(default_factory=list)

    # Contraintes / sécurité / observabilité, par composant
    constraints: list[str] = Field(default_factory=list)
    security_requirements: list[str] = Field(default_factory=list)
    observability_requirements: list[str] = Field(default_factory=list)

    # Exposition externe HTTP(S) (Ingress). None/enabled=False par défaut :
    # sans demande explicite, un composant reste interne (ClusterIP).
    ingress: Optional[IngressSpec] = None

    # Permissions API Kubernetes. Même si `enabled=False`, un ServiceAccount
    # dédié est toujours créé par défaut (bonne pratique) — voir RBACSpec.
    rbac: RBACSpec = Field(default_factory=RBACSpec)

    # Routage de service mesh explicitement demandé (ex: "canary 90/10 vers
    # v2", "timeout 5s", "circuit breaker"). Vide par défaut : le pattern
    # Sidecar (proxy ajouté au Pod) n'implique PAS automatiquement une
    # configuration de routage — ce sont deux demandes différentes.
    service_mesh_routing: list[str] = Field(default_factory=list)

    # Style d'exposition des métriques Prometheus. "annotations" (défaut) ne
    # nécessite aucun opérateur particulier ; "service_monitor" nécessite le
    # Prometheus Operator installé (même logique de dépendance que KEDA).
    observability_style: Literal["annotations", "service_monitor", "both"] = "annotations"

    # Expression cron de déclenchement, UNIQUEMENT pertinente si
    # `workload_type == "CronJob"`. Différent du scaling KEDA (qui, lui,
    # ajuste le nombre de réplicas d'un Deployment/StatefulSet existant) :
    # ici c'est le déclenchement même du Job qui est planifié.
    cron_schedule: Optional[str] = Field(
        default=None,
        description="Expression cron 5 champs (ex: '0 3 * * *' pour 3h du "
                    "matin chaque jour). Si l'utilisateur décrit un horaire "
                    "en langage naturel, convertis-le en respectant "
                    "strictement le format 'minute heure jour mois "
                    "jour_semaine' (voir règle de conversion dans le prompt "
                    "de l'Agent 1 — piège fréquent : ne jamais laisser le "
                    "champ heure en '*' pour un horaire quotidien fixe).",
    )

    # ConfigMap(s) dédiée(s), pour de la config non sensible explicite
    config_maps: list[ConfigMapSpec] = Field(default_factory=list)

    # Règles réseau fines (egress notamment). None = hardening par défaut
    # de l'Agent 2 suffit (voir NetworkPolicySpec).
    network_policy: Optional[NetworkPolicySpec] = None

    # Déploiement progressif (canary/blue-green via Argo Rollouts).
    # None = Deployment/StatefulSet standard (comportement par défaut).
    deployment_strategy: Optional[DeploymentStrategySpec] = None

    @field_validator("observability_style", mode="before")
    @classmethod
    def _normalize_observability_style(cls, v):
        return _coerce_literal(v, ("annotations", "service_monitor", "both"), "annotations")


# ---------------------------------------------------------------------------
# Le contrat central : NormalizedSpec
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ValidationError : sortie structurée d'Agent 3 (Validation), consommée par
# la boucle de correction Generator <-> Validator (nouveau mécanisme,
# distinct de la boucle de réparation post-Agent 5 / RepairRequest).
#
# Contrairement à RepairRequest (générique, ciblé sur UNE ressource, réservé
# aux contraintes globales du blackboard), ValidationError modélise
# spécifiquement des problèmes de SCHÉMA ou de SÉCURITÉ détectés sur le
# manifeste dans son ensemble à un instant donné -- l'équivalent structuré
# d'une sortie de linter (ligne, règle, message), pas une contrainte
# métier transversale.
# ---------------------------------------------------------------------------

class ValidationError(BaseModel):
    line: Optional[int] = Field(
        default=None,
        description="Ligne approximative dans `current_yaml` où l'erreur "
                    "a été localisée (calculée en repérant le bloc "
                    "'kind: X' / 'name: Y' du document concerné). None si "
                    "l'erreur ne concerne pas un document précis (ex: "
                    "cohérence inter-documents).",
    )
    rule: str = Field(
        description="Identifiant court et stable de la règle violée, "
                    "style kube-linter (ex: 'missing-security-context', "
                    "'privileged-container', 'invalid-resource-quantity', "
                    "'dangling-configmap-ref'). Toujours en kebab-case, "
                    "jamais une phrase.",
    )
    message: str = Field(
        description="Description humaine du problème, assez précise pour "
                    "qu'un agent puisse agir dessus sans re-déduire le "
                    "contexte.",
    )
    resource: Optional[str] = Field(
        default=None,
        description="Identifiant lisible de la ressource concernée, ex: "
                    "'Deployment/checkout-api'. None si l'erreur est "
                    "globale (ex: aucun document valide du tout).",
    )


class NormalizedSpec(BaseModel):
    """
    Sortie de l'Agent 1. C'est LE document de référence, transmis
    INCHANGÉ (lecture seule) à travers tout le pipeline. Les agents 2 à 5
    ne reçoivent JAMAIS le texte brut de l'utilisateur : ils reçoivent
    cette spec, ce qui force l'Agent 1 à être exhaustif et documente
    précisément ce qui a été compris.

    `components` contient toujours AU MOINS un élément : une demande
    "simple" (un seul service) produit un `components` à une seule entrée,
    une demande "microservices" en produit plusieurs. Les agents suivants
    itèrent sur `components` de façon générique — ils ne distinguent pas
    "simple" et "microservices" comme deux chemins de code séparés.
    """

    architecture_type: Literal["single", "microservices"] = Field(
        default="single",
        description="'microservices' UNIQUEMENT si l'utilisateur décrit "
                    "explicitement plusieurs services distincts en "
                    "interaction. Une seule appli avec un sidecar reste "
                    "'single' (le sidecar n'est pas un service séparé).",
    )
    namespace: str = "default"
    components: list[ServiceComponent] = Field(default_factory=list)

    # Politiques d'admission organisationnelles (OPA/Gatekeeper ou Kyverno),
    # au niveau de la demande entière (pas par composant — ce sont
    # généralement des règles transverses). Génération volontairement
    # CONSERVATRICE côté Agent 2 : seuls des patterns simples et bien
    # connus sont traduits en squelette de policy ; le reste est documenté
    # comme non résolu plutôt que d'halluciner une règle de sécurité.
    admission_policies: list[str] = Field(default_factory=list)

    # Multi-cluster/multi-région : déclenche la génération déterministe d'un
    # squelette ArgoCD ApplicationSet (voir utils/multi_cluster.py). Ce
    # pipeline reste conçu pour produire le CONTENU d'un déploiement type —
    # il ne connaît pas les adresses API réelles des clusters cibles.
    target_clusters: list[str] = Field(default_factory=list)

    # Filet de sécurité générique : toute exigence qui ne correspond à AUCUN
    # champ existant du schéma, même approximativement. Voir
    # `UnmappedRequirement` pour le raisonnement complet. Ce champ garde
    # TOUJOURS le même nom d'un cas à l'autre — c'est le contenu texte à
    # l'intérieur qui varie, jamais la structure du schéma.
    unmapped_requirements: list[UnmappedRequirement] = Field(default_factory=list)

    @field_validator("unmapped_requirements", mode="before")
    @classmethod
    def _coerce_unmapped_requirements(cls, v):
        """
        Coercion TOLÉRANTE, même logique que `_coerce_literal` : le LLM
        comprend très bien QUAND une exigence appartient à
        `unmapped_requirements` (il le fait à raison), mais échoue
        régulièrement sur la FORME exacte attendue — il envoie une simple
        chaîne, ou un dict qui regroupe plusieurs exigences dans un
        champ sans le nommer `text`, au lieu d'un objet
        `{"text": ..., "suggested_kind": ...}`. Observé en pratique : deux
        échecs consécutifs de la passe de réparation de schéma sur ce
        champ précis épuisent `AGENT1_MAX_REPAIR_ATTEMPTS` et font échouer
        tout le run, alors que l'information elle-même était correcte et
        au bon endroit. On normalise ici la forme plutôt que de compter
        sur la conformité du LLM sur un point aussi mineur.
        """
        if not isinstance(v, list):
            return v
        normalized = []
        for item in v:
            if isinstance(item, str):
                normalized.append({"text": item})
            elif isinstance(item, dict) and "text" not in item:
                # Objet mal formé sans le champ `text` : on reconstitue un
                # texte à partir de ce qui est disponible plutôt que de
                # perdre l'exigence sur une erreur de validation évitable.
                fallback_text = item.get("description") or item.get("value") or str(item)
                normalized.append({**item, "text": fallback_text})
            else:
                normalized.append(item)
        return normalized

    # Le mécanisme central de l'Architecture C : contraintes qui traversent
    # la frontière d'un composant unique (voir GlobalConstraint plus haut).
    # Stocké au niveau de la spec entière, PAS dans un ServiceComponent —
    # c'est précisément ce qui le rend lisible par tous les agents en aval,
    # y compris ceux qui génèrent des ressources hors schéma structuré.
    global_constraints: list[GlobalConstraint] = Field(default_factory=list)

    @field_validator("global_constraints", mode="before")
    @classmethod
    def _coerce_global_constraints(cls, v):
        """Même logique tolérante que `_coerce_unmapped_requirements` :
        le LLM comprend le concept mais peut envoyer une chaîne brute au
        lieu d'un objet structuré. On normalise plutôt que d'épuiser les
        tentatives de réparation de schéma sur un problème de forme."""
        if not isinstance(v, list):
            return v
        normalized = []
        for item in v:
            if isinstance(item, str):
                normalized.append({"text": item, "scope": "specific", "category": "other"})
            elif isinstance(item, dict):
                item = dict(item)
                item.setdefault("scope", "specific")
                item.setdefault("category", "other")
                normalized.append(item)
            else:
                normalized.append(item)
        return normalized

    # Contexte compact pour l'Agent 4 (Énergie) -- PAS le texte brut, un
    # résumé délibérément court (1-3 phrases) de la nature/criticité/profil
    # de trafic de la demande ENTIÈRE, pour que l'agent énergie puisse
    # juger si une infrastructure de scaling (HPA/KEDA) a du sens, plutôt
    # que de l'ajouter par réflexe "bonne pratique" même sur un site
    # statique à trafic quasi nul. Distinct de `raw_user_request` (jamais
    # transmis aux agents 2-4) : ceci EST transmis à l'Agent 4, précisément
    # parce que c'est un résumé curé, pas le texte intégral.
    application_context: str = Field(
        default="",
        description="1 à 3 phrases résumant le profil global de la "
                    "demande pour aider les décisions d'optimisation "
                    "énergie (criticité, volumétrie de trafic attendue, "
                    "contraintes de disponibilité). Ex: 'Site web "
                    "statique à trafic minimal, pas de contrainte de "
                    "disponibilité critique.' ou 'API de paiement "
                    "critique avec pics de charge prévisibles matin/soir, "
                    "disponibilité continue requise.'",
    )

    # Traçabilité / audit (niveau de la demande entière, pas par composant)
    raw_user_request: str = Field(
        description="Copie verbatim de la demande initiale, conservée "
                    "uniquement à des fins d'audit final (Agent 5). Les "
                    "agents 2-4 ne doivent PAS s'en servir pour générer du "
                    "contenu : ils doivent utiliser les champs structurés "
                    "ci-dessus."
    )
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    coverage: CoverageCheck = Field(default_factory=CoverageCheck)

    @field_validator("architecture_type", mode="before")
    @classmethod
    def _normalize_architecture_type(cls, v):
        return _coerce_literal(v, ("single", "microservices"), "single")


# ---------------------------------------------------------------------------
# Rapports produits par chaque agent (pour la traçabilité inter-étapes)
# ---------------------------------------------------------------------------

class AgentReport(BaseModel):
    agent_name: str
    fields_addressed: list[str] = Field(default_factory=list)
    fields_left_open: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# État global du graphe LangGraph
# ---------------------------------------------------------------------------

class StrategyProposal(BaseModel):
    """
    Proposition d'optimisation énergétique produite par UN agent-stratégie
    (Architecture D), pour UN composant, à un tour donné du débat.

    Chaque stratégie ne voit — comme l'ancien Agent 4 d'Architecture C —
    QUE le YAML validé du composant et ses propres champs énergie
    (`energy_goals`, `resource_hints`, `traffic_windows`, `constraints`,
    `workload_type`, `replicas`) + les contraintes globales applicables.
    La différence avec C n'est PAS l'accès à l'information (identique),
    mais l'ANGLE D'ATTAQUE imposé par la persona (voir prompts/strategy_*).
    """

    strategy: Literal["consolidation", "sizing", "autoscaling"]
    component_name: str
    manifest_yaml: str = Field(
        description="YAML du composant enrichi selon l'angle propre à cette stratégie."
    )
    rationale: str = Field(
        description="Justification de cette proposition, du point de vue de CETTE stratégie."
    )
    estimated_energy_savings_pct: Optional[float] = Field(
        default=None,
        description="Estimation (déclarative, non mesurée) du gain énergétique, en %.",
    )
    performance_risk: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Risque perçu par la stratégie elle-même sur la performance/SLA.",
    )
    actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StrategyCritique(BaseModel):
    """Une critique émise par une stratégie à l'encontre d'une autre, sur un
    point précis de désaccord (jamais un simple satisfecit vide)."""

    from_strategy: Literal["consolidation", "sizing", "autoscaling"]
    target_strategy: Literal["consolidation", "sizing", "autoscaling"]
    component_name: str
    comment: str = Field(
        description="Point de désaccord ou de risque identifié dans la proposition ciblée."
    )
    agrees: bool = Field(
        description="False si la critique pointe un risque/conflit réel, True si "
        "la stratégie ciblée n'a rien à redire de significatif à ce tour."
    )


class DebateRound(BaseModel):
    """Un tour complet du débat pour un composant : les propositions
    (éventuellement révisées) en vigueur à ce tour, et les critiques
    échangées à l'issue de ce tour."""

    round_number: int
    proposals: list[StrategyProposal] = Field(default_factory=list)
    critiques: list[StrategyCritique] = Field(default_factory=list)


class JudgeVerdict(BaseModel):
    """
    Verdict de l'Agent Juge (Architecture D) pour un composant : fusionne
    les trois propositions (post-débat) en UNE configuration finale,
    en tranchant explicitement chaque conflit plutôt qu'en moyennant
    silencieusement des choix contradictoires.
    """

    component_name: str
    manifest_yaml: str = Field(description="YAML final fusionné pour ce composant.")
    reasoning: str = Field(
        description="Raisonnement du Juge : ce qui a été retenu de chaque stratégie, et pourquoi."
    )
    strategy_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Score (0-10) attribué à chaque stratégie sur ce composant, "
        "combinant efficacité énergétique attendue et risque SLA/performance.",
    )
    chosen_elements: dict[str, str] = Field(
        default_factory=dict,
        description="Provenance de chaque élément retenu dans le YAML final, ex: "
        "{'resources': 'sizing', 'hpa': 'autoscaling', 'affinity': 'consolidation'}.",
    )
    fields_addressed: list[str] = Field(default_factory=list)
    fields_left_open: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PipelineState(BaseModel):
    """
    État partagé transmis de noeud en noeud dans le StateGraph.

    Important pour le "contexte isolé par étape" demandé dans
    l'architecture : chaque agent ne DOIT lire, dans son prompt LLM, que
    les champs qui le concernent (voir agents/*). Le State complet existe
    pour la traçabilité et pour permettre à l'Agent 5 de tout auditer à
    la fin, mais chaque agent construit son propre prompt en piochant
    uniquement ce dont il a besoin - jamais tout le state en vrac.
    """

    # Entrée
    user_request: str

    # Métriques historiques réelles fournies par l'utilisateur (--metrics-source),
    # clé = component_name. Si présentes pour un composant, l'Agent 4 les
    # utilise pour un dimensionnement déterministe plutôt qu'heuristique
    # LLM (voir utils/cost_estimate.py).
    historical_metrics: dict[str, dict] = Field(default_factory=dict)

    # Sortie Agent 1
    spec: Optional[NormalizedSpec] = None

    # Mode d'injection de chaque sidecar, décidé UNE SEULE FOIS de façon
    # déterministe (voir utils/sidecar_injection.py) au moment où l'Agent 2
    # génère le composant, puis relu tel quel par l'Agent 3 (validation) et
    # l'Agent 5 (vérification finale) au lieu d'être re-déduit par chacun
    # via son propre prompt LLM (c'est cette re-déduction indépendante qui
    # causait le doublon annotations+conteneur observé en production).
    # component_name -> sidecar_name -> {"mode": "annotations"|"manual_container", ...}
    sidecar_injection_mode: dict[str, dict[str, dict]] = Field(default_factory=dict)

    # Sorties successives (manifeste YAML, version après version)
    manifest_v1_yaml: Optional[str] = None   # Agent 2 : template de base
    manifest_v2_yaml: Optional[str] = None   # Agent 3 : validé/corrigé
    manifest_v3_yaml: Optional[str] = None   # Agent 4 : + énergie (HPA, resources)
    manifest_final_yaml: Optional[str] = None  # Agent 5 : vérifié syntaxiquement

    # Rapports (un par agent), pour la matrice de traçabilité finale
    reports: list[AgentReport] = Field(default_factory=list)

    # Matrice de traçabilité produite par l'Agent 5 (champ spec -> résolu où)
    traceability_matrix: list[dict] = Field(default_factory=list)

    # Erreurs bloquantes éventuelles (le pipeline reste strict : si un
    # agent lève une erreur bloquante, on s'arrête proprement plutôt que
    # de continuer avec un état invalide)
    error: Optional[str] = None

    # --- Architecture C : boucle de réparation bornée ---
    # Rempli par Agent 5 quand il détecte des gaps concrètement réparables
    # (voir RepairRequest). Vidé après chaque passage par le noeud "repair"
    # ; repeuplé par la revérification suivante d'Agent 5 si le gap
    # persiste. Liste vide = rien à réparer = fin normale du pipeline.
    repair_requests: list[RepairRequest] = Field(default_factory=list)

    # Compteur global de tentatives de réparation déjà effectuées (pas par
    # requête individuelle - le graphe s'arrête dès que CE compteur atteint
    # MAX_REPAIR_ATTEMPTS, même s'il reste des repair_requests non
    # résolues, pour garantir une borne stricte sur le coût/la latence
    # ajoutés par ce mécanisme).
    repair_attempt: int = 0

    # --- Boucle Generator <-> Validator (blackboard, distincte de la
    # boucle de réparation post-Agent 5 ci-dessus) ---
    # `current_yaml` : état courant du manifeste DANS cette boucle
    # (initialisé à la sortie d'Agent 2, mis à jour à chaque itération de
    # correction). Une fois la boucle terminée (propre ou borne atteinte),
    # sa valeur est copiée vers `manifest_v2_yaml` pour que la suite du
    # pipeline (Agent 4, Agent 5, sauvegarde des fichiers) n'ait rien à
    # changer.
    current_yaml: str = ""
    validation_errors: list[ValidationError] = Field(default_factory=list)
    iteration_count: int = 0

    # --- Architecture D : sous-système de débat multi-agents (remplace
    # l'Agent 4 unique d'Architecture C pour l'étape d'optimisation
    # énergétique). Clé = component_name.
    # Transcript complet (tous les tours, toutes les critiques) conservé
    # pour l'audit — jamais relu par le Juge d'un AUTRE composant (chaque
    # composant a son propre débat totalement indépendant, exécuté dans
    # son propre fan-out parallèle).
    debate_transcripts: dict[str, list[DebateRound]] = Field(default_factory=dict)
    judge_verdicts: list[JudgeVerdict] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}
