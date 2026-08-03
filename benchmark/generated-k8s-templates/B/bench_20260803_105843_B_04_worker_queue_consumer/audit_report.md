# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie un worker Python "image-resizer" (image myregistry/resizer:3.2, namespace "media") qui consomme des messages depuis une file RabbitMQ ("resize-queue", hôte à lire depuis le ConfigMap "rabbitmq-config", clé "host"). Pas de port HTTP exposé. Je veux qu'il scale automatiquement en fonction du nombre de messages en attente dans la file (KEDA), de 0 au repos jusqu'à 10 réplicas maximum en pic de charge, pour économiser un maximum de ressources quand la file est vide. Pas de stockage persistant nécessaire.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `image-resizer` (Deployment)

## 3. Auto-vérification Agent 1

- Auto-check réussi : **True**
- Tentatives de réparation internes : 0
- ⚠️ Exigences jamais couvertes : ["Autoscaling KEDA de 0 à 10 réplicas selon la profondeur de file (file 'resize-queue')"]
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].env_vars[0].name` : Quel nom de variable d'environnement le worker attend-il pour l'hôte RabbitMQ ? → hypothèse retenue : *Utilisation du nom standard 'RABBITMQ_HOST'.* (confiance medium)
  - `components[0].replicas` : Quel doit être le nombre de réplicas statique initial dans le manifeste Deployment ? → hypothèse retenue : *Déclaré à 0 réplicas pour respecter l'état au repos piloté par KEDA.* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[image-resizer]']
- ⚠️ Champs laissés ouverts : ["Autoscaling KEDA de 0 à 10 réplicas selon la profondeur de file (file 'resize-queue')", "unmapped_requirements: Autoscaling basé sur KEDA selon le nombre de messages en attente dans la file RabbitMQ 'resize-queue' (min 0, max 10 réplicas) (suggested_kind=ScaledObject)"]
- Actions :
  - Extraction initiale + 0 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ["Quel nom de variable d'environnement le worker attend-il pour l'hôte RabbitMQ ?", 'Quel doit être le nombre de réplicas statique initial dans le manifeste Deployment ?']

### Agent 2 - Template
- Champs traités : ['namespace', '[image-resizer] component_name', '[image-resizer] workload_type', '[image-resizer] image', '[image-resizer] replicas', '[image-resizer] labels', '[image-resizer] ports: aucun port à exposer, pas de Service généré', '[image-resizer] env_vars', '[image-resizer] volumes: aucun volume demandé', '[image-resizer] sidecars: aucun sidecar demandé', '[image-resizer] depends_on: aucune dépendance directe à câbler au niveau Pod', '[image-resizer] security_requirements: durcissement par défaut appliqué', '[image-resizer] observability_requirements: aucune exigence déclarée', '[image-resizer] ingress: aucun ingress demandé', '[image-resizer] rbac: désactivé, ServiceAccount minimal créé', '[image-resizer] service_mesh_routing: aucun routage mesh demandé', '[image-resizer] observability_style', '[image-resizer] cron_schedule: non applicable pour Deployment', '[image-resizer] config_maps: aucune ConfigMap dédiée à créer', '[image-resizer] network_policy: aucune restriction egress demandée', '[image-resizer] deployment_strategy: stratégie par défaut Deployment', '[image-resizer] namespace', '[image-resizer] security_requirements: Hardening par défaut appliqué (runAsNonRoot, allowPrivilegeEscalation=false, readOnlyRootFilesystem, drop ALL capabilities, seccomp RuntimeDefault)', "[image-resizer] observability_requirements: Aucune exigence d'observabilité spécifique fournie", '[image-resizer] ingress: Ingress non activé', "[image-resizer] rbac: ServiceAccount 'image-resizer-sa' créé sans privilèges API additionnels (principe de moindre privilège)"]
- ⚠️ Champs laissés ouverts : ['unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'media' généré (une seule fois, déterministe)
  - Génération BEST-EFFORT (non vérifiée, un appel LLM par exigence) pour 1 exigence(s) hors du schéma structuré : ["Autoscaling basé sur KEDA selon le nombre de messages en attente dans la file RabbitMQ 'resize-queue' (min 0, max 10 réplicas)"]
- Avertissements : ['[image-resizer] Nombre de réplicas défini à 0 selon la spécification fournie.', "[image-resizer] Si l'application nécessite d'écrire dans des fichiers temporaires, le système de fichiers en lecture seule (readOnlyRootFilesystem: true) devra être ajusté avec un volume emptyDir."]

### Agent 3 - Validation
- Champs traités : ['namespace', 'architecture_type', 'component_name', 'workload_type', 'image', 'replicas', 'labels', 'ports', 'env_vars', 'volumes', 'sidecars', 'ingress', 'rbac', 'observability_style', 'cron_schedule']
- Actions :
  - Structure du manifeste YAML valide et analysable
  - Présence des champs obligatoires (apiVersion, kind, metadata.name, spec)
  - Nom de namespace cohérent avec la spec ('media')
  - Présence et liaison correcte du ServiceAccount dédié ('image-resizer-sa')
  - Alignement strict des labels et selectors ('app: image-resizer')
  - Fidélité des variables d'environnement à la spec (RABBITMQ_HOST depuis ConfigMap 'rabbitmq-config')
  - Conformité du nombre de répliques (replicas: 0)
  - Respect de la configuration de sécurité (RunAsNonRoot, ReadOnlyRootFilesystem, Drop ALL)

### Agent 4 - Énergie
- Champs traités : ['[image-resizer] workload_type', '[image-resizer] replicas', '[image-resizer] energy_goals', '[image-resizer] resource_hints', '[image-resizer] traffic_windows', '[image-resizer] constraints', "[image-resizer] energy_goals: Mettre à l'échelle à 0 réplicas au repos pour économiser le maximum de ressources réseau et compute lorsque la file de messages est vide."]
- Actions :
  - [image-resizer] Ajout des requêtes et limites de ressources (CPU: 250m/1000m, Memory: 256Mi/1Gi) adaptées à un composant de traitement d'images.
  - [image-resizer] Ajout d'un ScaledObject KEDA configuré pour effectuer un auto-scaling de 0 à 10 réplicas basé sur la file RabbitMQ 'resize-queue'.
- Avertissements : ["[image-resizer] Le scaling jusqu'à 0 réplicas basé sur une file de messages RabbitMQ nécessite que l'opérateur KEDA soit installé dans le cluster (https://keda.sh).", "[image-resizer] Le seuil de longueur de file pour déclencher le scaling est défini par défaut à '5' messages par réplica et doit être ajusté selon la charge.", "Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['/']."]

### Agent 5 - Vérification finale
- Champs traités : ['syntax_validation', 'cross_resource_references', 'traceability_matrix', 'unmapped_requirements_audit']
- ⚠️ Champs laissés ouverts : ["unmapped_requirements: Autoscaling basé sur KEDA selon le nombre de messages en attente dans la file RabbitMQ 'resize-queue' (min 0, max 10 réplicas) — Exigence générée en best-effort par l'Agent 2 hors schéma strict, à valider manuellement avant déploiement.", "Workload 'image-resizer' : référence la ConfigMap 'rabbitmq-config' (env) qui n'existe pas parmi les ConfigMaps connues.", "1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Autoscaling basé sur KEDA selon le nombre de messages en attente dans la file RabbitMQ 'resize-queue' (min 0, max 10 réplicas)' (kind supposé: ScaledObject)"]
- Actions :
  - yaml.safe_load_all OK sur 4 documents (Namespace, ServiceAccount, Deployment, ScaledObject)
  - Formats des quantités k8s valides (cpu: 250m/1000m, memory: 256Mi/1Gi)
  - Cohérence des références croisées vérifiée : Deployment 'image-resizer' référencé par ScaledObject 'image-resizer-scaledobject'
  - Nom de ServiceAccount 'image-resizer-sa' aligné entre la ressource ServiceAccount et la spec du Pod
  - Labels et selectors 'app: image-resizer' strictement alignés
  - Namespace 'media' cohérent sur l'ensemble des documents
  - Contrôle déterministe Python : 1 erreur(s)
- Avertissements : ["L'utilisation de KEDA (CRD keda.sh/v1alpha1 ScaledObject) nécessite que l'opérateur KEDA soit préalablement installé sur le cluster cible.", "La ConfigMap 'rabbitmq-config' référencée par la variable RABBITMQ_HOST doit exister dans le namespace 'media'."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | media | manifest (Namespace media et metadata.namespace sur tous les objets) |
| components[0].component_name | image-resizer | manifest (Deployment nom=image-resizer) |
| components[0].image | myregistry/resizer:3.2 | manifest (Deployment image-resizer spec.template.spec.containers[0].image) |
| components[0].replicas | 0 | manifest (Deployment image-resizer spec.replicas=0) |
| components[0].env_vars[0] | RABBITMQ_HOST via configMapKeyRef rabbitmq-config.host | manifest (Deployment image-resizer env[0]) |
| components[0].energy_goals[0] | Mettre à l'échelle à 0 réplicas au repos pour économiser le maximum de ressources | manifest (Deployment spec.replicas=0, ScaledObject minReplicaCount=0) |
| unmapped_requirements[0] | Autoscaling basé sur KEDA selon le nombre de messages en attente dans la file RabbitMQ 'resize-queue' (min 0, max 10 réplicas) | manifest (ScaledObject keda.sh/v1alpha1 image-resizer-scaledobject, fragment libre non vérifié) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- Autoscaling basé sur KEDA selon le nombre de messages en attente dans la file RabbitMQ 'resize-queue' (min 0, max 10 réplicas) (kind supposé : `ScaledObject`)

## 7. ⚠️ À vérifier / relancer si besoin

- 1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'Autoscaling basé sur KEDA selon le nombre de messages en attente dans la file RabbitMQ 'resize-queue' (min 0, max 10 réplicas)' (kind supposé: ScaledObject)
- Autoscaling KEDA de 0 à 10 réplicas selon la profondeur de file (file 'resize-queue')
- Workload 'image-resizer' : référence la ConfigMap 'rabbitmq-config' (env) qui n'existe pas parmi les ConfigMaps connues.
- unmapped_requirements: 1 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: Autoscaling basé sur KEDA selon le nombre de messages en attente dans la file RabbitMQ 'resize-queue' (min 0, max 10 réplicas) (suggested_kind=ScaledObject)
- unmapped_requirements: Autoscaling basé sur KEDA selon le nombre de messages en attente dans la file RabbitMQ 'resize-queue' (min 0, max 10 réplicas) — Exigence générée en best-effort par l'Agent 2 hors schéma strict, à valider manuellement avant déploiement.

## Métriques d'exécution

- Latence totale du run : **264.309 s** (dont pipeline seul : 264.309 s)
- Appels LLM : **9** (1 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 261.555 s (moyenne 29.062 s/appel)
- Tokens consommés : **33226** (27020 prompt + 6206 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 37.455 | 5570 |
| Agent 1 - Analyse (self-check) | 2 (1 échoué(s)) | 31.47 | 1289 |
| Agent 1 - Analyse (réparation schéma) | 1 | 24.064 | 2515 |
| Agent 2 - Template | 1 | 25.038 | 6507 |
| Agent 2 - Template (best-effort) | 1 | 13.674 | 6306 |
| Agent 3 - Validation | 1 | 49.403 | 2328 |
| Agent 4 - Énergie | 1 | 14.701 | 3056 |
| Agent 5 - Vérification finale | 1 | 65.751 | 5655 |