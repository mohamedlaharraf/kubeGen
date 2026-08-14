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
- ⚠️ Dépendances vers des composants inexistants : ["'search-api' dépend de 'elasticsearch', qui n'existe pas parmi les composants générés."]

## 2bis. Contraintes globales (blackboard)

Extraites séparément des composants par l'Agent 1, visibles par tout agent en aval qui filtre par portée — voir `schemas.GlobalConstraint` pour le mécanisme complet.

- **[all_containers/security]** Authentification gérée via HashiCorp Vault avec injection automatique des credentials dans les pods via Vault Agent Injector

- Auto-check réussi : **True**
- Tentatives de réparation internes : 3
- ⚠️ Exigences jamais couvertes : ["Déployer un cluster Elasticsearch à 3 nœuds via l'opérateur ECK"]
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].labels` : Quels labels applicatifs doivent être appliqués ? → hypothèse retenue : *Utilisation du label par défaut app: search-api.* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[search-api]', 'global_constraints']
- ⚠️ Champs laissés ouverts : ["Déployer un cluster Elasticsearch à 3 nœuds via l'opérateur ECK", "unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (suggested_kind=None)"]
- Actions :
  - Extraction initiale + 2 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : 1 extraite(s) : ['Authentification gérée via HashiCorp Vault avec injection automatique des credentials dans les pods via Vault Agent Injector']
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ['Quels labels applicatifs doivent être appliqués ?']

### Agent 2 - Template
- Champs traités : ['namespace', '[search-api] global_constraints: Authentification gérée via HashiCorp Vault avec injection automatique des credentials dans les pods via Vault Agent Injector', '[search-api] component_name (search-api)', '[search-api] workload_type (Deployment)', '[search-api] image (myregistry/search:1.0)', '[search-api] replicas (2)', '[search-api] labels (app: search-api)', '[search-api] ports (http: 8080/TCP avec expose_service=True)', '[search-api] namespace (search)', '[search-api] env_vars: aucun demandé', '[search-api] volumes: aucun demandé', '[search-api] sidecars: aucun demandé', '[search-api] depends_on: pris en compte (elasticsearch)', '[search-api] config_maps: aucune demandée', '[search-api] cron_schedule: non applicable', '[search-api] network_policy: non demandée', '[search-api] deployment_strategy: non demandée', '[search-api] security_requirements: Durcissement de la sécurité par défaut : securityContext Pod et Container (runAsNonRoot, allowPrivilegeEscalation=false, readOnlyRootFilesystem=true, capabilities drop ALL, seccompProfile RuntimeDefault)', "[search-api] security_requirements: Service de type ClusterIP pour restreindre l'accès à l'interne du cluster", "[search-api] security_requirements: Injection d'annotations pour Vault Agent Injector (vault.hashicorp.com/agent-inject et vault.hashicorp.com/role)", "[search-api] observability_requirements: Aucune exigence d'observabilité spécifique fournie dans la spec", '[search-api] ingress: Ingress non activé (ingress=None)', '[search-api] rbac: Création du ServiceAccount dédié search-api-sa sans permissions associées (rbac.enabled=False, principe de moindre privilège)']
- ⚠️ Champs laissés ouverts : ["[search-api] resources.requests/limits et HPA (délégués à l'Agent 4)", "[search-api] Configuration fine du Vault Role et des politiques d'accès aux secrets dans l'instance HashiCorp Vault externe", 'unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'search' généré (une seule fois, déterministe)
  - [search-api] 1 contrainte(s) globale(s) du blackboard appliquée(s) : ['Authentification gérée via HashiCorp Vault avec injection automatique des credentials dans les pods via Vault Agent Injector']
  - Génération best-effort : 1 contrainte(s) globale(s) du blackboard transmise(s) (ex: chiffrement au repos sur tous les volumes) : ['Authentification gérée via HashiCorp Vault avec injection automatique des credentials dans les pods via Vault Agent Injector']
  - Génération BEST-EFFORT (non vérifiée) pour 1 exigence(s) hors du schéma structuré : ["Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données"]
- Avertissements : ["[search-api] L'utilisation de Vault Agent Injector nécessite que l'opérateur Vault soit installé dans le cluster et que le rôle Vault 'search-api' soit préalablement configuré.", "[search-api] readOnlyRootFilesystem est activé par défaut. Si le conteneur search-api nécessite d'écrire des fichiers temporaires, un volume emptyDir (ex: sur /tmp) devra être ajouté."]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'architecture_type', 'components', 'components.component_name', 'components.workload_type', 'components.image', 'components.replicas', 'components.labels', 'components.ports', 'components.env_vars', 'components.volumes', 'components.sidecars', 'components.security_requirements', 'components.ingress', 'components.rbac', 'components.observability_style', 'components.cron_schedule', 'global_constraints']
- Actions :
  - apiVersion et kind valides pour toutes les ressources
  - Champs metadata.name et metadata.namespace cohérents
  - Labels et selectors alignés entre Deployment et Service
  - ServiceAccount 'search-api-sa' présent et correctement référencé dans spec.template.spec.serviceAccountName
  - Annotations Vault Agent Injector présentes conformément aux exigences de sécurité et contraintes globales
  - securityContext défini au niveau pod et conteneur sans sur-privilèges

### Agent 4 - Énergie
- Champs traités : ['[search-api] resources', '[search-api] livenessProbe', '[search-api] readinessProbe', '[search-api] workload_type', '[search-api] replicas']
- Actions :
  - [search-api] 1 contrainte(s) globale(s) du blackboard prise(s) en compte pour l'optimisation énergie : ['Authentification gérée via HashiCorp Vault avec injection automatique des credentials dans les pods via Vault Agent Injector']
  - [search-api] Ajout de resources.requests (CPU 100m, mémoire 128Mi) et resources.limits (CPU 500m, mémoire 256Mi) calibrés pour une API standard sans contrainte explicite de volumétrie.
  - [search-api] Ajout des sondes livenessProbe et readinessProbe basées sur tcpSocket (port 8080) afin d'éviter les pods zombies consommateurs sans supposer de route HTTP.
  - [search-api] Absence de HPA : ni energy_goals ni traffic_windows ni le profil n'indiquent de besoin de variation de charge dynamique, ajouter un HPA créerait un sur-provisionnement inutile du plan de contrôle.
  - [search-api] Absence de PodDisruptionBudget : bien que replicas=2, aucune exigence de haute disponibilité critique n'a été spécifiée.
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['/']."]

### Agent 5 - Vérification finale
- Champs traités : ['manifest_syntax_validation', 'cross_resource_references', 'traceability_audit', 'global_constraints_coverage_check']
- ⚠️ Champs laissés ouverts : ["unmapped_requirements: 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données' généré en best-effort par l'Agent 2 sous forme de CRD libre sans schéma formel validé", "1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données'"]
- Actions :
  - yaml.safe_load_all valide sur les 6 documents YAML
  - Validation des types (cpu '100m'/'500m', memory '128Mi'/'256Mi', replicas int)
  - Cohérence selector/labels entre Deployment search-api et Service search-api
  - Référence ServiceAccount search-api-sa et elasticsearch-sa valide
  - Contraintes globales de sécurité (Vault Agent Injector) vérifiées sur l'ensemble des pods
  - Corrigé: Uniformisation de la déclaration du Namespace 'search' sur tous les documents du manifeste, y compris le fragment best-effort ECK
  - Contrôle déterministe Python : OK
- Avertissements : ["Le fragment CustomResource Elasticsearch (ECK) repose sur l'opérateur Elastic Cloud on Kubernetes qui doit être préalablement installé sur le cluster cible.", "L'utilisation de Vault Agent Injector nécessite la présence du mutating webhook Vault et l'existence des rôles 'search-api' et 'elasticsearch-role' dans l'instance Vault."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | search | manifest (Namespace/search et metadata.namespace sur tous les documents) |
| components[search-api].image | myregistry/search:1.0 | manifest (Deployment search-api spec.template.spec.containers[0].image) |
| components[search-api].replicas | 2 | manifest (Deployment search-api spec.replicas=2) |
| components[search-api].ports[0] | 8080/TCP (expose_service=True) | manifest (Deployment search-api containerPort=8080, Service search-api port=8080/targetPort=8080) |
| global_constraints[0] | Authentification HashiCorp Vault Agent Injector | manifest (annotations vault.hashicorp.com/agent-inject: 'true' sur Deployment search-api et Elasticsearch CRD) |
| unmapped_requirements[0] | Cluster Elasticsearch 3 nœuds via opérateur ECK | manifest (Elasticsearch/elasticsearch-cluster fragment best-effort non garanti) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (kind inconnu)

## 7. ⚠️ À vérifier / relancer si besoin

- 1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données'
- Déployer un cluster Elasticsearch à 3 nœuds via l'opérateur ECK
- [search-api] Configuration fine du Vault Role et des politiques d'accès aux secrets dans l'instance HashiCorp Vault externe
- [search-api] resources.requests/limits et HPA (délégués à l'Agent 4)
- unmapped_requirements: 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données' généré en best-effort par l'Agent 2 sous forme de CRD libre sans schéma formel validé
- unmapped_requirements: 1 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (suggested_kind=None)

## Métriques d'exécution

- Latence totale du run : **160.105 s** (dont pipeline seul : 160.105 s)
- Appels LLM : **14** (1 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 155.1 s (moyenne 11.079 s/appel)
- Tokens consommés : **45495** (36772 prompt + 8723 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 2 (1 échoué(s)) | 28.558 | 6230 |
| Agent 1 - Analyse (self-check) | 3 | 13.145 | 3507 |
| Agent 1 - Analyse (réparation) | 2 | 28.449 | 4168 |
| Agent 1 - Analyse (contraintes globales) | 1 | 5.591 | 1153 |
| Agent 1 - Analyse (réparation schéma) | 1 | 8.334 | 2200 |
| Agent 2 - Template | 1 | 15.816 | 6959 |
| Agent 2 - Template (best-effort) | 1 | 12.72 | 6596 |
| Agent 3 - Validation | 1 | 12.899 | 3306 |
| Agent 4 - Énergie | 1 | 13.526 | 4317 |
| Agent 5 - Vérification finale | 1 | 16.062 | 7059 |