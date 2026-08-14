# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie une API d'analytics appelée "analytics-api", image myregistry/analytics:2.0, namespace "data", port 8080. Elle doit se connecter à une base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone). L'application doit aussi être conforme à la norme PCI-DSS niveau 1 (chiffrement au repos obligatoire pour tous les volumes, rotation des clés tous les 90 jours). Utilise aussi Dapr comme sidecar pour la communication pub/sub avec les autres services de l'entreprise.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `analytics-api` (Deployment), 1 sidecar(s): ['dapr-sidecar']

## 2bis. Contraintes globales (blackboard)

Extraites séparément des composants par l'Agent 1, visibles par tout agent en aval qui filtre par portée — voir `schemas.GlobalConstraint` pour le mécanisme complet.

- **[all_components/compliance]** Conformité à la norme PCI-DSS niveau 1
- **[all_volumes/compliance]** Chiffrement au repos obligatoire pour tous les volumes
- **[all_components/security]** Rotation des clés tous les 90 jours

## 2ter. Boucle de réparation

- Tentatives effectuées : **1** (borne : 1)
- ✔ Tous les gaps détectés ont été résolus.

- Auto-check réussi : **True**
- Tentatives de réparation internes : 0
- ⚠️ Exigences jamais couvertes : ["Se connecter à une base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone)"]
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].sidecars[0].image` : Quelle image/tag exact utiliser pour le sidecar Dapr ? → hypothèse retenue : *Utilisation de l'image standard daprio/daprd:1.12.0* (confiance medium)
  - `components[0].replicas` : Combien de réplicas pour le déploiement analytics-api ? → hypothèse retenue : *1 réplica par défaut* (confiance low)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[analytics-api]', 'global_constraints']
- ⚠️ Champs laissés ouverts : ["Se connecter à une base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone)", "unmapped_requirements: Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone) (suggested_kind=PostgresCluster)"]
- Actions :
  - Extraction initiale + 0 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : 3 extraite(s) : ['Conformité à la norme PCI-DSS niveau 1', 'Chiffrement au repos obligatoire pour tous les volumes', 'Rotation des clés tous les 90 jours']
- Avertissements : ['Quelle image/tag exact utiliser pour le sidecar Dapr ?', 'Combien de réplicas pour le déploiement analytics-api ?']

### Agent 2 - Template
- Champs traités : ['namespace', '[analytics-api] global_constraints: Conformité à la norme PCI-DSS niveau 1', '[analytics-api] global_constraints: Chiffrement au repos obligatoire pour tous les volumes', '[analytics-api] global_constraints: Rotation des clés tous les 90 jours', "[analytics-api] component_name: utilisé comme metadata.name ('analytics-api')", '[analytics-api] workload_type: Deployment généré', "[analytics-api] image: 'myregistry/analytics:2.0'", '[analytics-api] replicas: 1', '[analytics-api] labels: app=analytics-api', '[analytics-api] ports: port 8080 TCP exposé sur le conteneur et dans le Service ClusterIP', '[analytics-api] env_vars: aucun demandé, aucune variable générée', '[analytics-api] volumes: aucun demandé, aucun volume ni PVC généré', "[analytics-api] sidecars: traité en mode annotations ('dapr.io/enabled', 'dapr.io/app-id') pour 'dapr-sidecar'", '[analytics-api] depends_on: aucun demandé', "[analytics-api] namespace: 'data'", "[analytics-api] rbac: désactivé (enabled=False), ServiceAccount dédié 'analytics-api-sa' créé sans rôles supplémentaires", '[analytics-api] ingress: aucun demandé', '[analytics-api] cron_schedule: non applicable pour un Deployment', '[analytics-api] config_maps: aucun demandé', '[analytics-api] network_policy: aucun demandé', '[analytics-api] deployment_strategy: aucun demandé', '[analytics-api] security_requirements: Hardening de base appliqué sur le Pod et le conteneur (runAsNonRoot, readOnlyRootFilesystem, allowPrivilegeEscalation=false, capabilities.drop=ALL, seccompProfile=RuntimeDefault)', "[analytics-api] security_requirements: Isolation du composant via un ServiceAccount dédié ('analytics-api-sa') sans privilèges superflus", '[analytics-api] security_requirements: Exposition restreinte au cluster uniquement via Service de type ClusterIP', '[analytics-api] observability_requirements: observability_requirements: aucune exigence explicite dans la liste du composant', '[analytics-api] ingress: ingress: non configuré (ingress=None)', "[analytics-api] rbac: rbac: ServiceAccount dédié 'analytics-api-sa' créé selon le principe du moindre privilège, aucun Role/RoleBinding nécessaire"]
- ⚠️ Champs laissés ouverts : ["admission_policies: Exiger le chiffrement au repos pour tous les volumes (PCI-DSS niveau 1) : pattern non reconnu, aucune policy générée automatiquement (évite le risque d'une règle de sécurité mal traduite) — à écrire manuellement.", "[analytics-api] resources.requests/limits: laissé pour l'Agent 4", "[analytics-api] hpa: laissé pour l'Agent 4", '[analytics-api] Conformité PCI-DSS niveau 1: requiert un ensemble de contrôles infrastructure, audit logs, SIEM, gestion des vulnérabilités et règles de réseau hors du scope du template k8s de base', "[analytics-api] Chiffrement au repos obligatoire pour tous les volumes: aucun volume n'est attaché à ce composant, le chiffrement des disques sous-jacents relève de la configuration infra/StorageClass", '[analytics-api] Rotation des clés tous les 90 jours: nécessite un gestionnaire de secrets externe (ex: Vault, External Secrets Operator) et un processus opérationnel dédié', 'unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'data' généré (une seule fois, déterministe)
  - Policies d'admission (Kyverno, mode Audit) : 0 générée(s) déterministiquement (pattern matching, pas de LLM sur ce domaine sensible)
  - [analytics-api] 3 contrainte(s) globale(s) du blackboard appliquée(s) : ['Conformité à la norme PCI-DSS niveau 1', 'Chiffrement au repos obligatoire pour tous les volumes', 'Rotation des clés tous les 90 jours']
  - [analytics-api] Sidecar 'dapr-sidecar' reconnu comme injection automatique (pattern déterministe, voir utils/sidecar_injection.py) : annotations ['dapr.io/enabled', 'dapr.io/app-id'] générées à la place d'un conteneur manuel.
  - Génération best-effort : 3 contrainte(s) globale(s) du blackboard transmise(s) (ex: chiffrement au repos sur tous les volumes) : ['Conformité à la norme PCI-DSS niveau 1', 'Chiffrement au repos obligatoire pour tous les volumes', 'Rotation des clés tous les 90 jours']
  - Génération BEST-EFFORT (non vérifiée) pour 1 exigence(s) hors du schéma structuré : ["Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone)"]
- Avertissements : ["[analytics-api] L'injection du sidecar 'dapr-sidecar' est configurée via des annotations pod ('dapr.io/enabled', 'dapr.io/app-id') conformément aux instructions. Cela nécessite que l'opérateur Dapr soit préalablement installé et actif sur le cluster.", "[analytics-api] Le système de fichiers racine du conteneur est configuré en lecture seule (readOnlyRootFilesystem: true). Veuillez vérifier que l'application 'analytics-api' n'a pas besoin d'écrire dans des répertoires locaux (/tmp ou répertoires de logs). Si des écritures temporaires sont nécessaires, un volume emptyDir devra être ajouté.", "[analytics-api] Sidecar 'dapr-sidecar' en mode annotations : nécessite Dapr (https://dapr.io) installé dans le cluster cible."]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'architecture_type', 'components', 'component_name', 'workload_type', 'image', 'replicas', 'labels', 'ports', 'env_vars', 'volumes', 'sidecars', 'security_requirements', 'ingress', 'rbac', 'observability_style', 'cron_schedule', 'global_constraints']
- Actions :
  - Structure du manifeste YAML valide et document multidoc correctement séparé
  - Présence des champs obligatoires (apiVersion, kind, metadata, spec)
  - Nommage et namespace cohérents ('data') sur toutes les ressources
  - ServiceAccount 'analytics-api-sa' conservé et correctement référencé dans le Deployment
  - Alignement des selectors Service et matchLabels Deployment avec les labels du pod ('app: analytics-api')
  - Sidecar Dapr vérifié en mode 'annotations' (annotations dapr.io/enabled et dapr.io/app-id présentes, aucun conteneur manuel superflus)
  - Conteneur principal 'analytics-api' configuré avec image, ports et securityContext adaptés
  - Service 'analytics-api' exposant le port targetPort 8080
- Avertissements : ['Contrainte globale hors périmètre direct de la spec K8s : Conformité à la norme PCI-DSS niveau 1', 'Contrainte globale non matérialisée par un PV/PVC : Chiffrement au repos obligatoire pour tous les volumes', 'Contrainte globale hors périmètre direct de la spec K8s : Rotation des clés tous les 90 jours']

### Agent 4 - Énergie
- Champs traités : ['[analytics-api] workload_type', '[analytics-api] replicas', '[analytics-api] resource_hints', '[analytics-api] energy_goals', '[analytics-api] traffic_windows', '[analytics-api] constraints']
- Actions :
  - [analytics-api] 3 contrainte(s) globale(s) du blackboard prise(s) en compte pour l'optimisation énergie : ['Conformité à la norme PCI-DSS niveau 1', 'Chiffrement au repos obligatoire pour tous les volumes', 'Rotation des clés tous les 90 jours']
  - [analytics-api] Dimensionnement des ressources CPU et mémoire (requests: 100m/128Mi, limits: 500m/256Mi) pour le conteneur analytics-api, calibré de manière sobre en l'absence de hanteurs/indicateurs de charge spécifique.
  - [analytics-api] Ajout de readinessProbe et livenessProbe basées sur tcpSocket sur le port 8080 pour garantir le recyclage des pods non fonctionnels et éviter le gaspillage de ressources.
  - [analytics-api] Pas de HPA généré : aucun besoin de scaling n'est spécifié dans energy_goals ou traffic_windows, et aucun profil de variation de charge n'indique un besoin d'autoscaling.
  - [analytics-api] Pas de PodDisruptionBudget généré car replicas est égal à 1 et aucun besoin d'haute disponibilité critique n'est spécifié.
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['/']."]

### Agent 5 - Vérification finale
- Champs traités : ['Validation syntaxique multi-document YAML', "Validation du mode d'injection sidecar (Dapr en annotations)", 'Audit de traçabilité NormalizedSpec -> Manifeste K8s', "Contrôle d'application des global_constraints sur toutes les ressources du périmètre", 'Vérification des références croisées Service / Deployment / ServiceAccount']
- ⚠️ Champs laissés ouverts : ["global_constraints[2] ('Rotation des clés tous les 90 jours') : ne peut pas être configurée de manière statique dans des manifestes Kubernetes basiques et nécessite un gestionnaire de secrets externe (ex: HashiCorp Vault, External Secrets Operator).", "unmapped_requirements[0] ('PostgresCluster') : ressource issue d'un fragment best-effort non validé par le schéma OpenAPI strict, à valider manuellement avant tout déploiement.", "1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone)' (kind supposé: PostgresCluster)"]
- Actions :
  - yaml.safe_load_all OK sur 7 documents K8s (Namespace, ServiceAccount, Deployment, Service, PostgresCluster, ServiceAccount, NetworkPolicy)
  - Contrôle de validation des types et des quantités K8s OK (100m, 500m, 128Mi, 256Mi, 20Gi)
  - Cohérence des références croisées OK : Service selector 'app: analytics-api' matche Deployment matchLabels/template labels
  - Validation du sidecar dapr-sidecar OK : mode 'annotations' confirmé (dapr.io/enabled: true, dapr.io/app-id: analytics-api), aucun conteneur manuel superflus
  - Vérification d'absence de collision de nommage ou de sélecteur inter-composants
  - Corrigé: Harmonisation du namespace : ajout explicite de 'namespace: data' sur les ressources PostgresCluster, postgres-cluster-sa et postgres-cluster-netpol issues du fragment unmapped
  - Contrôle déterministe Python : OK
- Avertissements : ["Le manifeste PostgresCluster requiert la présence de l'opérateur CrunchyData PGO (v5+) préinstallé dans le cluster.", "L'injection effective du sidecar Dapr nécessite que le Runtime Dapr soit installé dans le cluster."]

### Réparation ciblée (tentative 1/2)
- Champs traités : ['repair: PostgresCluster/postgres-cluster -> Expliciter une configuration de StorageClass chiffrée (ex: storageClassName: encrypted-sc) sur dataVolumeClaimSpec et pgbackrest volume.volumeClaimSpec pour satisfaire le chiffrement au repos.']
- Actions :
  - [réparation #1] PostgresCluster/postgres-cluster corrigé via agent2_template : Expliciter une configuration de StorageClass chiffrée (ex: storageClassName: encrypted-sc) sur dataVolumeClaimSpec et pgbackrest volume.volumeClaimSpec pour satisfaire le chiffrement au repos. — Ajout du champ storageClassName: encrypted-sc dans dataVolumeClaimSpec et pgbackrest volume.volumeClaimSpec afin d'assurer le chiffrement au repos des volumes.

### Agent 5 - Vérification finale
- Champs traités : ['Validation syntaxique globale multi-documents', "Verification du mode d'injection sidecar Dapr (annotations)", 'Audit de tracabilite NormalizedSpec -> Manifeste K8s', "Controle des global_constraints sur l'ensemble des ressources (y compris unmapped_requirements)", 'Verification des references croisees et namespaces']
- ⚠️ Champs laissés ouverts : ["global_constraints[2] ('Rotation des clés tous les 90 jours') : exige un composant externe de gestion de clés/secrets (ex: HashiCorp Vault, External Secrets Operator, AWS KMS) et un processus operationnel, non configurables de façon statique dans un manifeste K8s natif.", "unmapped_requirements[0] ('PostgresCluster avec 3 instances et réplication synchrone') : ressource générée en mode BEST-EFFORT par l'Agent 2 hors du schéma structuré strict, requérant la présence de l'opérateur CrunchyData PGO dans le cluster.", "admission_policies ('Exiger le chiffrement au repos pour tous les volumes') : aucune règle Kyverno/OPA générée automatiquement afin d'éviter une mauvaise interprétation de politique de sécurité sensible.", "1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone)' (kind supposé: PostgresCluster)"]
- Actions :
  - yaml.safe_load_all OK sur les 7 documents du manifeste
  - Types et quantites K8s valides (100m, 500m, 128Mi, 256Mi, 20Gi)
  - References croisees validees : Service selector 'app: analytics-api' pointe vers le Pod analytics-api
  - Reference ServiceAccount analytics-api-sa valide dans Deployment analytics-api
  - Sidecar dapr-sidecar valide en mode 'annotations' (dapr.io/enabled et dapr.io/app-id presentes, pas de conteneur manuel)
  - Contrôle déterministe Python : OK
- Avertissements : ["L'utilisation de la ressource PostgresCluster requiert la presence de l'operateur CrunchyData PGO (v5+) installe dans le cluster.", "L'injection effective du sidecar Dapr requiert l'opérateur Dapr actif dans le cluster cible."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | data | manifest (Namespace/data et namespace: data sur toutes les ressources) |
| components[0].component_name | analytics-api | manifest (Deployment/analytics-api, Service/analytics-api, ServiceAccount/analytics-api-sa) |
| components[0].image | myregistry/analytics:2.0 | manifest (Deployment analytics-api container image) |
| components[0].ports[0] | 8080/TCP | manifest (Deployment containerPort 8080, Service port/targetPort 8080) |
| components[0].sidecars[0] | dapr-sidecar | manifest (Deployment annotations dapr.io/enabled: 'true', dapr.io/app-id: analytics-api) |
| unmapped_requirements[0] | PostgresCluster CrunchyData | manifest (PostgresCluster/postgres-cluster best-effort) |
| global_constraints[0] | Conformité PCI-DSS niveau 1 | manifest (securityContext restreint, NetworkPolicy, StorageClass chiffrée) |
| global_constraints[1] | Chiffrement au repos obligatoire pour tous les volumes | manifest (PostgresCluster storageClassName: encrypted-sc sur dataVolumeClaimSpec et pgbackrest) |
| global_constraints[2] | Rotation des clés tous les 90 jours | unresolved_items (exigence operationnelle hors scope direct du manifeste K8s statique) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone) (kind supposé : `PostgresCluster`)

## 7. ⚠️ À vérifier / relancer si besoin

- 1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone)' (kind supposé: PostgresCluster)
- Se connecter à une base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone)
- [analytics-api] Chiffrement au repos obligatoire pour tous les volumes: aucun volume n'est attaché à ce composant, le chiffrement des disques sous-jacents relève de la configuration infra/StorageClass
- [analytics-api] Conformité PCI-DSS niveau 1: requiert un ensemble de contrôles infrastructure, audit logs, SIEM, gestion des vulnérabilités et règles de réseau hors du scope du template k8s de base
- [analytics-api] Rotation des clés tous les 90 jours: nécessite un gestionnaire de secrets externe (ex: Vault, External Secrets Operator) et un processus opérationnel dédié
- [analytics-api] hpa: laissé pour l'Agent 4
- [analytics-api] resources.requests/limits: laissé pour l'Agent 4
- admission_policies ('Exiger le chiffrement au repos pour tous les volumes') : aucune règle Kyverno/OPA générée automatiquement afin d'éviter une mauvaise interprétation de politique de sécurité sensible.
- admission_policies: Exiger le chiffrement au repos pour tous les volumes (PCI-DSS niveau 1) : pattern non reconnu, aucune policy générée automatiquement (évite le risque d'une règle de sécurité mal traduite) — à écrire manuellement.
- global_constraints[2] ('Rotation des clés tous les 90 jours') : exige un composant externe de gestion de clés/secrets (ex: HashiCorp Vault, External Secrets Operator, AWS KMS) et un processus operationnel, non configurables de façon statique dans un manifeste K8s natif.
- global_constraints[2] ('Rotation des clés tous les 90 jours') : ne peut pas être configurée de manière statique dans des manifestes Kubernetes basiques et nécessite un gestionnaire de secrets externe (ex: HashiCorp Vault, External Secrets Operator).
- unmapped_requirements: 1 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone) (suggested_kind=PostgresCluster)
- unmapped_requirements[0] ('PostgresCluster avec 3 instances et réplication synchrone') : ressource générée en mode BEST-EFFORT par l'Agent 2 hors du schéma structuré strict, requérant la présence de l'opérateur CrunchyData PGO dans le cluster.
- unmapped_requirements[0] ('PostgresCluster') : ressource issue d'un fragment best-effort non validé par le schéma OpenAPI strict, à valider manuellement avant tout déploiement.

## Métriques d'exécution

- Latence totale du run : **147.21 s** (dont pipeline seul : 147.21 s)
- Appels LLM : **10** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 142.719 s (moyenne 14.272 s/appel)
- Tokens consommés : **51338** (41372 prompt + 9966 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 21.645 | 6505 |
| Agent 1 - Analyse (self-check) | 1 | 3.464 | 1311 |
| Agent 1 - Analyse (contraintes globales) | 1 | 7.363 | 1266 |
| Agent 2 - Template | 1 | 15.888 | 7362 |
| Agent 2 - Template (best-effort) | 1 | 16.29 | 6921 |
| Agent 3 - Validation | 1 | 12.136 | 3758 |
| Agent 4 - Énergie | 1 | 11.886 | 4387 |
| Agent 5 - Vérification finale | 2 | 48.723 | 18347 |
| Réparation ciblée | 1 | 5.324 | 1481 |