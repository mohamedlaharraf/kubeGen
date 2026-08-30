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

    model_config = {"arbitrary_types_allowed": True}
