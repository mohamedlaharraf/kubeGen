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
  - `search-api` (Deployment), 1 sidecar(s): ['vault-agent'], dépend de: ['elasticsearch']
- ⚠️ Dépendances vers des noms non résolus (composant absent ou ressource externe) : ["'search-api' dépend de 'elasticsearch', qui ne correspond à aucun composant généré par ce pipeline — soit une faute de frappe dans le nom, soit une ressource externe gérée hors du schéma structuré (base de données, service tiers...) à vérifier manuellement."]

## 3. Auto-vérification Agent 1

- Auto-check réussi : **True**
- Tentatives de réparation internes : 2
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].workload_type` : Le type de workload n'est pas précisé pour l'API. → hypothèse retenue : *Deployment* (confiance high)
  - `components[0].sidecars[0].image` : L'image exacte pour le Vault Agent n'est pas fournie. → hypothèse retenue : *hashicorp/vault-agent* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[search-api]']
- ⚠️ Champs laissés ouverts : ["unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (data nodes) (suggested_kind=None)"]
- Actions :
  - Extraction initiale + 2 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ["Le type de workload n'est pas précisé pour l'API.", "L'image exacte pour le Vault Agent n'est pas fournie."]

### Agent 2 - Template
- Champs traités : ['namespace', '[search-api] component_name', '[search-api] workload_type', '[search-api] image', '[search-api] replicas', '[search-api] ports: expose_service=true traduit en Service ClusterIP', '[search-api] env_vars: aucun', '[search-api] volumes: aucun', '[search-api] sidecars: vault-agent traité via injection automatique', '[search-api] security_requirements: exposition interne et Vault', '[search-api] observability_requirements: aucun', '[search-api] ingress: disabled', '[search-api] rbac: disabled (ServiceAccount créé)', '[search-api] service_mesh_routing: aucun', '[search-api] observability_style: annotations (rien à ajouter sans requirements)', '[search-api] cron_schedule: non applicable', '[search-api] config_maps: aucun', '[search-api] network_policy: restrict_egress=false, ingress restreint via security_requirements', '[search-api] deployment_strategy: aucun', '[search-api] namespace', "[search-api] security_requirements: Exposition uniquement interne -> Service type ClusterIP + NetworkPolicy restreignant l'ingress au namespace", "[search-api] security_requirements: Authentification et injection de credentials via Vault -> Ajout de l'annotation vault.hashicorp.com/agent-inject: 'true' pour l'injecteur", '[search-api] observability_requirements: Aucune exigence spécifiée', '[search-api] ingress: ingress.enabled=False, aucune ressource générée', '[search-api] rbac: ServiceAccount search-api-sa créé, Role/Binding omis car rbac.enabled=False']
- ⚠️ Champs laissés ouverts : ['unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'search' généré (une seule fois, déterministe)
  - [search-api] 1 sidecar(s) empaqueté(s) dans le même Pod : ['Injection automatique des credentials via Vault Agent Injector']
  - Génération BEST-EFFORT (non vérifiée, un appel LLM par exigence) pour 1 exigence(s) hors du schéma structuré : ["Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (data nodes)"]
- Avertissements : ["[search-api] Le sidecar 'vault-agent' a été implémenté via l'annotation d'injection automatique 'vault.hashicorp.com/agent-inject' conformément au pattern Vault Agent Injector, et non via un conteneur manuel."]

### Agent 3 - Validation
- Champs traités : ['namespace', 'replicas', 'image', 'ports', 'sidecars', 'serviceAccount', 'rbac', 'ingress', 'env_vars', 'volumes']
- Actions :
  - apiVersion présent
  - kind présent
  - metadata.name présent
  - spec présent
  - Service selector aligné avec Deployment labels (app: search-api)
  - ServiceAccount présent malgré rbac.enabled=false
  - Sidecar Vault traité correctement via annotation d'injection automatique (pas de doublon de conteneur)
  - Replicas cohérents avec la spec (2)
  - Ports cohérents (8080)
  - Namespace cohérent (search)
  - Indentation YAML valide

### Agent 4 - Énergie
- Champs traités : ['[search-api] resource_hints', '[search-api] traffic_windows', '[search-api] replicas', '[search-api] energy_goals: Optimisation du dimensionnement des ressources pour éviter le gaspillage', "[search-api] energy_goals: Mise en place d'un scaling automatique pour adapter la consommation à la charge"]
- Actions :
  - [search-api] Ajout de resources.requests (100m CPU, 256Mi RAM) et limits (500m CPU, 512Mi RAM) : valeurs prudentes proposées pour une API de recherche en l'absence de resource_hints
  - [search-api] Ajout d'un HorizontalPodAutoscaler (HPA) avec min=2 et max=5 réplicas, cible CPU 60% pour optimiser le coût énergétique selon la charge réelle
  - [search-api] Ajout de livenessProbe et readinessProbe via tcpSocket sur le port 8080 pour éliminer les pods zombies et optimiser le cycle de vie des ressources
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['/']."]

### Agent 5 - Vérification finale
- Champs traités : ['namespace', 'search-api workload', 'internal networking', 'vault-agent injection', 'resource limits/requests', 'hpa scaling', 'elasticsearch cluster']
- ⚠️ Champs laissés ouverts : ["Requirement 'Cluster Elasticsearch géré par l'opérateur ECK' was generated in best-effort mode by Agent 2 and remains non-verified by the structural pipeline.", "1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (data nodes)'"]
- Actions :
  - yaml.safe_load_all OK sur 7 documents
  - Cross-reference: Service selector 'app: search-api' matches Deployment labels
  - Cross-reference: HPA target 'search-api' matches Deployment name
  - Cross-reference: Deployment serviceAccountName 'search-api-sa' matches ServiceAccount name
  - Port consistency: Service targetPort 8080 matches Deployment containerPort 8080 and Probes
  - Sidecar check: Vault Agent implemented via annotation 'vault.hashicorp.com/agent-inject' as per spec requirement
  - Corrigé: Ajout du namespace 'search' à la ressource Elasticsearch pour cohérence avec le reste du manifeste
  - Contrôle déterministe Python : OK
- Avertissements : ['The Elasticsearch resource requires the ECK operator to be pre-installed in the cluster.', 'The Elasticsearch configuration (version 8.12.0, roles) was assumed by Agent 2 and should be verified.']

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | search | manifest (Namespace, metadata.namespace) |
| components[0].component_name | search-api | manifest (Deployment, Service, HPA, NetworkPolicy) |
| components[0].image | myregistry/search:1.0 | manifest (Deployment container image) |
| components[0].replicas | 2 | manifest (Deployment replicas, HPA minReplicas) |
| components[0].ports[0].container_port | 8080 | manifest (Deployment containerPort, Service targetPort, Probes) |
| components[0].security_requirements[0] | Exposition uniquement interne | manifest (Service type ClusterIP, NetworkPolicy) |
| components[0].security_requirements[1] | Injection credentials via Vault | manifest (Deployment annotation vault.hashicorp.com/agent-inject) |
| unmapped_requirements[0] | Cluster Elasticsearch ECK 3 nodes | manifest (Elasticsearch Custom Resource - Best Effort) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (data nodes) (kind inconnu)

## 7. ⚠️ À vérifier / relancer si besoin

- 1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (data nodes)'
- Requirement 'Cluster Elasticsearch géré par l'opérateur ECK' was generated in best-effort mode by Agent 2 and remains non-verified by the structural pipeline.
- unmapped_requirements: 1 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (data nodes) (suggested_kind=None)

## Métriques d'exécution

- Latence totale du run : **704.616 s** (dont pipeline seul : 704.616 s)
- Appels LLM : **12** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 701.755 s (moyenne 58.48 s/appel)
- Tokens consommés : **43058** (33135 prompt + 9923 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 59.472 | 5556 |
| Agent 1 - Analyse (self-check) | 3 | 80.95 | 4259 |
| Agent 1 - Analyse (réparation) | 2 | 135.981 | 5524 |
| Agent 1 - Analyse (réparation schéma) | 1 | 48.734 | 2748 |
| Agent 2 - Template | 1 | 77.28 | 6789 |
| Agent 2 - Template (best-effort) | 1 | 92.874 | 6281 |
| Agent 3 - Validation | 1 | 54.058 | 2651 |
| Agent 4 - Énergie | 1 | 51.971 | 3329 |
| Agent 5 - Vérification finale | 1 | 100.434 | 5921 |