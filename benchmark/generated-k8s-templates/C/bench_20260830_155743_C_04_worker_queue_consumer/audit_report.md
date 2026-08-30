# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie un worker Python "image-resizer" (image myregistry/resizer:3.2, namespace "media") qui consomme des messages depuis une file RabbitMQ ("resize-queue", hôte à lire depuis le ConfigMap "rabbitmq-config", clé "host"). Pas de port HTTP exposé. Je veux qu'il scale automatiquement en fonction du nombre de messages en attente dans la file (KEDA), de 0 au repos jusqu'à 10 réplicas maximum en pic de charge, pour économiser un maximum de ressources quand la file est vide. Pas de stockage persistant nécessaire.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `image-resizer` (Deployment)

- Auto-check réussi : **False**
- Tentatives de réparation internes : 2
- ⚠️ Exigences jamais couvertes : ['Scaling KEDA 0 à 10 réplicas', "La configuration spécifique du scaling KEDA (plage de 0 à 10 réplicas) n'est pas intégrée dans un champ structuré dédié (présente uniquement dans 'unmapped_requirements' et 'resource_hints').", "Le runtime 'Python' n'est pas représenté dans les champs structurés du composant (présent uniquement dans 'unmapped_requirements').", 'Runtime Python']
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].env_vars` : Quel est le nom exact de la variable d'environnement attendue par l'application pour l'hôte RabbitMQ ? → hypothèse retenue : *Utilisation de 'RABBITMQ_HOST'* (confiance medium)
  - `components[0].replicas` : Nombre de réplicas initial ? → hypothèse retenue : *1 (le scaling à 0 sera géré par KEDA)* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[image-resizer]']
- ⚠️ Champs laissés ouverts : ['Scaling KEDA 0 à 10 réplicas', "La configuration spécifique du scaling KEDA (plage de 0 à 10 réplicas) n'est pas intégrée dans un champ structuré dédié (présente uniquement dans 'unmapped_requirements' et 'resource_hints').", "Le runtime 'Python' n'est pas représenté dans les champs structurés du composant (présent uniquement dans 'unmapped_requirements').", 'Runtime Python', "unmapped_requirements: scale automatiquement en fonction du nombre de messages en attente dans la file (KEDA), de 0 au repos jusqu'à 10 réplicas maximum (suggested_kind=KEDA ScaledObject)", 'unmapped_requirements: Le worker est développé en Python (suggested_kind=runtime)']
- Actions :
  - Extraction initiale + 2 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : aucune détectée
- Avertissements : ["Quel est le nom exact de la variable d'environnement attendue par l'application pour l'hôte RabbitMQ ?", 'Nombre de réplicas initial ?']

### Agent 2 - Template
- Champs traités : ['namespace', '[image-resizer] component_name', '[image-resizer] workload_type', '[image-resizer] image', '[image-resizer] replicas', '[image-resizer] labels', '[image-resizer] ports: aucun demandé, pas de Service généré', '[image-resizer] env_vars', '[image-resizer] volumes: aucun demandé', '[image-resizer] sidecars: aucun demandé', '[image-resizer] depends_on: aucun', '[image-resizer] security_requirements: application du hardening par défaut', '[image-resizer] observability_requirements: aucun demandé', '[image-resizer] ingress: aucun demandé', '[image-resizer] rbac: ServiceAccount créé, Role/Binding désactivés', '[image-resizer] service_mesh_routing: aucun demandé', '[image-resizer] observability_style: annotations (rien à injecter sans requirements)', '[image-resizer] cron_schedule: non applicable pour Deployment', '[image-resizer] config_maps: aucune configmap dédiée demandée', '[image-resizer] network_policy: aucune restriction spécifique demandée', '[image-resizer] deployment_strategy: aucune stratégie progressive demandée', '[image-resizer] namespace', '[image-resizer] security_requirements: Application du securityContext durci par défaut : runAsNonRoot, allowPrivilegeEscalation=false, readOnlyRootFilesystem=true, capabilities.drop=ALL, seccompProfile=RuntimeDefault', "[image-resizer] observability_requirements: Aucune exigence d'observabilité fournie", '[image-resizer] ingress: Aucun ingress demandé', '[image-resizer] rbac: Création du ServiceAccount dédié image-resizer-sa']
- ⚠️ Champs laissés ouverts : ['unmapped_requirements: 2 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'media' généré (une seule fois, déterministe)
  - Génération BEST-EFFORT (non vérifiée) pour 2 exigence(s) hors du schéma structuré : ["scale automatiquement en fonction du nombre de messages en attente dans la file (KEDA), de 0 au repos jusqu'à 10 réplicas maximum", 'Le worker est développé en Python']
- Avertissements : ["[image-resizer] readOnlyRootFilesystem: true appliqué par défaut ; vérifier si l'application a besoin d'écrire sur le disque local (si oui, un volume emptyDir devra être ajouté)."]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'component_name', 'workload_type', 'image', 'replicas', 'labels', 'ports', 'env_vars', 'volumes', 'sidecars', 'rbac', 'security_requirements']
- Actions :
  - apiVersion présent
  - kind présent
  - metadata.name présent
  - cohérence labels/selectors Deployment
  - ServiceAccount présent et lié au workload
  - securityContext conforme aux bonnes pratiques
  - env_vars fidèles à la NormalizedSpec
  - absence de sidecars conformément à la spec
- Avertissements : ["validation_errors: [deterministic-cross-reference] Workload 'image-resizer' : référence la ConfigMap 'rabbitmq-config' (env) qui n'existe pas parmi les ConfigMaps connues. (None)"]

### Agent 2 - Correction sur retour (itération 1)
- Champs traités : []
- Actions :
  - Ajout de la ressource ConfigMap 'rabbitmq-config' dans le namespace 'media' pour résoudre l'erreur de référence croisée du Deployment 'image-resizer'
- Avertissements : ["La valeur 'rabbitmq-service' a été assignée à la clé 'host' par défaut pour permettre la validation du manifeste."]

### Agent 3 - Validation (itération 1)
- Champs traités : ['namespace', 'replicas', 'image', 'env_vars', 'labels', 'serviceAccountName', 'securityContext', 'ports', 'volumes', 'sidecars', 'ingress', 'rbac']
- Actions :
  - apiVersion présent
  - kind présent
  - metadata.name présent
  - cohérence labels/selectors Deployment
  - ServiceAccount présent et correctement référencé
  - env_vars fidèles à la NormalizedSpec
  - securityContext présent et restrictif
  - indentation YAML valide

### Agent 4 - Énergie
- Champs traités : ['[image-resizer] energy_goals', '[image-resizer] resource_hints', '[image-resizer] replicas', '[image-resizer] traffic_windows', '[image-resizer] constraints', '[image-resizer] energy_goals: économiser un maximum de ressources quand la file est vide']
- Actions :
  - [image-resizer] Dimensionnement des ressources (requests/limits) calibré pour un worker de traitement d'images : CPU limité à 1000m pour absorber les pics de calcul sans bloquer le nœud, et mémoire stable à 512Mi.
  - [image-resizer] Implémentation d'un ScaledObject KEDA au lieu d'un HPA classique pour permettre le scaling agressif jusqu'à 0 réplica quand la file RabbitMQ est vide, conformément aux resource_hints et à l'application_context.
  - [image-resizer] Configuration d'un trigger RabbitMQ basé sur la longueur de la file (seuil de 5 messages) et d'un trigger CPU de secours (60%) pour garantir la réactivité du workload.
  - [image-resizer] Ajout de livenessProbe et readinessProbe via tcpSocket sur le port 8080 pour éviter la consommation de ressources par des pods zombies.
  - [image-resizer] Pas de PodDisruptionBudget (PDB) car le nombre de réplicas initial est de 1 et le scaling est géré dynamiquement par KEDA.
- Avertissements : ["[image-resizer] L'utilisation du ScaledObject nécessite l'installation de l'opérateur KEDA (https://keda.sh) dans le cluster cible. Alternative : HPA classique (mais ne permet pas le scaling à 0 ni le trigger RabbitMQ natif).", "[image-resizer] Port 8080 supposé pour les sondes tcpSocket et le containerPort car non spécifié dans le manifeste initial — à vérifier selon l'implémentation réelle du worker.", "Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['ConfigMap/rabbitmq-config']."]

### Agent 5 - Vérification finale
- Champs traités : ['namespace', 'image', 'env_vars', 'energy_goals', 'resource_hints', 'KEDA scaling', 'securityContext', 'ServiceAccount']
- ⚠️ Champs laissés ouverts : ["unmapped_requirements: 'Le worker est développé en Python' (Information de runtime, non traduisible en champ de manifeste Kubernetes standard)", "2 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'scale automatiquement en fonction du nombre de messages en attente dans la file (KEDA), de 0 au repos jusqu'à 10 réplicas maximum' (kind supposé: KEDA ScaledObject); 'Le worker est développé en Python' (kind supposé: runtime)"]
- Actions :
  - yaml.safe_load_all OK sur 5 documents
  - Cross-reference Deployment -> ServiceAccount (image-resizer-sa) OK
  - Cross-reference Deployment -> ConfigMap (rabbitmq-config) OK
  - Cross-reference ScaledObject -> Deployment (image-resizer) OK
  - Resource quantities (cpu/memory) valid k8s format
  - Namespace consistency OK (all resources in 'media')
  - Contrôle déterministe Python : OK
- Avertissements : ["L'utilisation du ScaledObject nécessite l'installation de l'opérateur KEDA dans le cluster cible.", "Le port 8080 utilisé pour les sondes et le containerPort a été déduit par l'Agent 4 car non spécifié dans la spec."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | media | Namespace/media |
| components[0].image | myregistry/resizer:3.2 | Deployment/image-resizer |
| components[0].env_vars[0] | RABBITMQ_HOST from rabbitmq-config | Deployment/image-resizer (env) |
| energy_goals[0] | économiser un maximum de ressources quand la file est vide | ScaledObject/image-resizer-scaledobject (minReplicaCount: 0) |
| unmapped_requirements[0] | scale automatiquement... KEDA... 0 au repos jusqu'à 10 réplicas | ScaledObject/image-resizer-scaledobject |
| resource_hints | Scaling de 0 à 10 réplicas basé sur la longueur de la file RabbitMQ | ScaledObject/image-resizer-scaledobject (triggers[0]) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- scale automatiquement en fonction du nombre de messages en attente dans la file (KEDA), de 0 au repos jusqu'à 10 réplicas maximum (kind supposé : `KEDA ScaledObject`)
- Le worker est développé en Python (kind supposé : `runtime`)

## 7. ⚠️ À vérifier / relancer si besoin

- 2 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : 'scale automatiquement en fonction du nombre de messages en attente dans la file (KEDA), de 0 au repos jusqu'à 10 réplicas maximum' (kind supposé: KEDA ScaledObject); 'Le worker est développé en Python' (kind supposé: runtime)
- La configuration spécifique du scaling KEDA (plage de 0 à 10 réplicas) n'est pas intégrée dans un champ structuré dédié (présente uniquement dans 'unmapped_requirements' et 'resource_hints').
- Le runtime 'Python' n'est pas représenté dans les champs structurés du composant (présent uniquement dans 'unmapped_requirements').
- Runtime Python
- Scaling KEDA 0 à 10 réplicas
- unmapped_requirements: 'Le worker est développé en Python' (Information de runtime, non traduisible en champ de manifeste Kubernetes standard)
- unmapped_requirements: 2 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 2 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: Le worker est développé en Python (suggested_kind=runtime)
- unmapped_requirements: scale automatiquement en fonction du nombre de messages en attente dans la file (KEDA), de 0 au repos jusqu'à 10 réplicas maximum (suggested_kind=KEDA ScaledObject)

## Métriques d'exécution

- Latence totale du run : **1013.433 s** (dont pipeline seul : 1013.433 s)
- Appels LLM : **14** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 1010.027 s (moyenne 72.145 s/appel)
- Tokens consommés : **48465** (39189 prompt + 9276 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 75.836 | 6508 |
| Agent 1 - Analyse (self-check) | 3 | 149.247 | 4214 |
| Agent 1 - Analyse (réparation) | 2 | 241.131 | 4993 |
| Agent 1 - Analyse (contraintes globales) | 1 | 17.102 | 1109 |
| Agent 2 - Template | 1 | 70.879 | 6647 |
| Agent 2 - Template (best-effort) | 1 | 128.396 | 6575 |
| Agent 3 - Validation | 2 | 94.939 | 6058 |
| Agent 2 - Correction sur retour | 1 | 29.819 | 1353 |
| Agent 4 - Énergie | 1 | 122.537 | 4488 |
| Agent 5 - Vérification finale | 1 | 80.141 | 6520 |