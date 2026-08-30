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

- **[all_components/security]** authentification gérée via HashiCorp Vault pour injecter les credentials automatiquement dans les pods (Vault Agent Injector)

## 2ter. Boucle de réparation

- Tentatives effectuées : **1** (borne : 1)
- ✔ Tous les gaps détectés ont été résolus.

- Auto-check réussi : **False**
- Tentatives de réparation internes : 2
- ⚠️ Exigences jamais couvertes : ["The specific requirement that the 3 Elasticsearch nodes must be 'data nodes' (nœuds de données) is not explicitly captured in the constraints or configuration, only the number of replicas is mentioned."]
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].sidecars[0].image` : L'utilisateur mentionne le 'Vault Agent Injector' (qui est un webhook), mais pas l'image du sidecar résultant. → hypothèse retenue : *Utilisation de l'image standard 'hashicorp/vault-agent:latest' pour représenter le sidecar injecté.* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[search-api]', 'global_constraints']
- ⚠️ Champs laissés ouverts : ["The specific requirement that the 3 Elasticsearch nodes must be 'data nodes' (nœuds de données) is not explicitly captured in the constraints or configuration, only the number of replicas is mentioned.", "unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (suggested_kind=None)"]
- Actions :
  - Extraction initiale + 2 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : 1 extraite(s) : ['authentification gérée via HashiCorp Vault pour injecter les credentials automatiquement dans les pods (Vault Agent Injector)']
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ["L'utilisateur mentionne le 'Vault Agent Injector' (qui est un webhook), mais pas l'image du sidecar résultant."]

### Agent 2 - Template
- Champs traités : ['namespace', '[search-api] global_constraints: authentification gérée via HashiCorp Vault pour injecter les credentials automatiquement dans les pods (Vault Agent Injector)', '[search-api] component_name', '[search-api] workload_type', '[search-api] image', '[search-api] replicas', '[search-api] ports: expose_service=true traduit en Service ClusterIP', '[search-api] env_vars: aucun', '[search-api] volumes: aucun', '[search-api] sidecars: vault-agent ajouté en manual_container', '[search-api] sidecar_injection_mode: manual_container appliqué', '[search-api] security_requirements: exposition interne et Vault', '[search-api] observability_requirements: aucun', '[search-api] ingress: enabled=false, rien à générer', '[search-api] rbac: enabled=false, ServiceAccount seul', '[search-api] service_mesh_routing: aucun', '[search-api] observability_style: annotations (rien à scraper)', '[search-api] config_maps: aucun', '[search-api] network_policy: restrict_egress=false, ingress restreint au namespace via security_requirements', '[search-api] deployment_strategy: aucun', '[search-api] namespace', "[search-api] security_requirements: Exposition réseau uniquement interne -> Service type ClusterIP + NetworkPolicy restreignant l'ingress au namespace", '[search-api] security_requirements: Authentification et injection de credentials gérées via HashiCorp Vault -> Implémentation du sidecar vault-agent en mode manual_container', '[search-api] security_requirements: Hardening par défaut -> runAsNonRoot, allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities.drop: [ALL], seccompProfile: RuntimeDefault', '[search-api] observability_requirements: Aucune exigence spécifiée dans le composant', '[search-api] ingress: ingress.enabled=False : aucune ressource Ingress ou Gateway générée', '[search-api] rbac: ServiceAccount search-api-sa créé', '[search-api] rbac: rbac.enabled=False : aucun Role ou RoleBinding généré']
- ⚠️ Champs laissés ouverts : ['unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'search' généré (une seule fois, déterministe)
  - [search-api] 1 contrainte(s) globale(s) du blackboard appliquée(s) : ['authentification gérée via HashiCorp Vault pour injecter les credentials automatiquement dans les pods (Vault Agent Injector)']
  - [search-api] 1 sidecar(s) empaqueté(s) comme conteneur(s) dans le même Pod : ['vault-agent']
  - Génération best-effort : 1 contrainte(s) globale(s) du blackboard transmise(s) (ex: chiffrement au repos sur tous les volumes) : ['authentification gérée via HashiCorp Vault pour injecter les credentials automatiquement dans les pods (Vault Agent Injector)']
  - Génération BEST-EFFORT (non vérifiée) pour 1 exigence(s) hors du schéma structuré : ["Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données"]
- Avertissements : ["[search-api] Le sidecar 'vault-agent' a été ajouté comme conteneur manuel dans le Pod conformément au mode 'manual_container' spécifié pour l'injection des credentials Vault."]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'replicas', 'image', 'ports', 'sidecars', 'securityContext', 'serviceAccountName', 'networkPolicy']
- Actions :
  - apiVersion, kind, metadata.name, spec presence
  - Deployment/Service selector alignment
  - ServiceAccount presence (maintained despite rbac.enabled: false)
  - Sidecar injection mode 'manual_container' verified for vault-agent
  - SecurityContext presence and correctness (non-root, readOnlyRootFilesystem, capabilities drop)
  - Global constraint (Vault Agent) implemented via manual container
  - NetworkPolicy aligns with internal network exposure requirement

### Agent 4 - Énergie
- Champs traités : ['[search-api] energy_goals', '[search-api] resource_hints', '[search-api] traffic_windows', '[search-api] constraints', '[search-api] workload_type', '[search-api] replicas']
- Actions :
  - [search-api] 1 contrainte(s) globale(s) du blackboard prise(s) en compte pour l'optimisation énergie : ['authentification gérée via HashiCorp Vault pour injecter les credentials automatiquement dans les pods (Vault Agent Injector)']
  - [search-api] Dimensionnement des ressources (requests/limits) basé sur le profil 'criticité modérée' et 'trafic interne' de l'application_context : valeurs équilibrées pour éviter le gaspillage tout en assurant la stabilité du service de recherche.
  - [search-api] Pas de HPA — l'application_context indique explicitement qu'il n'y a pas de besoin de scaling dynamique, l'ajout d'un HPA serait du sur-provisionnement opérationnel inutile.
  - [search-api] Pas de PDB — la criticité modérée et le contexte d'API interne ne justifient pas l'ajout d'un budget de disruption malgré la présence de 2 réplicas.
  - [search-api] Ajout de sondes livenessProbe et readinessProbe via tcpSocket sur le port 8080 pour optimiser la gestion du cycle de vie des pods et éviter la consommation de ressources par des pods zombies, sans supposer de chemin HTTP.
  - [search-api] Ajout de limites de ressources pour le container vault-agent afin de limiter l'empreinte énergétique globale du pod.
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['/']."]

### Agent 5 - Vérification finale
- Champs traités : ['namespace', 'components[search-api].image', 'components[search-api].replicas', 'components[search-api].ports', 'components[search-api].security_requirements', 'global_constraints[0]', 'unmapped_requirements[0]']
- ⚠️ Champs laissés ouverts : ["1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données'"]
- Actions :
  - yaml.safe_load_all OK sur 6 documents
  - Cross-reference check: Service selector matches Deployment labels
  - Cross-reference check: NetworkPolicy podSelector matches Deployment labels
  - Cross-reference check: Deployment serviceAccountName matches ServiceAccount name
  - Cross-reference check: Service targetPort matches Deployment containerPort
  - Sidecar check: vault-agent is correctly placed as a container in search-api pod (mode: manual_container)
  - Contrôle déterministe Python : OK
- Avertissements : ["L'opérateur ECK (Elastic Cloud on Kubernetes) doit être installé dans le cluster pour que la ressource 'Elasticsearch' soit traitée.", "L'injecteur Vault Agent doit être installé et configuré pour que les annotations 'vault.hashicorp.com' soient effectives."]

### Réparation ciblée (tentative 1/2)
- Champs traités : ["repair: Elasticsearch/elasticsearch -> nodeRoles: ['data']"]
- Actions :
  - [réparation #1] Elasticsearch/elasticsearch corrigé via agent2_template : nodeRoles: ['data'] — Ajout de 'node.roles': ['data'] dans la section config du nodeSet 'default' pour assigner explicitement le rôle de données aux nœuds.

### Agent 5 - Vérification finale
- Champs traités : ['namespace', 'components[0].image', 'components[0].replicas', 'components[0].ports', 'components[0].security_requirements', 'global_constraints[0]', 'unmapped_requirements[0]']
- ⚠️ Champs laissés ouverts : ["The specific requirement that the 3 Elasticsearch nodes must be 'data nodes' (nœuds de données) was handled as a best-effort requirement (unmapped_requirements) and remains marked as such for manual validation despite the presence of 'node.roles: [data]'.", "1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données'"]
- Actions :
  - yaml.safe_load_all OK sur 6 documents
  - Cross-reference: Service 'search-api' selector 'app: search-api' matches Deployment labels
  - Cross-reference: NetworkPolicy 'search-api-netpol' podSelector matches Deployment labels
  - Cross-reference: Deployment 'search-api' serviceAccountName matches ServiceAccount 'search-api-sa'
  - Cross-reference: Service targetPort 8080 matches Deployment containerPort 8080
  - Sidecar check: 'vault-agent' is present as a container in 'search-api' pod (mode: manual_container)
  - Resource types: CPU/Memory quantities (100m, 256Mi, etc.) are valid k8s formats
  - Contrôle déterministe Python : OK
- Avertissements : ["L'opérateur ECK (Elastic Cloud on Kubernetes) doit être installé dans le cluster pour que la ressource 'Elasticsearch' soit traitée.", "L'injecteur Vault Agent doit être installé et configuré pour que les annotations 'vault.hashicorp.com' soient effectives sur le cluster Elasticsearch."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | search | manifest (Namespace name=search) |
| components[0].image | myregistry/search:1.0 | manifest (Deployment search-api container search-api) |
| components[0].replicas | 2 | manifest (Deployment search-api spec.replicas) |
| components[0].ports[0] | 8080 TCP | manifest (Deployment containerPort 8080 / Service targetPort 8080) |
| components[0].security_requirements[0] | Exposition réseau uniquement interne | manifest (Service type: ClusterIP + NetworkPolicy search-api-netpol) |
| global_constraints[0] | authentification gérée via HashiCorp Vault | manifest (Deployment sidecar vault-agent + Elasticsearch annotations vault.hashicorp.com) |
| unmapped_requirements[0] | Cluster Elasticsearch ECK 3 nœuds de données | manifest (Elasticsearch resource count=3, node.roles=[data]) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (kind inconnu)

## 7. ⚠️ À vérifier / relancer si besoin

- 1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données'
- The specific requirement that the 3 Elasticsearch nodes must be 'data nodes' (nœuds de données) is not explicitly captured in the constraints or configuration, only the number of replicas is mentioned.
- The specific requirement that the 3 Elasticsearch nodes must be 'data nodes' (nœuds de données) was handled as a best-effort requirement (unmapped_requirements) and remains marked as such for manual validation despite the presence of 'node.roles: [data]'.
- unmapped_requirements: 1 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: Cluster Elasticsearch géré par l'opérateur ECK (Elastic Cloud on Kubernetes) avec 3 nœuds de données (suggested_kind=None)

## Métriques d'exécution

- Latence totale du run : **1049.578 s** (dont pipeline seul : 1049.578 s)
- Appels LLM : **15** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 1047.492 s (moyenne 69.833 s/appel)
- Tokens consommés : **58786** (46275 prompt + 12511 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 76.336 | 6471 |
| Agent 1 - Analyse (self-check) | 3 | 126.769 | 4367 |
| Agent 1 - Analyse (réparation) | 2 | 161.559 | 5596 |
| Agent 1 - Analyse (contraintes globales) | 1 | 30.607 | 1154 |
| Agent 1 - Analyse (réparation schéma) | 1 | 69.162 | 2998 |
| Agent 2 - Template | 1 | 75.783 | 7164 |
| Agent 2 - Template (best-effort) | 1 | 134.424 | 6418 |
| Agent 3 - Validation | 1 | 58.66 | 3664 |
| Agent 4 - Énergie | 1 | 63.323 | 4726 |
| Agent 5 - Vérification finale | 2 | 218.513 | 14928 |
| Réparation ciblée | 1 | 32.357 | 1300 |