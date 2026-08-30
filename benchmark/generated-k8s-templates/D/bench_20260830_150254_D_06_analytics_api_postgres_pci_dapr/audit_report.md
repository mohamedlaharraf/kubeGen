# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie une API d'analytics appelée "analytics-api", image myregistry/analytics:2.0, namespace "data", port 8080. Elle doit se connecter à une base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone). L'application doit aussi être conforme à la norme PCI-DSS niveau 1 (chiffrement au repos obligatoire pour tous les volumes, rotation des clés tous les 90 jours). Utilise aussi Dapr comme sidecar pour la communication pub/sub avec les autres services de l'entreprise.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `analytics-api` (Deployment), 1 sidecar(s): ['dapr'], dépend de: ['postgres-cluster']
- ⚠️ Dépendances vers des composants inexistants : ["'analytics-api' dépend de 'postgres-cluster', qui n'existe pas parmi les composants générés."]

## 2bis. Contraintes globales (blackboard)

Extraites séparément des composants par l'Agent 1, visibles par tout agent en aval qui filtre par portée — voir `schemas.GlobalConstraint` pour le mécanisme complet.

- **[all_components/compliance]** L'application doit être conforme à la norme PCI-DSS niveau 1
- **[all_volumes/compliance]** chiffrement au repos obligatoire pour tous les volumes
- **[all_components/compliance]** rotation des clés tous les 90 jours

## 2ter. Boucle de réparation

- Tentatives effectuées : **1** (borne : 1)
- ✔ Tous les gaps détectés ont été résolus.

- Auto-check réussi : **True**
- Tentatives de réparation internes : 2
- ⚠️ Exigences jamais couvertes : ['Opérateur CrunchyData', 'Base de données PostgreSQL (PostgresCluster, 3 instances, réplication synchrone)']
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].replicas` : Le nombre de réplicas pour l'API n'est pas précisé. → hypothèse retenue : *Valeur par défaut à 1* (confiance medium)
  - `components[0].sidecars[0].image` : L'image exacte de Dapr n'est pas fournie. → hypothèse retenue : *Utilisation de daprio/dapr:latest* (confiance medium)
  - `components[0].ingress` : L'utilisateur ne mentionne pas d'exposition externe (URL, Host). → hypothèse retenue : *Ingress désactivé, service interne uniquement* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[analytics-api]', 'global_constraints']
- ⚠️ Champs laissés ouverts : ['Opérateur CrunchyData', 'Base de données PostgreSQL (PostgresCluster, 3 instances, réplication synchrone)', 'unmapped_requirements: {\'requirement\': "L\'opérateur spécifique \'CrunchyData\' pour la base de données", \'suggested_kind\': \'operator\'} (suggested_kind=operator)', "unmapped_requirements: {'requirement': 'PostgresCluster avec 3 instances et réplication synchrone', 'suggested_kind': 'PostgresCluster'} (suggested_kind=PostgresCluster)"]
- Actions :
  - Extraction initiale + 2 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : 3 extraite(s) : ["L'application doit être conforme à la norme PCI-DSS niveau 1", 'chiffrement au repos obligatoire pour tous les volumes', 'rotation des clés tous les 90 jours']
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ["Le nombre de réplicas pour l'API n'est pas précisé.", "L'image exacte de Dapr n'est pas fournie.", "L'utilisateur ne mentionne pas d'exposition externe (URL, Host)."]

### Agent 2 - Template
- Champs traités : ['namespace', "[analytics-api] global_constraints: L'application doit être conforme à la norme PCI-DSS niveau 1", '[analytics-api] global_constraints: chiffrement au repos obligatoire pour tous les volumes', '[analytics-api] global_constraints: rotation des clés tous les 90 jours', '[analytics-api] component_name', '[analytics-api] workload_type', '[analytics-api] image', '[analytics-api] replicas', '[analytics-api] labels', '[analytics-api] ports', '[analytics-api] env_vars: aucun demandé', '[analytics-api] volumes: aucun demandé', '[analytics-api] sidecars', '[analytics-api] depends_on', '[analytics-api] security_requirements', '[analytics-api] observability_requirements: aucune', '[analytics-api] ingress: aucun', '[analytics-api] rbac', '[analytics-api] service_mesh_routing: aucun', '[analytics-api] observability_style', '[analytics-api] cron_schedule: non applicable', '[analytics-api] config_maps: aucune', '[analytics-api] network_policy: générée via security_requirements', '[analytics-api] deployment_strategy: aucune', '[analytics-api] namespace', '[analytics-api] sidecar_injection_mode', "[analytics-api] security_requirements: PCI-DSS: Implémentation d'un securityContext durci (non-root, read-only FS, drop capabilities)", '[analytics-api] security_requirements: PCI-DSS: Isolation réseau via NetworkPolicy (Ingress restreint au namespace, Egress restreint aux dépendances et DNS)', '[analytics-api] observability_requirements: Aucune exigence spécifique fournie', '[analytics-api] ingress: Aucun ingress demandé', '[analytics-api] rbac: Création du ServiceAccount dédié analytics-api-sa']
- ⚠️ Champs laissés ouverts : ['[analytics-api] PCI-DSS: Rotation des clés tous les 90 jours (nécessite un outil de gestion de secrets externe type Vault)', '[analytics-api] PCI-DSS: Chiffrement au repos (aucun volume PVC défini pour ce composant)', 'unmapped_requirements: 2 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'data' généré (une seule fois, déterministe)
  - [analytics-api] 3 contrainte(s) globale(s) du blackboard appliquée(s) : ["L'application doit être conforme à la norme PCI-DSS niveau 1", 'chiffrement au repos obligatoire pour tous les volumes', 'rotation des clés tous les 90 jours']
  - [analytics-api] Sidecar 'dapr' reconnu comme injection automatique (pattern déterministe, voir utils/sidecar_injection.py) : annotations ['dapr.io/enabled', 'dapr.io/app-id'] générées à la place d'un conteneur manuel.
  - Génération best-effort : 3 contrainte(s) globale(s) du blackboard transmise(s) (ex: chiffrement au repos sur tous les volumes) : ["L'application doit être conforme à la norme PCI-DSS niveau 1", 'chiffrement au repos obligatoire pour tous les volumes', 'rotation des clés tous les 90 jours']
  - Génération BEST-EFFORT (non vérifiée) pour 2 exigence(s) hors du schéma structuré : ['{\'requirement\': "L\'opérateur spécifique \'CrunchyData\' pour la base de données", \'suggested_kind\': \'operator\'}', "{'requirement': 'PostgresCluster avec 3 instances et réplication synchrone', 'suggested_kind': 'PostgresCluster'}"]
- Avertissements : ["[analytics-api] L'injection du sidecar 'dapr' est gérée via annotations conformément au mode 'annotations' spécifié (injection automatique déterministe).", "[analytics-api] NetworkPolicy générée en mode restrictif pour répondre à la norme PCI-DSS : l'egress est limité au composant 'postgres-cluster' et au DNS du cluster.", "[analytics-api] Sidecar 'dapr' en mode annotations : nécessite Dapr (https://dapr.io) installé dans le cluster cible."]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'replicas', 'image', 'ports', 'sidecars', 'rbac', 'security_requirements', 'volumes']
- Actions :
  - apiVersion présent
  - kind présent
  - metadata.name présent
  - Cohérence Deployment/Service selectors
  - ServiceAccount présent et assigné
  - Sidecar Dapr injecté via annotations (mode correct)
  - SecurityContext strict aligné PCI-DSS
  - NetworkPolicy cohérente avec le flux
  - Indentation YAML valide
- Avertissements : ["La contrainte globale 'rotation des clés tous les 90 jours' n'est pas explicitement configurable via les ressources Kubernetes standards fournies et doit être gérée par la politique de gestion des secrets."]

### Agent 4 - Débat multi-agents (Énergie)
- Champs traités : ['[analytics-api] resources', '[analytics-api] affinity', '[analytics-api] nodeSelector', '[analytics-api] replicas', '[analytics-api] hpa', '[analytics-api] probes']
- Actions :
  - [analytics-api] Débat conclu : 1 tour(s) de critique, 5 conflit(s) réel(s) relevé(s), scores {'consolidation': 9.0, 'sizing': 9.0, 'autoscaling': 10.0}.
  - [analytics-api] Éléments retenus par stratégie : {'resources': 'sizing', 'probes': 'sizing', 'nodeSelector': 'consolidation', 'affinity': 'consolidation', 'replicas': 'autoscaling', 'hpa': 'autoscaling'}
  - [analytics-api] The final manifest is a fusion of the three strategies, prioritizing High Availability (HA) and stability as required by the 'critical' nature of the analytics API. 1) Replicas: The conflict between 1 and 2 replicas was resolved in favor of 2 (Autoscaling/Consolidation) to eliminate the Single Point of Failure (SPOF). 2) Resources: Sizing's resource requests (200m/256Mi) were retained over Consolidation's lower estimates to prevent CPU throttling and OOMKills, which is critical for stability and a prerequisite for the HPA to function correctly. 3) Placement: Consolidation's nodeSelector (shared pool) and preferred podAffinity were kept. The 'preferred' mode was specifically chosen over 'required' to ensure that the HPA can still scale pods to other nodes if the preferred host is saturated, balancing energy density with availability. 4) Scaling: The HPA from the Autoscaling strategy was integrated to handle traffic bursts. 5) Probes: TCP probes from Sizing were adopted to minimize overhead. Security contexts from the original YAML were preserved to maintain PCI-DSS compliance.
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['/']."]

### Agent 5 - Vérification finale
- Champs traités : ['namespace: data', 'namespace: prod-db', 'component: analytics-api', 'component: postgres-cluster', 'security_requirements: PCI-DSS', 'global_constraints: encryption_at_rest', 'sidecar: dapr (annotations)']
- ⚠️ Champs laissés ouverts : ['global_constraints[2]: rotation des clés tous les 90 jours (non implémentable via YAML Kubernetes standard, nécessite un gestionnaire de secrets externe type Vault)', '2 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : \'{\'requirement\': "L\'opérateur spécifique \'CrunchyData\' pour la base de données", \'suggested_kind\': \'operator\'}\' (kind supposé: operator); \'{\'requirement\': \'PostgresCluster avec 3 instances et réplication synchrone\', \'suggested_kind\': \'PostgresCluster\'}\' (kind supposé: PostgresCluster)']
- Actions :
  - yaml.safe_load_all OK sur 13 documents
  - Cross-references validated: HPA -> Deployment (analytics-api) OK
  - Cross-references validated: Service -> Deployment (analytics-api) OK
  - Cross-references validated: RoleBinding -> ServiceAccount (postgres-cluster-sa) OK
  - Sidecar Dapr: mode 'annotations' verified, no manual container present
  - Corrigé: Added missing 'namespace: prod-db' to all postgres-cluster resources for consistency with RoleBinding
  - Corrigé: Added 'Namespace' resource for 'prod-db'
  - Corrigé: Updated 'analytics-api-netpol' egress to include 'namespaceSelector' for 'prod-db' to allow cross-namespace communication with the database
  - Contrôle déterministe Python : OK
- Avertissements : ["app.kubernetes.io/version='unknown' for postgres-cluster resources: image tag should be specified before production deployment", "StorageClass 'pci-encrypted' is assumed to exist in the target cluster"]

### Réparation ciblée (tentative 1/2)
- Champs traités : ['repair: Deployment/crunchydata-operator -> resources.requests and resources.limits']
- Actions :
  - [réparation #1] Deployment/crunchydata-operator corrigé via agent4_debate : resources.requests and resources.limits — Ajout des ressources (requests et limits) pour le conteneur 'operator' afin de passer d'un profil best-effort à un dimensionnement optimisé et borné.

### Agent 5 - Vérification finale
- Champs traités : ['namespace: data', 'namespace: prod-db', 'component: analytics-api', 'component: postgres-cluster', 'global_constraints: PCI-DSS', 'global_constraints: encryption_at_rest', 'sidecar: dapr']
- ⚠️ Champs laissés ouverts : ['global_constraints[2]: rotation des clés tous les 90 jours (non implémentable via YAML Kubernetes standard, nécessite un gestionnaire de secrets externe type Vault)', "BEST-EFFORT: L'opérateur CrunchyData et le PostgresCluster sont implémentés hors schéma structuré initial, validation manuelle requise", '2 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : \'{\'requirement\': "L\'opérateur spécifique \'CrunchyData\' pour la base de données", \'suggested_kind\': \'operator\'}\' (kind supposé: operator); \'{\'requirement\': \'PostgresCluster avec 3 instances et réplication synchrone\', \'suggested_kind\': \'PostgresCluster\'}\' (kind supposé: PostgresCluster)']
- Actions :
  - yaml.safe_load_all OK sur 13 documents
  - Validation des types de ressources k8s (CPU/Memory) OK
  - Vérification croisée HPA -> Deployment (analytics-api) OK
  - Vérification croisée Service -> Deployment (analytics-api) OK
  - Vérification croisée RoleBinding -> ServiceAccount (postgres-cluster-sa) OK
  - Vérification croisée NetworkPolicy -> Namespace (prod-db) OK
  - Vérification mode sidecar Dapr (annotations) OK : annotations présentes, aucun conteneur manuel
  - Contrôle déterministe Python : OK
- Avertissements : ["app.kubernetes.io/version='unknown' pour les ressources postgres-cluster : le tag d'image doit être spécifié avant production", "StorageClass 'pci-encrypted' est supposée exister dans le cluster cible"]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| global_constraints[0] | PCI-DSS niveau 1 | manifest (Deployment/analytics-api securityContext, Deployment/crunchydata-operator securityContext, NetworkPolicies) |
| global_constraints[1] | chiffrement au repos | manifest (PostgresCluster storageClassName=pci-encrypted) |
| components[0].sidecars[0] | Dapr pub/sub | manifest (Deployment/analytics-api annotations dapr.io/*) |
| unmapped_requirements[0] | Opérateur CrunchyData | manifest (Deployment/crunchydata-operator) |
| unmapped_requirements[1] | PostgresCluster 3 instances synchrone | manifest (PostgresCluster/postgres-cluster) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- {'requirement': "L'opérateur spécifique 'CrunchyData' pour la base de données", 'suggested_kind': 'operator'} (kind supposé : `operator`)
- {'requirement': 'PostgresCluster avec 3 instances et réplication synchrone', 'suggested_kind': 'PostgresCluster'} (kind supposé : `PostgresCluster`)

## 7. ⚠️ À vérifier / relancer si besoin

- 2 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : '{'requirement': "L'opérateur spécifique 'CrunchyData' pour la base de données", 'suggested_kind': 'operator'}' (kind supposé: operator); '{'requirement': 'PostgresCluster avec 3 instances et réplication synchrone', 'suggested_kind': 'PostgresCluster'}' (kind supposé: PostgresCluster)
- BEST-EFFORT: L'opérateur CrunchyData et le PostgresCluster sont implémentés hors schéma structuré initial, validation manuelle requise
- Base de données PostgreSQL (PostgresCluster, 3 instances, réplication synchrone)
- Opérateur CrunchyData
- [analytics-api] PCI-DSS: Chiffrement au repos (aucun volume PVC défini pour ce composant)
- [analytics-api] PCI-DSS: Rotation des clés tous les 90 jours (nécessite un outil de gestion de secrets externe type Vault)
- global_constraints[2]: rotation des clés tous les 90 jours (non implémentable via YAML Kubernetes standard, nécessite un gestionnaire de secrets externe type Vault)
- unmapped_requirements: 2 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 2 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: {'requirement': "L'opérateur spécifique 'CrunchyData' pour la base de données", 'suggested_kind': 'operator'} (suggested_kind=operator)
- unmapped_requirements: {'requirement': 'PostgresCluster avec 3 instances et réplication synchrone', 'suggested_kind': 'PostgresCluster'} (suggested_kind=PostgresCluster)

## Métriques d'exécution

- Latence totale du run : **1516.374 s** (dont pipeline seul : 1516.374 s)
- Appels LLM : **21** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 1794.823 s (moyenne 85.468 s/appel)
- Tokens consommés : **109732** (80609 prompt + 29123 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 69.438 | 6628 |
| Agent 1 - Analyse (self-check) | 3 | 154.848 | 4574 |
| Agent 1 - Analyse (réparation) | 2 | 220.98 | 5829 |
| Agent 1 - Analyse (contraintes globales) | 1 | 29.969 | 1274 |
| Agent 1 - Analyse (réparation schéma) | 1 | 68.402 | 3171 |
| Agent 2 - Template | 1 | 110.959 | 8459 |
| Agent 2 - Template (best-effort) | 1 | 160.242 | 8590 |
| Agent 3 - Validation | 1 | 71.771 | 4579 |
| Agent4-Debate-Strategy-sizing | 1 | 67.385 | 3570 |
| Agent4-Debate-Strategy-consolidation | 1 | 68.46 | 3607 |
| Agent4-Debate-Strategy-autoscaling | 1 | 89.063 | 3978 |
| Agent4-Debate-Strategy-consolidation-Critique | 1 | 71.697 | 7039 |
| Agent4-Debate-Strategy-sizing-Critique | 1 | 73.154 | 6983 |
| Agent4-Debate-Strategy-autoscaling-Critique | 1 | 90.26 | 7713 |
| Agent4-Debate-Judge | 1 | 83.917 | 8484 |
| Agent 5 - Vérification finale | 2 | 334.963 | 23517 |
| Réparation ciblée | 1 | 29.316 | 1737 |