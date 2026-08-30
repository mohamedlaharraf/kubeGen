# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie une API de paiement Node.js appelée "checkout-api", image myregistry/checkout:1.4.2, namespace "payments". Elle doit tourner en 3 réplicas, exposer le port 8080 en HTTP. Elle a besoin d'une variable d'environnement NODE_ENV=production et d'un mot de passe base de données DB_PASSWORD à lire depuis le secret "checkout-db-secret". Le trafic est très faible la nuit (entre minuit et 6h) et très élevé entre 9h et midi : je veux que ça scale automatiquement pour économiser de l'énergie/coût aux heures creuses, avec un minimum de 2 réplicas et un maximum de 8. Pas de stockage persistant nécessaire. La sécurité est primordiale.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `checkout-api` (Deployment)

## 3. Auto-vérification Agent 1

- Auto-check réussi : **True**
- Tentatives de réparation internes : 1
- ⚠️ Exigences jamais couvertes : ['Runtime: Node.js', 'Type: API de paiement']
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].workload_type` : Le type de workload n'est pas spécifié, s'agit-il d'un Deployment ? → hypothèse retenue : *Deployment* (confiance high)
  - `components[0].env_vars[1].secret_key` : La clé exacte à l'intérieur du secret 'checkout-db-secret' n'est pas précisée. → hypothèse retenue : *DB_PASSWORD* (confiance medium)
  - `components[0].ingress` : L'utilisateur demande d'exposer le port 8080, mais ne mentionne pas d'accès externe (DNS, HTTPS). → hypothèse retenue : *Exposition via Service interne uniquement, pas d'Ingress* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[checkout-api]']
- ⚠️ Champs laissés ouverts : ['Runtime: Node.js', 'Type: API de paiement', "unmapped_requirements: {'requirement': 'Application: API de paiement', 'suggested_kind': 'description'} (suggested_kind=description)", "unmapped_requirements: {'requirement': 'Runtime: Node.js', 'suggested_kind': 'runtime'} (suggested_kind=runtime)"]
- Actions :
  - Extraction initiale + 1 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
- Avertissements : ["Le type de workload n'est pas spécifié, s'agit-il d'un Deployment ?", "La clé exacte à l'intérieur du secret 'checkout-db-secret' n'est pas précisée.", "L'utilisateur demande d'exposer le port 8080, mais ne mentionne pas d'accès externe (DNS, HTTPS)."]

### Agent 2 - Template
- Champs traités : ['namespace', '[checkout-api] component_name: utilisé pour metadata.name', '[checkout-api] workload_type: Deployment généré', '[checkout-api] image: appliquée au conteneur', '[checkout-api] replicas: 3 configurés', '[checkout-api] labels: appliqués au Deployment et au Pod', '[checkout-api] ports: port 8080 configuré et Service généré car expose_service=true', '[checkout-api] env_vars: NODE_ENV et DB_PASSWORD (via secretKeyRef) configurés', '[checkout-api] volumes: aucun demandé, rien à faire', '[checkout-api] sidecars: aucun demandé, rien à faire', '[checkout-api] depends_on: aucune dépendance, rien à faire', '[checkout-api] security_requirements: hardening appliqué (securityContext)', '[checkout-api] observability_requirements: aucune exigence, rien à faire', '[checkout-api] ingress: aucun demandé, rien à faire', '[checkout-api] rbac: désactivé, seul le ServiceAccount est créé', '[checkout-api] service_mesh_routing: aucun demandé, rien à faire', "[checkout-api] observability_style: annotations (aucune métrique spécifiée donc pas d'annotations ajoutées)", '[checkout-api] cron_schedule: non applicable pour Deployment', '[checkout-api] config_maps: aucune demandée, rien à faire', '[checkout-api] network_policy: aucune demandée, rien à faire', '[checkout-api] deployment_strategy: aucune demandée, Deployment standard utilisé', '[checkout-api] namespace: payments appliqué à toutes les ressources', "[checkout-api] security_requirements: Application d'un securityContext durci sur le pod et le conteneur (runAsNonRoot, allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities.drop: [ALL], seccompProfile: RuntimeDefault) suite à l'exigence 'La sécurité est primordiale'", "[checkout-api] observability_requirements: Aucune exigence d'observabilité fournie dans la spec", '[checkout-api] ingress: Aucun ingress demandé', '[checkout-api] rbac: Création du ServiceAccount dédié checkout-api-sa']
- ⚠️ Champs laissés ouverts : ['unmapped_requirements: 2 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'payments' généré (une seule fois, déterministe)
  - Génération BEST-EFFORT (non vérifiée, un appel LLM par exigence) pour 2 exigence(s) hors du schéma structuré : ["{'requirement': 'Application: API de paiement', 'suggested_kind': 'description'}", "{'requirement': 'Runtime: Node.js', 'suggested_kind': 'runtime'}"]

### Agent 3 - Validation
- Champs traités : ['namespace', 'component_name', 'workload_type', 'image', 'replicas', 'labels', 'ports', 'env_vars', 'volumes', 'sidecars', 'ingress', 'rbac', 'serviceAccount']
- Actions :
  - apiVersion, kind, metadata.name, spec présents pour toutes les ressources
  - Cohérence des labels et selectors entre Deployment et Service (app: checkout-api)
  - Présence du ServiceAccount dédié malgré rbac.enabled=false
  - Fidélité de l'image, des replicas et des ports par rapport à la NormalizedSpec
  - Configuration correcte des variables d'environnement (valeur directe et secretKeyRef)
  - Indentation YAML valide
  - Absence de doublons de ressources

### Agent 4 - Énergie
- Champs traités : ['[checkout-api] energy_goals', '[checkout-api] resource_hints', '[checkout-api] traffic_windows', '[checkout-api] constraints', '[checkout-api] workload_type', '[checkout-api] replicas', "[checkout-api] energy_goals: économiser de l'énergie/coût aux heures creuses"]
- Actions :
  - [checkout-api] Dimensionnement des ressources (requests/limits) basé sur des valeurs prudentes pour un API standard afin d'éviter le sur-provisionnement.
  - [checkout-api] Remplacement de l'HPA classique par un ScaledObject KEDA pour implémenter le scaling temporel basé sur traffic_windows.
  - [checkout-api] Configuration d'un trigger cron KEDA pour descendre à 2 réplicas entre 00:00 et 06:00.
  - [checkout-api] Configuration d'un trigger cron KEDA pour monter à 8 réplicas entre 09:00 et 12:00.
  - [checkout-api] Ajout d'un trigger CPU (60%) pour garantir la réactivité du scaling en dehors des fenêtres fixes.
  - [checkout-api] Ajout de livenessProbe et readinessProbe via tcpSocket pour éliminer les pods inactifs/zombies.
  - [checkout-api] Ajout d'un PodDisruptionBudget pour maintenir un minimum de 2 pods disponibles lors des opérations de maintenance.
- Avertissements : ["[checkout-api] L'utilisation du ScaledObject nécessite l'installation de l'opérateur KEDA (https://keda.sh) dans le cluster. Alternative : utiliser un HorizontalPodAutoscaler classique (moins précis sur les horaires).", "[checkout-api] Timezone 'UTC' utilisée par défaut pour les triggers cron car non spécifiée dans la configuration.", '[checkout-api] Les ressources CPU/Mémoire ont été estimées par défaut car resource_hints ne contenait que des informations de scaling et non de dimensionnement matériel.']

### Agent 5 - Vérification finale
- Champs traités : ['namespace', 'component_name', 'workload_type', 'image', 'replicas', 'labels', 'ports', 'env_vars', 'energy_goals', 'resource_hints', 'traffic_windows', 'constraints', 'security_requirements']
- ⚠️ Champs laissés ouverts : ['Runtime: Node.js (unmapped_requirement - information descriptive non traduisible en ressource K8s)', 'Type: API de paiement (unmapped_requirement - information descriptive non traduisible en ressource K8s)', "2 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : '{'requirement': 'Application: API de paiement', 'suggested_kind': 'description'}' (kind supposé: description); '{'requirement': 'Runtime: Node.js', 'suggested_kind': 'runtime'}' (kind supposé: runtime)"]
- Actions :
  - yaml.safe_load_all OK sur 6 documents
  - Vérification des types de quantités K8s (cpu/memory) : OK
  - Cohérence Service -> Deployment (selector app: checkout-api) : OK
  - Cohérence ScaledObject -> Deployment (scaleTargetRef: checkout-api) : OK
  - Cohérence PDB -> Deployment (selector app: checkout-api) : OK
  - Cohérence Deployment -> ServiceAccount (serviceAccountName: checkout-api-sa) : OK
  - Vérification des ports (containerPort 8080 == targetPort 8080 == probes 8080) : OK
  - Contrôle déterministe Python : OK
- Avertissements : ["L'utilisation du ScaledObject nécessite l'installation de l'opérateur KEDA dans le cluster.", "Timezone 'UTC' utilisée par défaut pour les triggers cron."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | payments | manifest (Namespace, metadata.namespace) |
| components[0].component_name | checkout-api | manifest (Deployment, Service, ScaledObject, PDB) |
| components[0].image | myregistry/checkout:1.4.2 | manifest (Deployment.spec.template.spec.containers[0].image) |
| components[0].replicas | 3 | manifest (Deployment.spec.replicas) |
| components[0].ports[0] | 8080 | manifest (Deployment.containerPort, Service.port/targetPort) |
| components[0].env_vars | NODE_ENV, DB_PASSWORD | manifest (Deployment.spec.template.spec.containers[0].env) |
| components[0].energy_goals[0] | économiser de l'énergie/coût aux heures creuses | manifest (ScaledObject triggers cron) |
| components[0].resource_hints | min 2, max 8 | manifest (ScaledObject.spec.minReplicaCount/maxReplicaCount) |
| components[0].traffic_windows | 00-06 low, 09-12 high | manifest (ScaledObject triggers cron) |
| components[0].security_requirements | La sécurité est primordiale | manifest (Deployment.spec.template.spec.securityContext & containers[0].securityContext) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- {'requirement': 'Application: API de paiement', 'suggested_kind': 'description'} (kind supposé : `description`)
- {'requirement': 'Runtime: Node.js', 'suggested_kind': 'runtime'} (kind supposé : `runtime`)

## 7. ⚠️ À vérifier / relancer si besoin

- 2 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : '{'requirement': 'Application: API de paiement', 'suggested_kind': 'description'}' (kind supposé: description); '{'requirement': 'Runtime: Node.js', 'suggested_kind': 'runtime'}' (kind supposé: runtime)
- Runtime: Node.js
- Runtime: Node.js (unmapped_requirement - information descriptive non traduisible en ressource K8s)
- Type: API de paiement
- Type: API de paiement (unmapped_requirement - information descriptive non traduisible en ressource K8s)
- unmapped_requirements: 2 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 2 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: {'requirement': 'Application: API de paiement', 'suggested_kind': 'description'} (suggested_kind=description)
- unmapped_requirements: {'requirement': 'Runtime: Node.js', 'suggested_kind': 'runtime'} (suggested_kind=runtime)

## Métriques d'exécution

- Latence totale du run : **1161.614 s** (dont pipeline seul : 1161.614 s)
- Appels LLM : **11** (1 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 1159.69 s (moyenne 105.426 s/appel)
- Tokens consommés : **44529** (36241 prompt + 8288 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 81.765 | 5973 |
| Agent 1 - Analyse (self-check) | 2 | 142.336 | 3386 |
| Agent 1 - Analyse (réparation) | 1 | 95.935 | 3171 |
| Agent 2 - Template | 2 (1 échoué(s)) | 353.92 | 6731 |
| Agent 2 - Template (best-effort) | 2 | 266.214 | 12245 |
| Agent 3 - Validation | 1 | 51.644 | 2953 |
| Agent 4 - Énergie | 1 | 79.086 | 3681 |
| Agent 5 - Vérification finale | 1 | 88.789 | 6389 |