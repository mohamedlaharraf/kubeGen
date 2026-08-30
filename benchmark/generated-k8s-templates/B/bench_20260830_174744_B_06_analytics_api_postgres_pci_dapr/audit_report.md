# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie une API d'analytics appelée "analytics-api", image myregistry/analytics:2.0, namespace "data", port 8080. Elle doit se connecter à une base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances et réplication synchrone). L'application doit aussi être conforme à la norme PCI-DSS niveau 1 (chiffrement au repos obligatoire pour tous les volumes, rotation des clés tous les 90 jours). Utilise aussi Dapr comme sidecar pour la communication pub/sub avec les autres services de l'entreprise.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `analytics-api` (Deployment), 1 sidecar(s): ['dapr'], dépend de: ['postgres-db']
- ⚠️ Dépendances vers des noms non résolus (composant absent ou ressource externe) : ["'analytics-api' dépend de 'postgres-db', qui ne correspond à aucun composant généré par ce pipeline — soit une faute de frappe dans le nom, soit une ressource externe gérée hors du schéma structuré (base de données, service tiers...) à vérifier manuellement."]

## 3. Auto-vérification Agent 1

- Auto-check réussi : **True**
- Tentatives de réparation internes : 2
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].replicas` : Le nombre de réplicas n'est pas spécifié pour l'API. → hypothèse retenue : *1* (confiance medium)
  - `components[0].workload_type` : Le type de workload n'est pas précisé pour l'API. → hypothèse retenue : *Deployment* (confiance high)
  - `components[0].sidecars[0].image` : L'image exacte pour le sidecar Dapr n'est pas fournie. → hypothèse retenue : *dapr/dapr* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[analytics-api]']
- ⚠️ Champs laissés ouverts : ["unmapped_requirements: Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances, réplication synchrone, chiffrement au repos obligatoire pour tous les volumes) (suggested_kind=None)"]
- Actions :
  - Extraction initiale + 2 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ["Le nombre de réplicas n'est pas spécifié pour l'API.", "Le type de workload n'est pas précisé pour l'API.", "L'image exacte pour le sidecar Dapr n'est pas fournie."]

### Agent 2 - Template
- Champs traités : ['namespace', '[analytics-api] component_name', '[analytics-api] workload_type', '[analytics-api] image', '[analytics-api] replicas', '[analytics-api] ports: expose_service=true traduit en Service ClusterIP', "[analytics-api] sidecars: dapr traité via annotations d'injection automatique", '[analytics-api] rbac: ServiceAccount créé, Role/Binding non requis (enabled=false)', '[analytics-api] namespace', "[analytics-api] labels: aucun fourni, utilisé 'app: analytics-api' pour le sélecteur", "[analytics-api] security_requirements: Conformité norme PCI-DSS niveau 1 : Application d'un securityContext durci (non-root, readOnlyRootFilesystem, drop capabilities, seccompProfile).", '[analytics-api] rbac: Création du ServiceAccount analytics-api-sa']
- ⚠️ Champs laissés ouverts : ['[analytics-api] env_vars: vide', '[analytics-api] volumes: vide', '[analytics-api] ingress: None', '[analytics-api] service_mesh_routing: vide', '[analytics-api] config_maps: vide', '[analytics-api] network_policy: None', '[analytics-api] deployment_strategy: None', "[analytics-api] Chiffrement au repos obligatoire pour tous les volumes : Aucun volume défini dans la spec, cette exigence devra être gérée au niveau de la StorageClass par l'infrastructure.", '[analytics-api] Rotation des clés tous les 90 jours : Exigence de processus/politique non traduisible dans un manifeste Kubernetes statique.', 'unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'data' généré (une seule fois, déterministe)
  - [analytics-api] 1 sidecar(s) empaqueté(s) dans le même Pod : ["communication pub/sub avec les autres services de l'entreprise"]
  - Génération BEST-EFFORT (non vérifiée, un appel LLM par exigence) pour 1 exigence(s) hors du schéma structuré : ["Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances, réplication synchrone, chiffrement au repos obligatoire pour tous les volumes)"]
- Avertissements : ["[analytics-api] Le sidecar 'dapr' a été implémenté via des annotations d'injection automatique conformément aux standards Dapr, et non comme un conteneur manuel.", '[analytics-api] La conformité PCI-DSS niveau 1 nécessite des contrôles bien au-delà du manifeste Kubernetes (audit, monitoring, isolation réseau physique, etc.).', "[analytics-api] Le champ 'readOnlyRootFilesystem: true' est activé par défaut pour le hardening ; si l'application a besoin d'écrire dans des dossiers temporaires, un volume emptyDir devra être ajouté."]

### Agent 3 - Validation
- Champs traités : ['namespace', 'component_name', 'workload_type', 'image', 'replicas', 'ports', 'sidecars', 'rbac', 'serviceAccount']
- Actions :
  - apiVersion présent
  - kind présent
  - metadata.name présent
  - spec présent
  - Cohérence Service selector / Deployment labels
  - Présence du ServiceAccount dédié
  - Sidecar Dapr traité via annotations d'injection (pas de doublon de conteneur)
  - Namespace cohérent
  - Indentation YAML valide

### Agent 4 - Énergie
- Champs traités : ['[analytics-api] energy_goals', '[analytics-api] resource_hints', '[analytics-api] traffic_windows', '[analytics-api] replicas', '[analytics-api] energy_goals: Optimisation du dimensionnement des ressources pour éviter le gaspillage (right-sizing)', "[analytics-api] energy_goals: Mise en place d'un scaling automatique pour adapter la consommation à la charge réelle"]
- Actions :
  - [analytics-api] Définition de resources.requests (100m CPU, 256Mi RAM) et limits (500m CPU, 512Mi RAM) basées sur un profil d'API analytique standard, car aucun resource_hint n'était fourni.
  - [analytics-api] Ajout d'un HorizontalPodAutoscaler (HPA) avec un min de 1 et un max de 5 réplicas, ciblant 60% d'utilisation CPU pour optimiser le coût énergétique en période de faible charge.
  - [analytics-api] Ajout de livenessProbe et readinessProbe via tcpSocket sur le port 8080 pour garantir que seules les instances saines consomment des ressources.
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['/']."]

### Agent 5 - Vérification finale
- Champs traités : ['namespace', 'analytics-api workload', 'analytics-api service', 'analytics-api hpa', 'analytics-api sa', 'postgres-cluster', 'security hardening', 'resource optimization']
- ⚠️ Champs laissés ouverts : ['Rotation des clés tous les 90 jours (exigence de politique/processus non traduisible en manifeste Kubernetes)', "Base de données gérée par l'opérateur CrunchyData PostgreSQL (générée en best-effort, non vérifiée par schéma OpenAPI)", "1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances, réplication synchrone, chiffrement au repos obligatoire pour tous les volumes)'"]
- Actions :
  - yaml.safe_load_all OK sur 6 documents
  - Vérification HPA -> Deployment: analytics-api cible analytics-api (OK)
  - Vérification Service -> Deployment: selector 'app: analytics-api' correspond aux labels (OK)
  - Vérification Deployment -> ServiceAccount: analytics-api-sa présent (OK)
  - Vérification des ports: Service 8080 -> Deployment 8080 (OK)
  - Vérification des quantités k8s: 100m, 256Mi, 500m, 512Mi sont valides (OK)
  - Vérification Sidecar: Dapr implémenté via annotations dapr.io/* dans le Pod (OK)
  - Corrigé: Intégration du document PostgresCluster (best-effort) dans le flux YAML final
  - Corrigé: Ajout explicite du namespace 'data' aux métadonnées du PostgresCluster pour cohérence
  - Contrôle déterministe Python : OK
- Avertissements : ["L'utilisation de la ressource PostgresCluster nécessite l'installation préalable de l'opérateur CrunchyData PostgreSQL.", "Le storageClassName 'encrypted-storage' est un placeholder et doit être mappé au StorageClass chiffré réel du cluster."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| components[0].component_name | analytics-api | manifest (Deployment, Service, HPA, ServiceAccount) |
| components[0].image | myregistry/analytics:2.0 | manifest (Deployment.spec.template.spec.containers[0].image) |
| components[0].sidecars[0] | dapr | manifest (Deployment annotations dapr.io/enabled) |
| security_requirements[0] | Conformité norme PCI-DSS niveau 1 | manifest (Deployment.spec.template.spec.securityContext & containers[0].securityContext) |
| security_requirements[1] | Chiffrement au repos obligatoire | manifest (PostgresCluster.spec.storage.storageClassName: encrypted-storage) |
| unmapped_requirements[0] | Base de données CrunchyData PostgreSQL | manifest (PostgresCluster) |
| energy_goals | Scaling automatique / Right-sizing | manifest (HorizontalPodAutoscaler, resources.requests/limits) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances, réplication synchrone, chiffrement au repos obligatoire pour tous les volumes) (kind inconnu)

## 7. ⚠️ À vérifier / relancer si besoin

- 1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances, réplication synchrone, chiffrement au repos obligatoire pour tous les volumes)'
- Base de données gérée par l'opérateur CrunchyData PostgreSQL (générée en best-effort, non vérifiée par schéma OpenAPI)
- Rotation des clés tous les 90 jours (exigence de politique/processus non traduisible en manifeste Kubernetes)
- [analytics-api] Chiffrement au repos obligatoire pour tous les volumes : Aucun volume défini dans la spec, cette exigence devra être gérée au niveau de la StorageClass par l'infrastructure.
- [analytics-api] Rotation des clés tous les 90 jours : Exigence de processus/politique non traduisible dans un manifeste Kubernetes statique.
- [analytics-api] config_maps: vide
- [analytics-api] deployment_strategy: None
- [analytics-api] env_vars: vide
- [analytics-api] ingress: None
- [analytics-api] network_policy: None
- [analytics-api] service_mesh_routing: vide
- [analytics-api] volumes: vide
- unmapped_requirements: 1 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: Base de données gérée par l'opérateur CrunchyData PostgreSQL (PostgresCluster avec 3 instances, réplication synchrone, chiffrement au repos obligatoire pour tous les volumes) (suggested_kind=None)

## Métriques d'exécution

- Latence totale du run : **810.58 s** (dont pipeline seul : 810.58 s)
- Appels LLM : **12** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 808.667 s (moyenne 67.389 s/appel)
- Tokens consommés : **42601** (32929 prompt + 9672 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 62.863 | 5609 |
| Agent 1 - Analyse (self-check) | 3 | 82.418 | 4307 |
| Agent 1 - Analyse (réparation) | 2 | 125.417 | 5371 |
| Agent 1 - Analyse (réparation schéma) | 1 | 59.09 | 2725 |
| Agent 2 - Template | 1 | 70.125 | 6711 |
| Agent 2 - Template (best-effort) | 1 | 199.86 | 6258 |
| Agent 3 - Validation | 1 | 49.764 | 2459 |
| Agent 4 - Énergie | 1 | 59.53 | 3263 |
| Agent 5 - Vérification finale | 1 | 99.599 | 5898 |