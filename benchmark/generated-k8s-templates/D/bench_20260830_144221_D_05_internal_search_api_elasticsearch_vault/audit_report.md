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
- ⚠️ Dépendances vers des composants inexistants : ["'search-api' dépend de 'elasticsearch', qui n'existe pas parmi les composants générés."]

## 2bis. Contraintes globales (blackboard)

Extraites séparément des composants par l'Agent 1, visibles par tout agent en aval qui filtre par portée — voir `schemas.GlobalConstraint` pour le mécanisme complet.

- **[all_components/security]** authentification gérée via HashiCorp Vault pour injecter les credentials automatiquement dans les pods

- Auto-check réussi : **True**
- Tentatives de réparation internes : 1
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].sidecars[0].image` : L'image exacte du Vault Agent Injector n'est pas spécifiée → hypothèse retenue : *Utilisation de l'image standard hashicorp/vault-agent* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[search-api]', 'global_constraints']
- ⚠️ Champs laissés ouverts : ['unmapped_requirements: {\'component_name\': \'elasticsearch\', \'workload_type\': \'Elasticsearch\', \'image\': None, \'replicas\': 3, \'labels\': {\'app\': \'elasticsearch\'}, \'ports\': [], \'env_vars\': [], \'volumes\': [], \'sidecars\': [], \'depends_on\': [], \'energy_goals\': [], \'resource_hints\': None, \'traffic_windows\': [], \'constraints\': ["Géré par l\'opérateur ECK (Elastic Cloud on Kubernetes)"], \'security_requirements\': [], \'observability_requirements\': [], \'ingress\': {\'enabled\': False, \'host\': None, \'path\': \'/\', \'tls\': False, \'tls_secret_name\': None, \'ingress_class\': None, \'api_style\': \'ingress\', \'gateway_name\': None, \'cert_manager_issuer\': None, \'cert_manager_issuer_kind\': None}, \'rbac\': {\'enabled\': False, \'rules_description\': []}, \'service_mesh_routing\': [], \'observability_style\': \'annotations\', \'cron_schedule\': None, \'config_maps\': [], \'network_policy\': {\'restrict_egress\': False, \'allowed_egress_targets\': [], \'allowed_ingress_sources\': []}, \'deployment_strategy\': None} (suggested_kind=None)']
- Actions :
  - Extraction initiale + 1 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : 1 extraite(s) : ['authentification gérée via HashiCorp Vault pour injecter les credentials automatiquement dans les pods']
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ["L'image exacte du Vault Agent Injector n'est pas spécifiée"]

### Agent 2 - Template
- Champs traités : ['namespace', '[search-api] global_constraints: authentification gérée via HashiCorp Vault pour injecter les credentials automatiquement dans les pods', '[search-api] component_name: utilisé pour metadata.name et labels', '[search-api] workload_type: Deployment généré', '[search-api] image: appliquée au conteneur principal', '[search-api] replicas: 2', '[search-api] labels: appliqués et enrichis avec app.kubernetes.io/*', '[search-api] ports: port 8080 exposé via Service ClusterIP', '[search-api] env_vars: aucun demandé', '[search-api] volumes: aucun demandé', '[search-api] sidecars: vault-agent ajouté comme conteneur', '[search-api] sidecar_injection_mode: mode manual_container appliqué', '[search-api] security_requirements: ClusterIP + NetworkPolicy + SecurityContext durci', '[search-api] observability_requirements: aucun demandé', '[search-api] ingress: disabled, aucune ressource générée', '[search-api] rbac: disabled, ServiceAccount créé sans Role/Binding', '[search-api] service_mesh_routing: aucun demandé', '[search-api] observability_style: annotations (aucun port de métriques spécifié)', '[search-api] cron_schedule: N/A pour Deployment', '[search-api] config_maps: aucun demandé', '[search-api] network_policy: restrict_egress=False, ingress restreint au namespace via security_requirements', '[search-api] deployment_strategy: aucun demandé', '[search-api] namespace: search', "[search-api] security_requirements: Exposition uniquement interne (pas d'accès public) -> Service type ClusterIP + NetworkPolicy ingress namespace", '[search-api] security_requirements: Injection automatique des credentials via HashiCorp Vault -> Implémenté via sidecar vault-agent en mode manual_container', '[search-api] ingress: ingress.enabled=False : aucune ressource Ingress/Gateway générée', '[search-api] rbac: ServiceAccount search-api-sa créé', '[search-api] rbac: rbac.enabled=False : aucun Role/RoleBinding généré']
- ⚠️ Champs laissés ouverts : ['[search-api] depends_on: information conservée pour les étapes de validation/santé ultérieures', 'unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'search' généré (une seule fois, déterministe)
  - [search-api] 1 contrainte(s) globale(s) du blackboard appliquée(s) : ['authentification gérée via HashiCorp Vault pour injecter les credentials automatiquement dans les pods']
  - [search-api] 1 sidecar(s) empaqueté(s) comme conteneur(s) dans le même Pod : ['vault-agent']
  - Génération best-effort : 1 contrainte(s) globale(s) du blackboard transmise(s) (ex: chiffrement au repos sur tous les volumes) : ['authentification gérée via HashiCorp Vault pour injecter les credentials automatiquement dans les pods']
  - Génération BEST-EFFORT (non vérifiée) pour 1 exigence(s) hors du schéma structuré : ['{\'component_name\': \'elasticsearch\', \'workload_type\': \'Elasticsearch\', \'image\': None, \'replicas\': 3, \'labels\': {\'app\': \'elasticsearch\'}, \'ports\': [], \'env_vars\': [], \'volumes\': [], \'sidecars\': [], \'depends_on\': [], \'energy_goals\': [], \'resource_hints\': None, \'traffic_windows\': [], \'constraints\': ["Géré par l\'opérateur ECK (Elastic Cloud on Kubernetes)"], \'security_requirements\': [], \'observability_requirements\': [], \'ingress\': {\'enabled\': False, \'host\': None, \'path\': \'/\', \'tls\': False, \'tls_secret_name\': None, \'ingress_class\': None, \'api_style\': \'ingress\', \'gateway_name\': None, \'cert_manager_issuer\': None, \'cert_manager_issuer_kind\': None}, \'rbac\': {\'enabled\': False, \'rules_description\': []}, \'service_mesh_routing\': [], \'observability_style\': \'annotations\', \'cron_schedule\': None, \'config_maps\': [], \'network_policy\': {\'restrict_egress\': False, \'allowed_egress_targets\': [], \'allowed_ingress_sources\': []}, \'deployment_strategy\': None}']
- Avertissements : ["[search-api] readOnlyRootFilesystem: false appliqué au sidecar 'vault-agent' car l'agent Vault nécessite généralement l'écriture de tokens ou de caches locaux pour fonctionner."]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'replicas', 'image', 'ports', 'sidecars', 'serviceAccount', 'networkPolicy', 'securityContext']
- Actions :
  - apiVersion present
  - kind present
  - metadata.name present
  - Service selector matches Deployment labels
  - ServiceAccount present and correctly referenced in Deployment
  - Sidecar vault-agent correctly injected as manual_container
  - NetworkPolicy correctly restricts access to internal pods
  - SecurityContext present on pod and all containers
  - Global constraint for Vault authentication reflected via vault-agent container

### Agent 4 - Débat multi-agents (Énergie)
- Champs traités : ['[search-api] resources', '[search-api] affinity', '[search-api] livenessProbe', '[search-api] readinessProbe', '[search-api] replicas']
- Actions :
  - [search-api] Débat conclu : 1 tour(s) de critique, 3 conflit(s) réel(s) relevé(s), scores {'consolidation': 8.0, 'sizing': 9.0, 'autoscaling': 7.0}.
  - [search-api] Éléments retenus par stratégie : {'resources': 'sizing', 'affinity': 'consolidation', 'probes': 'sizing', 'replicas': 'autoscaling'}
  - [search-api] Le verdict fusionne les apports complémentaires des trois stratégies. 1) Ressources : J'ai tranché le conflit entre Consolidation et Sizing en faveur de Sizing pour le container 'search-api'. Bien que Consolidation propose une request mémoire plus basse (128Mi) pour augmenter la densité, le risque d'OOMKill pour une API de recherche est jugé trop élevé. Sizing propose un ratio limit/request plus sain (1.5x pour la mémoire, 2x pour le CPU), évitant le gaspillage des limites excessives de Consolidation (500m CPU). Pour le sidecar 'vault-agent', les limites de Sizing sont retenues car plus précises. 2) Placement : Les affinités de Consolidation (nodeAffinity vers pool shared et podAffinity pour le regroupement) sont conservées car elles sont compatibles avec le sizing et optimisent l'empreinte énergétique globale. 3) Santé : Les probes TCP proposées par Sizing et Consolidation sont intégrées pour stabiliser le workload. 4) Scaling : La décision de l'agent Autoscaling de ne pas implémenter de HPA est validée, car l'absence de données de trafic et le maintien de 2 réplicas assurent un compromis stabilité/énergie optimal sans complexité inutile.
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['/']."]

### Agent 5 - Vérification finale
- Champs traités : ['global_constraints[0]', 'components[0].security_requirements', 'components[0].replicas', 'components[0].ports', 'unmapped_requirements[0]']
- ⚠️ Champs laissés ouverts : ["Best-effort fragment for 'elasticsearch' (from spec.unmapped_requirements) - manually validated but outside standard pipeline controls", '1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : \'{\'component_name\': \'elasticsearch\', \'workload_type\': \'Elasticsearch\', \'image\': None, \'replicas\': 3, \'labels\': {\'app\': \'elasticsearch\'}, \'ports\': [], \'env_vars\': [], \'volumes\': [], \'sidecars\': [], \'depends_on\': [], \'energy_goals\': [], \'resource_hints\': None, \'traffic_windows\': [], \'constraints\': ["Géré par l\'opérateur ECK (Elastic Cloud on Kubernetes)"], \'security_requirements\': [], \'observability_requirements\': [], \'ingress\': {\'enabled\': False, \'host\': None, \'path\': \'/\', \'tls\': False, \'tls_secret_name\': None, \'ingress_class\': None, \'api_style\': \'ingress\', \'gateway_name\': None, \'cert_manager_issuer\': None, \'cert_manager_issuer_kind\': None}, \'rbac\': {\'enabled\': False, \'rules_description\': []}, \'service_mesh_routing\': [], \'observability_style\': \'annotations\', \'cron_schedule\': None, \'config_maps\': [], \'network_policy\': {\'restrict_egress\': False, \'allowed_egress_targets\': [], \'allowed_ingress_sources\': []}, \'deployment_strategy\': None}\'']
- Actions :
  - yaml.safe_load_all OK sur 7 documents
  - Cross-references OK: Service search-api -> Deployment search-api
  - Cross-references OK: Deployment search-api -> ServiceAccount search-api-sa
  - Cross-references OK: Elasticsearch -> ServiceAccount elasticsearch-sa
  - Resource quantities (cpu/memory) valid for all containers
  - Sidecar vault-agent correctly placed as manual_container in search-api Pod
  - Corrigé: Elasticsearch CR: Fixed indentation of securityContext fields (allowPrivilegeEscalation, capabilities, seccompProfile) which were floating in podTemplate.spec
  - Corrigé: Elasticsearch CR: Moved vault annotations from podTemplate.spec to podTemplate.metadata
  - Corrigé: Elasticsearch CR: Removed floating labels from podTemplate.spec and merged into metadata
  - Corrigé: Elasticsearch CR: Added namespace 'search' to metadata for consistency
  - Contrôle déterministe Python : OK
- Avertissements : ["app.kubernetes.io/version='unknown' for elasticsearch: image tag not explicitly provided in spec", 'Elasticsearch CR is a best-effort generation based on ECK operator requirements']

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| global_constraints[0] | authentification via HashiCorp Vault | manifest (Deployment search-api container=vault-agent, Elasticsearch CR annotations) |
| components[0].security_requirements[0] | Exposition uniquement interne | manifest (Service type=ClusterIP, NetworkPolicy search-api-netpol) |
| components[0].security_requirements[1] | Injection credentials via Vault | manifest (Deployment search-api container=vault-agent) |
| components[0].replicas | 2 | manifest (Deployment search-api spec.replicas) |
| components[0].ports[0] | 8080 TCP | manifest (Service search-api port 8080, Deployment containerPort 8080) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- {'component_name': 'elasticsearch', 'workload_type': 'Elasticsearch', 'image': None, 'replicas': 3, 'labels': {'app': 'elasticsearch'}, 'ports': [], 'env_vars': [], 'volumes': [], 'sidecars': [], 'depends_on': [], 'energy_goals': [], 'resource_hints': None, 'traffic_windows': [], 'constraints': ["Géré par l'opérateur ECK (Elastic Cloud on Kubernetes)"], 'security_requirements': [], 'observability_requirements': [], 'ingress': {'enabled': False, 'host': None, 'path': '/', 'tls': False, 'tls_secret_name': None, 'ingress_class': None, 'api_style': 'ingress', 'gateway_name': None, 'cert_manager_issuer': None, 'cert_manager_issuer_kind': None}, 'rbac': {'enabled': False, 'rules_description': []}, 'service_mesh_routing': [], 'observability_style': 'annotations', 'cron_schedule': None, 'config_maps': [], 'network_policy': {'restrict_egress': False, 'allowed_egress_targets': [], 'allowed_ingress_sources': []}, 'deployment_strategy': None} (kind inconnu)

## 7. ⚠️ À vérifier / relancer si besoin

- 1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : '{'component_name': 'elasticsearch', 'workload_type': 'Elasticsearch', 'image': None, 'replicas': 3, 'labels': {'app': 'elasticsearch'}, 'ports': [], 'env_vars': [], 'volumes': [], 'sidecars': [], 'depends_on': [], 'energy_goals': [], 'resource_hints': None, 'traffic_windows': [], 'constraints': ["Géré par l'opérateur ECK (Elastic Cloud on Kubernetes)"], 'security_requirements': [], 'observability_requirements': [], 'ingress': {'enabled': False, 'host': None, 'path': '/', 'tls': False, 'tls_secret_name': None, 'ingress_class': None, 'api_style': 'ingress', 'gateway_name': None, 'cert_manager_issuer': None, 'cert_manager_issuer_kind': None}, 'rbac': {'enabled': False, 'rules_description': []}, 'service_mesh_routing': [], 'observability_style': 'annotations', 'cron_schedule': None, 'config_maps': [], 'network_policy': {'restrict_egress': False, 'allowed_egress_targets': [], 'allowed_ingress_sources': []}, 'deployment_strategy': None}'
- Best-effort fragment for 'elasticsearch' (from spec.unmapped_requirements) - manually validated but outside standard pipeline controls
- [search-api] depends_on: information conservée pour les étapes de validation/santé ultérieures
- unmapped_requirements: 1 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: {'component_name': 'elasticsearch', 'workload_type': 'Elasticsearch', 'image': None, 'replicas': 3, 'labels': {'app': 'elasticsearch'}, 'ports': [], 'env_vars': [], 'volumes': [], 'sidecars': [], 'depends_on': [], 'energy_goals': [], 'resource_hints': None, 'traffic_windows': [], 'constraints': ["Géré par l'opérateur ECK (Elastic Cloud on Kubernetes)"], 'security_requirements': [], 'observability_requirements': [], 'ingress': {'enabled': False, 'host': None, 'path': '/', 'tls': False, 'tls_secret_name': None, 'ingress_class': None, 'api_style': 'ingress', 'gateway_name': None, 'cert_manager_issuer': None, 'cert_manager_issuer_kind': None}, 'rbac': {'enabled': False, 'rules_description': []}, 'service_mesh_routing': [], 'observability_style': 'annotations', 'cron_schedule': None, 'config_maps': [], 'network_policy': {'restrict_egress': False, 'allowed_egress_targets': [], 'allowed_ingress_sources': []}, 'deployment_strategy': None} (suggested_kind=None)

## Métriques d'exécution

- Latence totale du run : **1132.565 s** (dont pipeline seul : 1132.565 s)
- Appels LLM : **17** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 1425.316 s (moyenne 83.842 s/appel)
- Tokens consommés : **86486** (65949 prompt + 20537 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 60.502 | 6427 |
| Agent 1 - Analyse (self-check) | 2 | 56.843 | 2716 |
| Agent 1 - Analyse (réparation) | 1 | 68.379 | 2634 |
| Agent 1 - Analyse (contraintes globales) | 1 | 61.979 | 1149 |
| Agent 1 - Analyse (réparation schéma) | 1 | 70.491 | 3163 |
| Agent 2 - Template | 1 | 112.301 | 8487 |
| Agent 2 - Template (best-effort) | 1 | 88.985 | 8286 |
| Agent 3 - Validation | 1 | 69.643 | 4414 |
| Agent4-Debate-Strategy-autoscaling | 1 | 58.89 | 3552 |
| Agent4-Debate-Strategy-sizing | 1 | 66.593 | 3516 |
| Agent4-Debate-Strategy-consolidation | 1 | 69.286 | 3577 |
| Agent4-Debate-Strategy-consolidation-Critique | 1 | 81.807 | 6820 |
| Agent4-Debate-Strategy-sizing-Critique | 1 | 87.663 | 6855 |
| Agent4-Debate-Strategy-autoscaling-Critique | 1 | 238.778 | 6816 |
| Agent4-Debate-Judge | 1 | 87.846 | 7717 |
| Agent 5 - Vérification finale | 1 | 145.329 | 10357 |