# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie une API de recherche "search-api" (image myregistry/search:1.0),
namespace "search", 2 réplicas, port 8080 en HTTP, exposée uniquement en
interne.

Elle a besoin d'un cluster Elasticsearch géré par l'opérateur ECK (Elastic
Cloud on Kubernetes) avec 3 nœuds de données et de l'authentification
gérée via HashiCorp Vault pour injecter les credentials automatiquement
dans les pods (Vault Agent Injector).

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `search-api` (Deployment), dépend de: ['elasticsearch']
- ⚠️ Dépendances vers des noms non résolus (composant absent ou ressource externe) : ["'search-api' dépend de 'elasticsearch', qui ne correspond à aucun composant généré par ce pipeline — soit une faute de frappe dans le nom, soit une ressource externe gérée hors du schéma structuré (base de données, service tiers...) à vérifier manuellement."]

## 3. Auto-vérification Agent 1

- Auto-check réussi : **True**
- Tentatives de réparation internes : 2
- ⚠️ Exigences jamais couvertes : ['Injection automatique de secrets via annotations Vault Agent Injector', "Cluster Elasticsearch de 3 nœuds géré par l'opérateur ECK"]
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].workload_type` : Quel type de workload Kubernetes utiliser pour search-api ? → hypothèse retenue : *Un Deployment a été retenu pour l'API applicative sans état.* (confiance high)
  - `components[1].workload_type` : Quel type de workload utiliser pour le cluster Elasticsearch ECK ? → hypothèse retenue : *Une CustomResource de l'opérateur ECK (Kind Elasticsearch) a été retenue.* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[search-api]']
- ⚠️ Champs laissés ouverts : ['Injection automatique de secrets via annotations Vault Agent Injector', "Cluster Elasticsearch de 3 nœuds géré par l'opérateur ECK", 'unmapped_requirements: Injection automatique de secrets via annotations Vault Agent Injector (suggested_kind=VaultAgentInjector)', "unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (suggested_kind=Elasticsearch)"]
- Actions :
  - Extraction initiale + 1 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ['Quel type de workload Kubernetes utiliser pour search-api ?', 'Quel type de workload utiliser pour le cluster Elasticsearch ECK ?']

### Agent 2 - Template
- Champs traités : ['namespace', '[search-api] component_name: search-api utilisé comme metadata.name', '[search-api] workload_type: Deployment généré', '[search-api] image: myregistry/search:1.0 configuré dans la spec du conteneur', '[search-api] replicas: 2 appliqué dans spec.replicas', '[search-api] labels: app=search-api appliqué sur le Deployment, Service, SA et pods', '[search-api] ports: port 8080/TCP exposé dans le conteneur et dans le Service ClusterIP', "[search-api] env_vars: aucune variable d'environnement demandée", '[search-api] volumes: aucun volume persistant demandé', '[search-api] sidecars: aucun sidecar demandé', '[search-api] depends_on: dépendance vers elasticsearch documentée', '[search-api] namespace: search appliqué sur toutes les ressources', '[search-api] cron_schedule: non applicable (Deployment)', '[search-api] config_maps: aucune ConfigMap demandée', '[search-api] deployment_strategy: stratégie par défaut Deployment utilisée', '[search-api] security_requirements: Exposition uniquement en interne: Service de type ClusterIP et NetworkPolicy limitant le trafic Ingress au namespace', '[search-api] security_requirements: Hardening de sécurité par défaut: runAsNonRoot: true, allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities.drop ALL, seccompProfile RuntimeDefault', "[search-api] security_requirements: HashiCorp Vault Agent Injector: ajout des annotations 'vault.hashicorp.com/agent-inject' et 'vault.hashicorp.com/role' sur les pods", '[search-api] observability_requirements: observability_requirements: aucune exigence explicite fournie dans la spec', "[search-api] ingress: ingress: aucun Ingress créé suite à l'exigence d'exposition strictement interne", "[search-api] rbac: rbac: ServiceAccount 'search-api-sa' créé et configuré sans Role/RoleBinding car rbac.enabled est false (moindre privilège)"]
- ⚠️ Champs laissés ouverts : ["[search-api] depends_on: la séquence d'initialisation/attente d'elasticsearch n'est pas gérée au niveau du template purement k8s (nécessite un initContainer d'attente si strict)", "[search-api] La configuration exacte des rôles et des chemins de secrets Vault (vault.hashicorp.com/agent-inject-secret-*) doit être affinée selon les secrets précis requis par l'application.", 'unmapped_requirements: 2 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'search' généré (une seule fois, déterministe)
  - Génération BEST-EFFORT (non vérifiée, un appel LLM par exigence) pour 2 exigence(s) hors du schéma structuré : ['Injection automatique de secrets via annotations Vault Agent Injector', "Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données"]
- Avertissements : ["[search-api] L'annotation Vault 'vault.hashicorp.com/role: search-api' suppose l'existence d'un rôle Vault nommé 'search-api' dans le cluster. À ajuster si le rôle Vault configuré a un autre nom.", "[search-api] L'utilisation de readOnlyRootFilesystem: true impose que l'application n'écrive pas sur le système de fichiers local sans volume temporaire (emptyDir)."]

### Agent 3 - Validation
- Champs traités : ['namespace', 'architecture_type', 'components.search-api.workload_type', 'components.search-api.image', 'components.search-api.replicas', 'components.search-api.labels', 'components.search-api.ports', 'components.search-api.env_vars', 'components.search-api.volumes', 'components.search-api.sidecars', 'components.search-api.ingress', 'components.search-api.rbac', 'components.search-api.observability_style', 'components.search-api.cron_schedule']
- Actions :
  - apiVersion et kind présents et valides pour toutes les ressources (Namespace, ServiceAccount, Deployment, Service, NetworkPolicy)
  - Nom d'espace de noms 'search' cohérent sur l'ensemble des ressources
  - Deployment 'search-api' et Service 'search-api' ont leurs labels et selectors parfaitement alignés (app: search-api)
  - Nombre de répliques conforme (2)
  - Image conteneur et ports conformes (myregistry/search:1.0, containerPort: 8080)
  - ServiceAccount 'search-api-sa' conservé et référencé dans le Deployment
  - Annotations Vault Agent Injector bien positionnées sans duplication de conteneur manuel
  - Corrigé: Suppression du bloc JSON résiduel et invalide concaténé à la fin du manifeste YAML par l'étape précédente

### Agent 4 - Énergie
- Champs traités : ['[search-api] component_name', '[search-api] workload_type', '[search-api] replicas', '[search-api] energy_goals', '[search-api] resource_hints', '[search-api] traffic_windows', '[search-api] constraints']
- Actions :
  - [search-api] Ajout des ressources requests (cpu: 100m, memory: 128Mi) et limits (cpu: 500m, memory: 256Mi) dimensionnées prudemment en l'absence de resource_hints.
  - [search-api] Ajout de sondes livenessProbe et readinessProbe basées sur tcpSocket (port 8080) pour éviter de conserver des pods inactifs sans faire d'hypothèse sur un chemin HTTP.
  - [search-api] Ajout d'un HorizontalPodAutoscaler (HPA) réactif ciblant 75% d'utilisation CPU avec minReplicas=2 et maxReplicas=5.
  - [search-api] Ajout d'un PodDisruptionBudget (PDB) garantissant minAvailable=1 lors des opérations de maintenance.
- Avertissements : ["[search-api] Aucun resource_hint ni objectif d'énergie spécifique fourni : utilisation de valeurs de requêtes/limites CPU et mémoire par défaut. À affiner selon l'usage réel.", "Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['/']."]

### Agent 5 - Vérification finale
- Champs traités : ['namespace', 'architecture_type', 'components.search-api.workload_type', 'components.search-api.image', 'components.search-api.replicas', 'components.search-api.labels', 'components.search-api.ports', 'components.search-api.security_requirements', 'components.search-api.resources', 'components.search-api.probes', 'components.search-api.hpa', 'components.search-api.pdb', 'unmapped_requirements']
- ⚠️ Champs laissés ouverts : ["unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK généré en best-effort (Kind: Elasticsearch, apiVersion: elasticsearch.k8s.elastic.co/v1), non validé par le schéma standard Kubernetes.", "components[0].depends_on: La dépendance envers elasticsearch n'inclut pas d'initContainer ou de mécanisme d'attente réseau actif avant le démarrage du pod.", "Vault Agent Injector: L'annotation vault.hashicorp.com/agent-inject-secret-* n'a pas été renseignée car aucun nom de secret précis n'a été spécifié.", "2 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Injection automatique de secrets via annotations Vault Agent Injector' (kind supposé: VaultAgentInjector); 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données' (kind supposé: Elasticsearch)"]
- Actions :
  - yaml.safe_load_all OK sur 8 documents YAML
  - Validation des types et quantités k8s OK (100m, 500m, 128Mi, 256Mi)
  - Vérification des références croisées : Service.spec.selector (app=search-api) correspond exactement au Deployment.spec.template.metadata.labels
  - Vérification HPA : scaleTargetRef pointe explicitement sur Deployment/search-api
  - Vérification NetworkPolicy : podSelector pointe sur app=search-api
  - Vérification PodDisruptionBudget : selector pointe sur app=search-api
  - Vérification ServiceAccount : Deployment references search-api-sa
  - Corrigé: Formatage et réintégration propre du document CRD Elasticsearch (elasticsearch.k8s.elastic.co/v1) en document YAML standard valide
  - Corrigé: Alignement du namespace 'search' sur le document Elasticsearch généré par l'Agent 2
  - Contrôle déterministe Python : OK
- Avertissements : ["La ressource Elasticsearch (elasticsearch.k8s.elastic.co/v1) repose sur une CRD générée en best-effort et nécessite la présence préalable de l'opérateur Elastic Cloud on Kubernetes (ECK) dans le cluster.", "L'annotation 'vault.hashicorp.com/role: search-api' nécessite qu'un rôle d'authentification Kubernetes nommé 'search-api' soit préalablement configuré sur le serveur HashiCorp Vault."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | search | manifest (Namespace/search et metadata.namespace sur tous les objets) |
| components[0].component_name | search-api | manifest (Deployment search-api, Service search-api, SA search-api-sa, HPA search-api-hpa, PDB search-api-pdb, NetworkPolicy search-api-netpol) |
| components[0].image | myregistry/search:1.0 | manifest (Deployment search-api spec.template.spec.containers[0].image) |
| components[0].replicas | 2 | manifest (Deployment search-api spec.replicas=2, HPA minReplicas=2) |
| components[0].ports | 8080/TCP (ClusterIP) | manifest (Deployment containerPort 8080, Service port 8080 targetPort 8080 type ClusterIP) |
| components[0].security_requirements[0] | Exposition uniquement en interne | manifest (Service ClusterIP, NetworkPolicy search-api-netpol) |
| components[0].security_requirements[1] | Vault Agent Injector | manifest (Deployment annotations vault.hashicorp.com/agent-inject: 'true' et vault.hashicorp.com/role: search-api) |
| unmapped_requirements[0] | Injection automatique de secrets via annotations Vault Agent Injector | manifest (Deployment annotations Vault Agent Injector) |
| unmapped_requirements[1] | Cluster Elasticsearch géré par l'opérateur ECK avec 3 nœuds | manifest (Elasticsearch elasticsearch.k8s.elastic.co/v1 count=3) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- Injection automatique de secrets via annotations Vault Agent Injector (kind supposé : `VaultAgentInjector`)
- Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (kind supposé : `Elasticsearch`)

## 7. ⚠️ À vérifier / relancer si besoin

- 2 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Injection automatique de secrets via annotations Vault Agent Injector' (kind supposé: VaultAgentInjector); 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données' (kind supposé: Elasticsearch)
- Cluster Elasticsearch de 3 nœuds géré par l'opérateur ECK
- Injection automatique de secrets via annotations Vault Agent Injector
- Vault Agent Injector: L'annotation vault.hashicorp.com/agent-inject-secret-* n'a pas été renseignée car aucun nom de secret précis n'a été spécifié.
- [search-api] La configuration exacte des rôles et des chemins de secrets Vault (vault.hashicorp.com/agent-inject-secret-*) doit être affinée selon les secrets précis requis par l'application.
- [search-api] depends_on: la séquence d'initialisation/attente d'elasticsearch n'est pas gérée au niveau du template purement k8s (nécessite un initContainer d'attente si strict)
- components[0].depends_on: La dépendance envers elasticsearch n'inclut pas d'initContainer ou de mécanisme d'attente réseau actif avant le démarrage du pod.
- unmapped_requirements: 2 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 2 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (suggested_kind=Elasticsearch)
- unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK généré en best-effort (Kind: Elasticsearch, apiVersion: elasticsearch.k8s.elastic.co/v1), non validé par le schéma standard Kubernetes.
- unmapped_requirements: Injection automatique de secrets via annotations Vault Agent Injector (suggested_kind=VaultAgentInjector)

## Métriques d'exécution

- Latence totale du run : **286.875 s** (dont pipeline seul : 286.875 s)
- Appels LLM : **11** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 284.398 s (moyenne 25.854 s/appel)
- Tokens consommés : **45552** (36347 prompt + 9205 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 15.996 | 5380 |
| Agent 1 - Analyse (self-check) | 2 | 29.285 | 2509 |
| Agent 1 - Analyse (réparation) | 1 | 15.585 | 2089 |
| Agent 1 - Analyse (réparation schéma) | 1 | 49.485 | 2546 |
| Agent 2 - Template | 1 | 19.785 | 6948 |
| Agent 2 - Template (best-effort) | 2 | 70.814 | 12451 |
| Agent 3 - Validation | 1 | 46.974 | 3102 |
| Agent 4 - Énergie | 1 | 13.1 | 3505 |
| Agent 5 - Vérification finale | 1 | 23.375 | 7022 |