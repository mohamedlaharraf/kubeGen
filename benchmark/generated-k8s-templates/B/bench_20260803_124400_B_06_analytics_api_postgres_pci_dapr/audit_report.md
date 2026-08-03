# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie une API d'analytics appelée "analytics-api", image
myregistry/analytics:2.0, namespace "data", port 8080. Elle doit se
connecter à une base de données gérée par l'opérateur CrunchyData
PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone).
L'application doit aussi être conforme à la norme PCI-DSS niveau 1
(chiffrement au repos obligatoire pour tous les volumes, rotation des
clés tous les 90 jours). Utilise aussi Dapr comme sidecar pour la
communication pub/sub avec les autres services de l'entreprise.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `analytics-api` (Deployment), 1 sidecar(s): ['dapr']

## 3. Auto-vérification Agent 1

- Auto-check réussi : **True**
- Tentatives de réparation internes : 2
- ⚠️ Exigences jamais couvertes : ['Rotation des clés tous les 90 jours', "Connexion à une base de données PostgresCluster (3 instances, réplication synchrone) via l'opérateur CrunchyData"]
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].replicas` : Nombre de réplicas non spécifié pour analytics-api. → hypothèse retenue : *Définition de 1 réplica par défaut.* (confiance medium)
  - `components[0].sidecars[0].image` : Quelle version d'image exacte pour le sidecar Dapr ? → hypothèse retenue : *Utilisation de l'image standard daprio/daprd:1.12.0.* (confiance medium)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[analytics-api]']
- ⚠️ Champs laissés ouverts : ['Rotation des clés tous les 90 jours', "Connexion à une base de données PostgresCluster (3 instances, réplication synchrone) via l'opérateur CrunchyData", 'unmapped_requirements: Procédure/Politique de rotation des clés de chiffrement tous les 90 jours pour conformité PCI-DSS niveau 1 (suggested_kind=None)', "unmapped_requirements: Base de données PostgresCluster (3 instances, réplication synchrone) gérée par l'opérateur CrunchyData PostgreSQL (suggested_kind=PostgresCluster)"]
- Actions :
  - Extraction initiale + 2 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ['Nombre de réplicas non spécifié pour analytics-api.', "Quelle version d'image exacte pour le sidecar Dapr ?"]

### Agent 2 - Template
- Champs traités : ['namespace', "[analytics-api] component_name: 'analytics-api' (utilisé dans metadata.name et selectors)", "[analytics-api] workload_type: 'Deployment' (génération d'un Deployment apps/v1)", "[analytics-api] image: 'myregistry/analytics:2.0'", '[analytics-api] replicas: 1', "[analytics-api] labels: {'app': 'analytics-api'}", "[analytics-api] namespace: 'data'", "[analytics-api] ports: [{'name': 'http', 'container_port': 8080, 'expose_service': true}] -> Service ClusterIP et containerPort exposés", '[analytics-api] env_vars: aucun demandé, section omise', '[analytics-api] volumes: aucun demandé, aucun PVC/volume généré', "[analytics-api] sidecars: 'dapr' détecté comme système d'injection automatique -> converti en annotations dapr.io sur la spec du Pod", '[analytics-api] depends_on: liste vide, pas de dépendance explicite', "[analytics-api] rbac: rbac.enabled=false -> ServiceAccount 'analytics-api-sa' créé sans Role/RoleBinding", "[analytics-api] observability_style: 'annotations' -> aucune exigence explicite dans observability_requirements", '[analytics-api] cron_schedule: non applicable pour Deployment', '[analytics-api] config_maps: aucun demandé', '[analytics-api] network_policy: non spécifié', '[analytics-api] deployment_strategy: non spécifié (stratégie par défaut K8s utilisée)', "[analytics-api] security_requirements: Application d'un securityContext durci par défaut sur le Pod et le conteneur: runAsNonRoot=true, allowPrivilegeEscalation=false, readOnlyRootFilesystem=true, capabilities.drop=['ALL'], seccompProfile.type=RuntimeDefault", "[analytics-api] rbac: ServiceAccount dédié 'analytics-api-sa' créé et assigné au Pod via serviceAccountName.", "[analytics-api] rbac: rbac.enabled est False: aucun Role ni RoleBinding n'a été créé, respectant le principe de moindre privilège."]
- ⚠️ Champs laissés ouverts : ["[analytics-api] resources.requests/limits et HPA: non générés (délégués à l'Agent 4)", "[analytics-api] 'Conformité à la norme PCI-DSS niveau 1': nécessite des contrôles d'infrastructure/processus externes, politiques d'audit (OPA/Gatekeeper), chiffrement réseau et gouvernance hors portée d'un simple manifeste Deployment K8s.", "[analytics-api] 'Chiffrement au repos obligatoire pour tous les volumes': aucun volume/PVC n'est rattaché à ce composant, et le chiffrement au repos est géré au niveau de la StorageClass ou du cloud provider.", "[analytics-api] 'Rotation des clés de chiffrement tous les 90 jours': nécessite un gestionnaire de secrets externe (ex: HashiCorp Vault, AWS KMS, cert-manager) non configurable directement dans ce manifeste.", 'unmapped_requirements: 2 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'data' généré (une seule fois, déterministe)
  - [analytics-api] 1 sidecar(s) empaqueté(s) dans le même Pod : ["Communication pub/sub avec les autres services de l'entreprise"]
  - Génération BEST-EFFORT (non vérifiée, un appel LLM par exigence) pour 2 exigence(s) hors du schéma structuré : ['Procédure/Politique de rotation des clés de chiffrement tous les 90 jours pour conformité PCI-DSS niveau 1', "Base de données PostgresCluster (3 instances, réplication synchrone) gérée par l'opérateur CrunchyData PostgreSQL"]
- Avertissements : ["[analytics-api] Le sidecar Dapr 'dapr' (image: daprio/daprd:1.12.0) a été traité via les annotations d'injection automatique Dapr (dapr.io/enabled, dapr.io/app-id, dapr.io/app-port) sur le Pod au lieu d'un conteneur manuel dans containers[]. Cela nécessite l'installation préalable de l'opérateur Dapr dans le cluster.", "[analytics-api] readOnlyRootFilesystem a été activé dans le securityContext par mesure de sécurité. Si l'application écrit dans des répertoires temporaires (ex: /tmp), des volumes emptyDir devront être ajoutés."]

### Agent 3 - Validation
- Champs traités : ['namespace', 'architecture_type', 'components[0].component_name', 'components[0].workload_type', 'components[0].image', 'components[0].replicas', 'components[0].labels', 'components[0].ports', 'components[0].env_vars', 'components[0].volumes', 'components[0].sidecars', 'components[0].ingress', 'components[0].rbac', 'components[0].observability_style', 'components[0].cron_schedule']
- Actions :
  - Présence et validité des champs apiVersion, kind, metadata.name et spec
  - Présence du Namespace 'data'
  - Présence du ServiceAccount dédié 'analytics-api-sa' malgré rbac.enabled=false
  - Alignement des selectors du Service 'analytics-api' avec les labels du Deployment
  - Le ServiceAccount est correctement référencé dans spec.template.spec.serviceAccountName
  - Sidecar Dapr géré correctement via les annotations d'injection automatique (dapr.io/enabled, dapr.io/app-id, dapr.io/app-port) sans ajout d'un conteneur manuel inutile/doublon
  - Conformité de l'image 'myregistry/analytics:2.0' et du port 8080 avec la NormalizedSpec

### Agent 4 - Énergie
- Champs traités : ['[analytics-api] component_name', '[analytics-api] workload_type', '[analytics-api] replicas', '[analytics-api] energy_goals', '[analytics-api] resource_hints', '[analytics-api] traffic_windows', '[analytics-api] constraints']
- Actions :
  - [analytics-api] Ajout de resources.requests (cpu: 100m, memory: 128Mi) et resources.limits (cpu: 500m, memory: 256Mi) pour éviter la surallocation énergétique et prémunir des fuites.
  - [analytics-api] Ajout de livenessProbe et readinessProbe en tcpSocket sur le port 8080 pour éviter les pods zombies consommateurs d'énergie sans supposer de route HTTP.
  - [analytics-api] Création d'un HorizontalPodAutoscaler réactif basé sur l'utilisation CPU (cible 75%, min: 1, max: 5) adapté en l'absence de fenêtres de trafic horaires.
  - [analytics-api] Ajout d'un PodDisruptionBudget (minAvailable: 1) pour maintenir la disponibilité lors du drainage de nœuds.
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['PostgresCluster/postgres-cluster']."]

### Agent 5 - Vérification finale
- Champs traités : ['yaml_syntax_validation', 'cross_references_validation', 'multi_document_coherency', 'namespace_consistency', 'traceability_audit']
- ⚠️ Champs laissés ouverts : ['Rotation des clés de chiffrement tous les 90 jours : requiert un gestionnaire KMS / Vault externe, infaisable via des manifestes Kubernetes déclaratifs natifs.', "Chiffrement au repos pour tous les volumes : doit être garanti au niveau de l'infrastructure / StorageClass / Cloud Provider, aucun PVC/volume explicite n'étant rattaché au Pod analytics-api.", 'PostgresCluster/postgres-cluster : fragment CRD généré en mode best-effort (Agent 2) hors du schéma structuré core/v1, nécessitant que le CustomResourceDefinition CrunchyData PostgreSQL Operator soit préalablement installé sur le cluster récepteur.', "2 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Procédure/Politique de rotation des clés de chiffrement tous les 90 jours pour conformité PCI-DSS niveau 1'; 'Base de données PostgresCluster (3 instances, réplication synchrone) gérée par l'opérateur CrunchyData PostgreSQL' (kind supposé: PostgresCluster)"]
- Actions :
  - yaml.safe_load_all OK sur les 7 documents
  - Validation des types Kubernetes (quantités CPU/Mémoire, numéros de ports integer) OK
  - Validation des références croisées (HPA scaleTargetRef -> Deployment analytics-api, Service selector -> Deployment template labels, ServiceAccount -> Deployment spec.serviceAccountName) OK
  - Vérification d'isolation inter-composants OK (aucun chevauchement de labels ou selectors accidentel)
  - Corrigé: Ajout explicite du namespace 'data' sur le document PostgresCluster/postgres-cluster pour uniformité globale avec les autres ressources
  - Contrôle déterministe Python : OK
- Avertissements : ["Le CustomResource PostgresCluster généré en best-effort par l'Agent 2 est inclus dans le manifeste final mais n'a pas pu faire l'objet de validation OpenAPI formelle (CRD externe).", "L'utilisation des annotations dapr.io nécessite que l'opérateur Dapr soit déployé dans le cluster pour injecter le sidecar à la création des pods."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | data | manifest (Namespace name=data + metadata.namespace sur toutes les ressources) |
| components[0].component_name | analytics-api | manifest (Deployment nom=analytics-api, Service nom=analytics-api, SA nom=analytics-api-sa, HPA nom=analytics-api, PDB nom=analytics-api) |
| components[0].image | myregistry/analytics:2.0 | manifest (Deployment container[0].image) |
| components[0].ports[0] | 8080 TCP (expose_service=True) | manifest (Service port 8080 -> targetPort 8080, Deployment containerPort 8080) |
| components[0].sidecars[0] | dapr (daprio/daprd:1.12.0) | manifest (Deployment pod annotations dapr.io/enabled, dapr.io/app-id, dapr.io/app-port) |
| components[0].security_requirements | Conformité PCI-DSS, chiffrement au repos, rotation des clés | manifest (Pod/Container securityContext: runAsNonRoot=true, readOnlyRootFilesystem=true, drop ALL, seccompProfile) / partiellement non résolu (voir unresolved_items) |
| energy_goals / optimisations Agent 4 | Resources requests/limits, probes, HPA, PDB | manifest (Deployment resources cpu 100m/500m mem 128Mi/256Mi, liveness/readiness probes tcpSocket:8080, HPA target CPU 75% min 1 max 5, PDB minAvailable 1) |
| unmapped_requirements[1] | Base de données PostgresCluster CrunchyData | manifest (PostgresCluster nom=postgres-cluster généré en best-effort) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- Procédure/Politique de rotation des clés de chiffrement tous les 90 jours pour conformité PCI-DSS niveau 1 (kind inconnu)
- Base de données PostgresCluster (3 instances, réplication synchrone) gérée par l'opérateur CrunchyData PostgreSQL (kind supposé : `PostgresCluster`)

## 7. ⚠️ À vérifier / relancer si besoin

- 2 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Procédure/Politique de rotation des clés de chiffrement tous les 90 jours pour conformité PCI-DSS niveau 1'; 'Base de données PostgresCluster (3 instances, réplication synchrone) gérée par l'opérateur CrunchyData PostgreSQL' (kind supposé: PostgresCluster)
- Chiffrement au repos pour tous les volumes : doit être garanti au niveau de l'infrastructure / StorageClass / Cloud Provider, aucun PVC/volume explicite n'étant rattaché au Pod analytics-api.
- Connexion à une base de données PostgresCluster (3 instances, réplication synchrone) via l'opérateur CrunchyData
- PostgresCluster/postgres-cluster : fragment CRD généré en mode best-effort (Agent 2) hors du schéma structuré core/v1, nécessitant que le CustomResourceDefinition CrunchyData PostgreSQL Operator soit préalablement installé sur le cluster récepteur.
- Rotation des clés de chiffrement tous les 90 jours : requiert un gestionnaire KMS / Vault externe, infaisable via des manifestes Kubernetes déclaratifs natifs.
- Rotation des clés tous les 90 jours
- [analytics-api] 'Chiffrement au repos obligatoire pour tous les volumes': aucun volume/PVC n'est rattaché à ce composant, et le chiffrement au repos est géré au niveau de la StorageClass ou du cloud provider.
- [analytics-api] 'Conformité à la norme PCI-DSS niveau 1': nécessite des contrôles d'infrastructure/processus externes, politiques d'audit (OPA/Gatekeeper), chiffrement réseau et gouvernance hors portée d'un simple manifeste Deployment K8s.
- [analytics-api] 'Rotation des clés de chiffrement tous les 90 jours': nécessite un gestionnaire de secrets externe (ex: HashiCorp Vault, AWS KMS, cert-manager) non configurable directement dans ce manifeste.
- [analytics-api] resources.requests/limits et HPA: non générés (délégués à l'Agent 4)
- unmapped_requirements: 2 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 2 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: Base de données PostgresCluster (3 instances, réplication synchrone) gérée par l'opérateur CrunchyData PostgreSQL (suggested_kind=PostgresCluster)
- unmapped_requirements: Procédure/Politique de rotation des clés de chiffrement tous les 90 jours pour conformité PCI-DSS niveau 1 (suggested_kind=None)

## Métriques d'exécution

- Latence totale du run : **348.529 s** (dont pipeline seul : 348.529 s)
- Appels LLM : **21** (8 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 338.641 s (moyenne 16.126 s/appel)
- Tokens consommés : **50630** (40148 prompt + 10482 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 4 (3 échoué(s)) | 52.668 | 5655 |
| Agent 1 - Analyse (self-check) | 4 (1 échoué(s)) | 71.442 | 4439 |
| Agent 1 - Analyse (réparation) | 2 | 30.987 | 5276 |
| Agent 1 - Analyse (réparation schéma) | 1 | 45.118 | 2648 |
| Agent 2 - Template | 4 (3 échoué(s)) | 25.93 | 6988 |
| Agent 2 - Template (best-effort) | 3 (1 échoué(s)) | 52.544 | 12359 |
| Agent 3 - Validation | 1 | 15.467 | 3012 |
| Agent 4 - Énergie | 1 | 12.865 | 3377 |
| Agent 5 - Vérification finale | 1 | 31.62 | 6876 |