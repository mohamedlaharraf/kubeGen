# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie une API d'analytics appelée "analytics-api", image myregistry/analytics:2.0, namespace "data", port 8080. Elle doit se connecter à une base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone). L'application doit aussi être conforme à la norme PCI-DSS niveau 1 (chiffrement au repos obligatoire pour tous les volumes, rotation des clés tous les 90 jours). Utilise aussi Dapr comme sidecar pour la communication pub/sub avec les autres services de l'entreprise.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `analytics-api` (Deployment), 1 sidecar(s): ['dapr'], dépend de: ['postgres-db']
- ⚠️ Dépendances vers des composants inexistants : ["'analytics-api' dépend de 'postgres-db', qui n'existe pas parmi les composants générés."]

## 2bis. Contraintes globales (blackboard)

Extraites séparément des composants par l'Agent 1, visibles par tout agent en aval qui filtre par portée — voir `schemas.GlobalConstraint` pour le mécanisme complet.

- **[all_components/compliance]** Conformité à la norme PCI-DSS niveau 1
- **[all_volumes/compliance]** Chiffrement au repos obligatoire pour tous les volumes
- **[all_components/compliance]** Rotation des clés tous les 90 jours

- Auto-check réussi : **True**
- Tentatives de réparation internes : 2
- ⚠️ Exigences jamais couvertes : ['Base de données CrunchyData PostgreSQL (PostgresCluster, 3 instances, réplication synchrone)']
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].replicas` : Le nombre de réplicas pour l'API n'est pas spécifié. → hypothèse retenue : *Valeur par défaut à 1* (confiance medium)
  - `components[0].sidecars[0].image` : L'image exacte pour le sidecar Dapr n'est pas fournie. → hypothèse retenue : *Utilisation de l'image standard 'daprio/dapr:latest'* (confiance high)
  - `components[0].ingress` : L'utilisateur ne mentionne pas d'exposition externe (domaine, HTTPS), seulement un port 8080. → hypothèse retenue : *Ingress désactivé, exposition via Service interne uniquement* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[analytics-api]', 'global_constraints']
- ⚠️ Champs laissés ouverts : ['Base de données CrunchyData PostgreSQL (PostgresCluster, 3 instances, réplication synchrone)', "unmapped_requirements: Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone) (suggested_kind=None)"]
- Actions :
  - Extraction initiale + 2 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : 3 extraite(s) : ['Conformité à la norme PCI-DSS niveau 1', 'Chiffrement au repos obligatoire pour tous les volumes', 'Rotation des clés tous les 90 jours']
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ["Le nombre de réplicas pour l'API n'est pas spécifié.", "L'image exacte pour le sidecar Dapr n'est pas fournie.", "L'utilisateur ne mentionne pas d'exposition externe (domaine, HTTPS), seulement un port 8080."]

### Agent 2 - Template
- Champs traités : ['namespace', '[analytics-api] global_constraints: Conformité à la norme PCI-DSS niveau 1', '[analytics-api] global_constraints: Chiffrement au repos obligatoire pour tous les volumes', '[analytics-api] global_constraints: Rotation des clés tous les 90 jours', '[analytics-api] component_name', '[analytics-api] workload_type', '[analytics-api] image', '[analytics-api] replicas', '[analytics-api] ports: expose_service=true traduit en Service ClusterIP', '[analytics-api] env_vars: aucun', '[analytics-api] volumes: aucun', '[analytics-api] sidecars: dapr traité via sidecar_injection_mode', "[analytics-api] sidecar_injection_mode: mode 'annotations' appliqué", '[analytics-api] security_requirements: PCI-DSS traduit en hardening et NetworkPolicy', '[analytics-api] observability_requirements: aucun', '[analytics-api] ingress: aucun', '[analytics-api] rbac: enabled=false, seul ServiceAccount créé', '[analytics-api] service_mesh_routing: aucun', '[analytics-api] observability_style: annotations (aucune métrique spécifique demandée)', '[analytics-api] cron_schedule: non applicable', '[analytics-api] config_maps: aucun', '[analytics-api] network_policy: générée pour isolation PCI-DSS', '[analytics-api] deployment_strategy: aucun', '[analytics-api] namespace', "[analytics-api] security_requirements: Conformité PCI-DSS niveau 1 : Implémentation d'un securityContext durci (non-root, readOnlyRootFilesystem, drop capabilities)", "[analytics-api] security_requirements: Isolation réseau : Service en ClusterIP et NetworkPolicy restreignant l'accès au namespace", '[analytics-api] observability_requirements: Aucune exigence spécifique fournie', '[analytics-api] ingress: Aucun ingress demandé', '[analytics-api] rbac: Création du ServiceAccount analytics-api-sa']
- ⚠️ Champs laissés ouverts : ['[analytics-api] Rotation des clés tous les 90 jours : Cette contrainte infrastructurelle ne peut être implémentée dans un manifeste Kubernetes et doit être gérée par un secret manager (ex: HashiCorp Vault, AWS Secrets Manager)', 'unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'data' généré (une seule fois, déterministe)
  - [analytics-api] 3 contrainte(s) globale(s) du blackboard appliquée(s) : ['Conformité à la norme PCI-DSS niveau 1', 'Chiffrement au repos obligatoire pour tous les volumes', 'Rotation des clés tous les 90 jours']
  - [analytics-api] Sidecar 'dapr' reconnu comme injection automatique (pattern déterministe, voir utils/sidecar_injection.py) : annotations ['dapr.io/enabled', 'dapr.io/app-id'] générées à la place d'un conteneur manuel.
  - Génération best-effort : 3 contrainte(s) globale(s) du blackboard transmise(s) (ex: chiffrement au repos sur tous les volumes) : ['Conformité à la norme PCI-DSS niveau 1', 'Chiffrement au repos obligatoire pour tous les volumes', 'Rotation des clés tous les 90 jours']
  - Génération BEST-EFFORT (non vérifiée) pour 1 exigence(s) hors du schéma structuré : ["Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone)"]
- Avertissements : ["[analytics-api] L'injection du sidecar Dapr est configurée via annotations ; cela nécessite que l'opérateur Dapr soit installé et actif dans le cluster.", "[analytics-api] Le champ readOnlyRootFilesystem est activé pour PCI-DSS. Si l'application nécessite d'écrire des fichiers temporaires, un volume emptyDir devra être ajouté par l'Agent 4 ou l'utilisateur.", '[analytics-api] La rotation des clés tous les 90 jours est notée mais non implémentable via YAML Kubernetes standard.', "[analytics-api] Sidecar 'dapr' en mode annotations : nécessite Dapr (https://dapr.io) installé dans le cluster cible."]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'replicas', 'image', 'ports', 'sidecars', 'rbac', 'volumes', 'security_requirements']
- Actions :
  - apiVersion présent
  - kind présent
  - metadata.name présent
  - Cohérence Deployment/Service (selectors/labels)
  - ServiceAccount présent malgré rbac.enabled=false
  - Sidecar dapr injecté via annotations (mode correct)
  - Absence de conteneur manuel pour sidecar en mode annotations
  - SecurityContext Pod et Conteneur présents et stricts
  - NetworkPolicy alignée sur le workload
- Avertissements : ['Rotation des clés tous les 90 jours']

### Agent 4 - Énergie
- Champs traités : ['[analytics-api] energy_goals', '[analytics-api] resource_hints', '[analytics-api] traffic_windows', '[analytics-api] constraints', '[analytics-api] workload_type', '[analytics-api] replicas']
- Actions :
  - [analytics-api] 3 contrainte(s) globale(s) du blackboard prise(s) en compte pour l'optimisation énergie : ['Conformité à la norme PCI-DSS niveau 1', 'Chiffrement au repos obligatoire pour tous les volumes', 'Rotation des clés tous les 90 jours']
  - [analytics-api] Dimensionnement des ressources (requests/limits) avec une marge de sécurité modérée car l'application_context définit le service comme 'critique', malgré l'absence de resource_hints.
  - [analytics-api] Augmentation du nombre de replicas à 2 et ajout d'un HPA (min 2, max 5) : justifié par la criticité du service mentionnée dans l'application_context, nécessitant une haute disponibilité et une capacité de montée en charge.
  - [analytics-api] Ajout d'un PodDisruptionBudget (minAvailable: 1) car le service est critique et dispose de plusieurs réplicas, assurant la continuité de service lors des opérations de maintenance du cluster.
  - [analytics-api] Ajout de livenessProbe et readinessProbe via tcpSocket sur le port 8080 pour optimiser l'utilisation des ressources en éliminant les pods zombies ou non prêts.
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['/']."]

### Agent 5 - Vérification finale
- Champs traités : ['architecture_type', 'namespace', 'components[0].component_name', 'components[0].image', 'components[0].ports', 'components[0].sidecars', 'unmapped_requirements[0]', 'global_constraints[0]', 'global_constraints[1]']
- ⚠️ Champs laissés ouverts : ['global_constraints[2] (Rotation des clés tous les 90 jours) : Exigence de conformité organisationnelle/infrastructurelle non implémentable via manifeste Kubernetes statique.', "1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone)'"]
- Actions :
  - yaml.safe_load_all OK sur 11 documents
  - Vérification des types k8s (CPU/Memory) OK
  - Cohérence HPA -> Deployment (analytics-api) OK
  - Cohérence Service -> Deployment (labels app: analytics-api) OK
  - Cohérence PDB -> Deployment (labels app: analytics-api) OK
  - Vérification sidecar Dapr : mode 'annotations' respecté (présence annotations, absence de conteneur manuel) OK
  - Contrôle déterministe Python : OK
- Avertissements : ["L'injection du sidecar Dapr nécessite l'installation préalable de l'opérateur Dapr dans le cluster.", "Le chiffrement au repos dépend de la configuration réelle de la StorageClass 'encrypted-storage' sur le cloud provider.", 'La rotation des clés doit être gérée par un outil externe (ex: Vault, AWS KMS).']

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| components[0].component_name | analytics-api | manifest (Deployment/analytics-api) |
| components[0].image | myregistry/analytics:2.0 | manifest (Deployment/analytics-api) |
| components[0].ports[0] | 8080 | manifest (Service/analytics-api, Deployment/analytics-api) |
| components[0].sidecars[0] | dapr | manifest (Deployment/analytics-api annotations) |
| unmapped_requirements[0] | CrunchyData PostgreSQL (3 instances, sync) | manifest (PostgresCluster/postgres-db) |
| global_constraints[0] | PCI-DSS niveau 1 | manifest (NetworkPolicy analytics-api-netpol, postgres-db-netpol, Deployment securityContext) |
| global_constraints[1] | Chiffrement au repos | manifest (PostgresCluster/postgres-db storageClassName: encrypted-storage) |
| global_constraints[2] | Rotation des clés 90j | AgentReport (Agent 2) : identifié comme non-implémentable via YAML |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone) (kind inconnu)

## 7. ⚠️ À vérifier / relancer si besoin

- 1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone)'
- Base de données CrunchyData PostgreSQL (PostgresCluster, 3 instances, réplication synchrone)
- [analytics-api] Rotation des clés tous les 90 jours : Cette contrainte infrastructurelle ne peut être implémentée dans un manifeste Kubernetes et doit être gérée par un secret manager (ex: HashiCorp Vault, AWS Secrets Manager)
- global_constraints[2] (Rotation des clés tous les 90 jours) : Exigence de conformité organisationnelle/infrastructurelle non implémentable via manifeste Kubernetes statique.
- unmapped_requirements: 1 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone) (suggested_kind=None)

## Métriques d'exécution

- Latence totale du run : **805.672 s** (dont pipeline seul : 805.672 s)
- Appels LLM : **13** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 803.568 s (moyenne 61.813 s/appel)
- Tokens consommés : **52050** (40573 prompt + 11477 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 64.327 | 6637 |
| Agent 1 - Analyse (self-check) | 3 | 76.671 | 4564 |
| Agent 1 - Analyse (réparation) | 2 | 158.314 | 5767 |
| Agent 1 - Analyse (contraintes globales) | 1 | 27.959 | 1271 |
| Agent 1 - Analyse (réparation schéma) | 1 | 68.203 | 3112 |
| Agent 2 - Template | 1 | 83.543 | 7149 |
| Agent 2 - Template (best-effort) | 1 | 96.86 | 6668 |
| Agent 3 - Validation | 1 | 63.355 | 3651 |
| Agent 4 - Énergie | 1 | 65.513 | 4834 |
| Agent 5 - Vérification finale | 1 | 98.823 | 8397 |