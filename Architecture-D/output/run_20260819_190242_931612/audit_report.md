# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> 
Déploie une API de recherche "search-api" (image myregistry/search:1.0),
namespace "search", 2 réplicas, port 8080 en HTTP, exposée uniquement en
interne.

Elle a besoin d'un cluster Elasticsearch géré par l'opérateur ECK (Elastic
Cloud on Kubernetes) avec 3 nœuds de données et de l'authentification
gérée via HashiCorp Vault pour injecter les credentials automatiquement
dans les pods (Vault Agent Injector).



## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `search-api` (Deployment)

## 2bis. Contraintes globales (blackboard)

Extraites séparément des composants par l'Agent 1, visibles par tout agent en aval qui filtre par portée — voir `schemas.GlobalConstraint` pour le mécanisme complet.

- **[all_containers/security]** Authentification et gestion des credentials gérées via HashiCorp Vault avec injection automatique dans les pods (Vault Agent Injector)

- Auto-check réussi : **True**
- Tentatives de réparation internes : 0
- ⚠️ Exigences jamais couvertes : ["Cluster Elasticsearch géré par l'opérateur ECK avec 3 nœuds de données"]
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].ports[0].name` : Quel est le nom du port HTTP 8080 ? → hypothèse retenue : *Nommé 'http' par défaut.* (confiance high)
  - `components[0].security_requirements` : Quelles sont les annotations ou rôles Vault exacts à configurer pour Vault Agent Injector ? → hypothèse retenue : *Capture sous forme d'exigence de sécurité pour que l'Agent 2 génère les annotations pod nécessaires.* (confiance medium)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[search-api]', 'global_constraints']
- ⚠️ Champs laissés ouverts : ["Cluster Elasticsearch géré par l'opérateur ECK avec 3 nœuds de données", "unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (suggested_kind=Elasticsearch)"]
- Actions :
  - Extraction initiale + 0 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : 1 extraite(s) : ['Authentification et gestion des credentials gérées via HashiCorp Vault avec injection automatique dans les pods (Vault Agent Injector)']
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ['Quel est le nom du port HTTP 8080 ?', 'Quelles sont les annotations ou rôles Vault exacts à configurer pour Vault Agent Injector ?']

### Agent 2 - Template
- Champs traités : ['namespace', '[search-api] global_constraints: Authentification et gestion des credentials gérées via HashiCorp Vault avec injection automatique dans les pods (Vault Agent Injector)', "[search-api] component_name: 'search-api' utilisé pour les nommages de ressources", "[search-api] workload_type: 'Deployment' généré", "[search-api] image: 'myregistry/search:1.0' assigné", '[search-api] replicas: 2 appliqué', "[search-api] labels: 'app: search-api' appliqué sur selector, template et metadata", "[search-api] ports: port 'http' (8080/TCP) configuré sur le conteneur et exposé via Service ClusterIP", '[search-api] env_vars: aucune variable fournie, aucune configurée', '[search-api] volumes: aucun volume PVC demandé', '[search-api] sidecars: aucun sidecar demandé', '[search-api] depends_on: aucune dépendance directe', "[search-api] namespace: 'search' appliqué à l'ensemble des ressources", "[search-api] rbac: ServiceAccount 'search-api-sa' créé ; pas de Role/RoleBinding car rbac.enabled=false", '[search-api] config_maps: aucune ConfigMap demandée', '[search-api] network_policy: non demandée', '[search-api] deployment_strategy: stratégie par défaut Deployment', '[search-api] cron_schedule: non applicable pour Deployment', "[search-api] security_requirements: Injection automatique Vault configurée via les annotations d'injection Vault Agent (vault.hashicorp.com/agent-inject=true et vault.hashicorp.com/role=search-api)", '[search-api] security_requirements: Hardening de sécurité de base appliqué au pod (runAsNonRoot, seccomp RuntimeDefault) et au conteneur (allowPrivilegeEscalation=false, readOnlyRootFilesystem=true, capabilities DROP ALL)', "[search-api] observability_requirements: observability_style 'annotations' pris en compte (aucune exigence explicite dans observability_requirements)", '[search-api] ingress: ingress: non configuré (valeur null)', "[search-api] rbac: ServiceAccount dédié créé ('search-api-sa') conformément au principe de moindre privilège", '[search-api] rbac: Aucun rôle excessif attribué (rbac.enabled=false)']
- ⚠️ Champs laissés ouverts : ["[search-api] resource requirements/limits et HPA/autoscaling réservés pour l'Agent 4", "[search-api] La configuration exacte des chemins de secrets à injecter par Vault Agent nécessite une configuration fine d'annotations Vault spécifiques (ex: vault.hashicorp.com/agent-inject-secret-...)", 'unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'search' généré (une seule fois, déterministe)
  - [search-api] 1 contrainte(s) globale(s) du blackboard appliquée(s) : ['Authentification et gestion des credentials gérées via HashiCorp Vault avec injection automatique dans les pods (Vault Agent Injector)']
  - Génération best-effort : 1 contrainte(s) globale(s) du blackboard transmise(s) (ex: chiffrement au repos sur tous les volumes) : ['Authentification et gestion des credentials gérées via HashiCorp Vault avec injection automatique dans les pods (Vault Agent Injector)']
  - Génération BEST-EFFORT (non vérifiée) pour 1 exigence(s) hors du schéma structuré : ["Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données"]
- Avertissements : ["[search-api] L'injection automatique Vault dépend de la présence et de la configuration du Vault Agent Injector (mutating webhook) et de l'existence du rôle 'search-api' dans HashiCorp Vault.", "[search-api] readOnlyRootFilesystem est activé par défaut. Si l'application a besoin d'écrire dans des répertoires temporaires (ex: /tmp), ajouter un volume emptyDir."]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'architecture_type', 'components[0].component_name', 'components[0].workload_type', 'components[0].image', 'components[0].replicas', 'components[0].labels', 'components[0].ports', 'components[0].env_vars', 'components[0].volumes', 'components[0].sidecars', 'components[0].security_requirements', 'components[0].ingress', 'components[0].rbac', 'components[0].observability_style', 'components[0].cron_schedule', 'global_constraints']
- Actions :
  - apiVersion et kind valides sur toutes les ressources (Namespace, ServiceAccount, Service, Deployment)
  - Nommage et namespace cohérents (search)
  - ServiceAccount dédié présent et correctement référencé dans le Deployment
  - Correspondance exacte entre le selector du Service et les labels du Pod template (app: search-api)
  - Alignement des ports Service (8080) et containerPort (8080)
  - Présence des annotations d'injection Vault conformément aux spécifications et aux contraintes globales
  - SecurityContext au niveau Pod et Conteneur configuré selon les meilleures pratiques de sécurité
- Avertissements : ['validation_errors: [deterministic-cross-reference] Deployment \'search-api\' : annoté pour l\'injection Vault Agent (vault.hashicorp.com/agent-inject: "true") et readOnlyRootFilesystem: true sur le conteneur \'search-api\', mais aucun volume monté sous un chemin contenant \'vault\' (ex: emptyDir sur /vault/secrets) -- Vault Agent Injector ne pourra probablement pas écrire les secrets, le pod risque de ne pas démarrer correctement. (None)']

### Agent 2 - Correction sur retour (itération 1)
- Champs traités : []
- Actions :
  - Deployment/search-api : ajout d'un volume emptyDir 'vault-secrets' monté sur '/vault/secrets' pour le conteneur 'search-api'
- Avertissements : ["Ajout de la configuration de volume emptyDir sur /vault/secrets afin de permettre à Vault Agent d'écrire les secrets tout en conservant readOnlyRootFilesystem: true."]

### Agent 3 - Validation (itération 1)
- Champs traités : ['namespace', 'components.search-api.workload_type', 'components.search-api.image', 'components.search-api.replicas', 'components.search-api.labels', 'components.search-api.ports', 'components.search-api.security_requirements', 'components.search-api.rbac', 'global_constraints']
- Actions :
  - Présence et validité des champs de structure de base (apiVersion, kind, metadata, spec) sur toutes les ressources
  - Cohérence des namespaces ('search') sur l'ensemble des ressources
  - Alignement strict des labels et selectors entre Deployment et Service ('app: search-api')
  - Présence du ServiceAccount dédié ('search-api-sa') lié au Deployment
  - Conformité des contextes de sécurité au niveau Pod et Conteneur (runAsNonRoot, seccompProfile, drop ALL, readOnlyRootFilesystem)
  - Prise en compte de la contrainte globale Vault Agent Injector via les annotations appropriées

### Agent 4 - Débat multi-agents (Énergie)
- Champs traités : ['[search-api] spec.template.spec.nodeSelector', '[search-api] spec.template.spec.affinity', '[search-api] spec.template.spec.containers[0].resources', '[search-api] spec.template.spec.containers[0].livenessProbe', '[search-api] spec.template.spec.containers[0].readinessProbe']
- Actions :
  - [search-api] Débat conclu : 1 tour(s) de critique, 3 conflit(s) réel(s) relevé(s), scores {'consolidation': 8.5, 'sizing': 9.0, 'autoscaling': 8.5}.
  - [search-api] Éléments retenus par stratégie : {'placement': 'consolidation', 'resources': 'sizing', 'probes': 'sizing', 'autoscaling': 'autoscaling'}
  - [search-api] La fusion combine les éléments complémentaires des trois stratégies tout en tranchant le seul conflit réel concernant la définition des ressources. 1) Sizing vs Consolidation sur le bloc 'resources': Consolidation proposait un sur-engagement agressif (100m CPU / 128Mi RAM en requests, ratios de 5x et 4x avec les limits), ce qui présente un risque de performance (throttling CPU et OOMKills) pour une API de recherche interagissant avec Elasticsearch et Vault. La proposition de Sizing (150m/256Mi requests, 300m/384Mi limits) a été retenue car elle assure la stabilité applicative avec un risque SLA quasi nul pour une économie d'énergie équivalente (20%). 2) Placement: La proposition de Consolidation (nodeSelector nodepool: shared + podAffinity préférentielle) a été retenue car elle permet de compacter les workloads sur le même pool de nœuds sans perturber le fonctionnement de l'application. 3) Autoscaling: Conformément aux avis convergents de Sizing et Autoscaling, aucun HPA/ScaledObject n'a été ajouté en l'absence de métriques/variations de trafic dynamiques, évitant ainsi la surcharge inutile de la boucle de contrôle K8s. 4) Probes: Les sondes liveness/readiness via tcpSocket proposées conjointement par Sizing et Consolidation ont été conservées.

### Agent 5 - Vérification finale
- Champs traités : ['syntax_validation', 'type_checking', 'cross_references_validation', 'traceability_matrix_generation']
- ⚠️ Champs laissés ouverts : ["unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (exigence hors schéma applicatif direct, nécessite l'installation préalable du CRD ECK/Elasticsearch)", "1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données' (kind supposé: Elasticsearch)"]
- Actions :
  - yaml.safe_load_all OK sur 4 documents (ServiceAccount, Service, Deployment, Namespace)
  - Validation des types K8s (cpu: 150m/300m, memory: 256Mi/384Mi, replicas: 2) OK
  - Coherence des références croisées (Service selector 'app: search-api' -> Deployment pod label 'app: search-api', targetPort 8080 -> containerPort 8080, serviceAccountName 'search-api-sa' -> ServiceAccount) OK
  - Coherence des volumes (emptyDir 'vault-secrets' monté sur '/vault/secrets') OK
  - Contrôle déterministe Python : OK

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | search | manifest (Namespace/search, metadata.namespace sur toutes les ressources) |
| components[0].component_name | search-api | manifest (Deployment, Service, ServiceAccount metadata.name=search-api) |
| components[0].image | myregistry/search:1.0 | manifest (Deployment spec.template.spec.containers[0].image) |
| components[0].replicas | 2 | manifest (Deployment spec.replicas=2) |
| components[0].ports[0] | 8080/TCP (http) | manifest (Deployment containerPort=8080, Service port=8080/targetPort=8080) |
| global_constraints[0] | Authentification et injection automatique des credentials Vault | manifest (Deployment annotations vault.hashicorp.com/agent-inject=true et vault.hashicorp.com/role=search-api, volume emptyDir /vault/secrets) |
| unmapped_requirements[0] | Cluster Elasticsearch géré par l'opérateur ECK avec 3 nœuds de données | unresolved_items (non pris en charge directement dans les manifestes applicatifs standard K8s) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (kind supposé : `Elasticsearch`)

## 7. ⚠️ À vérifier / relancer si besoin

- 1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données' (kind supposé: Elasticsearch)
- Cluster Elasticsearch géré par l'opérateur ECK avec 3 nœuds de données
- [search-api] La configuration exacte des chemins de secrets à injecter par Vault Agent nécessite une configuration fine d'annotations Vault spécifiques (ex: vault.hashicorp.com/agent-inject-secret-...)
- [search-api] resource requirements/limits et HPA/autoscaling réservés pour l'Agent 4
- unmapped_requirements: 1 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (exigence hors schéma applicatif direct, nécessite l'installation préalable du CRD ECK/Elasticsearch)
- unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (suggested_kind=Elasticsearch)

## Métriques d'exécution

- Latence totale du run : **261.384 s** (dont pipeline seul : 261.384 s)
- Appels LLM : **20** (3 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 384.502 s (moyenne 19.225 s/appel)
- Tokens consommés : **68671** (54532 prompt + 14139 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 21.632 | 6368 |
| Agent 1 - Analyse (self-check) | 1 | 7.169 | 1205 |
| Agent 1 - Analyse (contraintes globales) | 1 | 5.321 | 1152 |
| Agent 1 - Analyse (réparation schéma) | 1 | 23.945 | 2286 |
| Agent 2 - Template | 1 | 14.001 | 7074 |
| Agent 2 - Template (best-effort) | 1 | 13.482 | 6473 |
| Agent 3 - Validation | 2 | 30.9 | 6758 |
| Agent 2 - Correction sur retour | 1 | 21.854 | 1631 |
| Agent4-Debate-Strategy-consolidation | 2 (1 échoué(s)) | 21.332 | 2605 |
| Agent4-Debate-Strategy-sizing | 1 | 17.679 | 2762 |
| Agent4-Debate-Strategy-autoscaling | 1 | 30.957 | 2728 |
| Agent4-Debate-Strategy-consolidation-Critique | 1 | 34.69 | 5035 |
| Agent4-Debate-Strategy-sizing-Critique | 2 (1 échoué(s)) | 52.452 | 4998 |
| Agent4-Debate-Strategy-autoscaling-Critique | 2 (1 échoué(s)) | 56.459 | 4974 |
| Agent4-Debate-Judge | 1 | 15.148 | 5484 |
| Agent 5 - Vérification finale | 1 | 17.48 | 7138 |