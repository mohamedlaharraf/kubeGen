# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Crée une tâche planifiée "log-cleanup" (image myregistry/cleanup-tool:1.0, namespace "ops") qui s'exécute tous les jours à 3h du matin pour purger les logs de plus de 30 jours sur un volume partagé "shared-logs" (PVC existant, montage en lecture-écriture). Pas besoin de port réseau. La tâche doit s'arrêter automatiquement si elle dépasse 15 minutes d'exécution, et ne pas relancer plus de 2 tentatives en cas d'échec.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `log-cleanup` (CronJob)

## 3. Auto-vérification Agent 1

- Auto-check réussi : **True**
- Tentatives de réparation internes : 1
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].volumes[0].mount_path` : Quel est le chemin de montage requis pour le volume shared-logs ? → hypothèse retenue : */logs* (confiance medium)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[log-cleanup]']
- Actions :
  - Extraction initiale + 1 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
- Avertissements : ['Quel est le chemin de montage requis pour le volume shared-logs ?']

### Agent 2 - Template
- Champs traités : ['namespace', '[log-cleanup] component_name', '[log-cleanup] workload_type', '[log-cleanup] image', '[log-cleanup] cron_schedule', '[log-cleanup] volumes: PVC généré séparément pour CronJob', '[log-cleanup] sidecars: aucun demandé', '[log-cleanup] depends_on: aucun', '[log-cleanup] security_requirements: application du hardening par défaut', '[log-cleanup] observability_requirements: aucun', '[log-cleanup] ingress: aucun', '[log-cleanup] rbac: ServiceAccount créé, pas de Role/Binding', '[log-cleanup] service_mesh_routing: aucun', '[log-cleanup] observability_style: annotations (rien à configurer sans requirements)', '[log-cleanup] config_maps: aucune', '[log-cleanup] network_policy: aucune', '[log-cleanup] deployment_strategy: non applicable pour CronJob', '[log-cleanup] namespace', '[log-cleanup] security_requirements: Application du hardening par défaut : runAsNonRoot, allowPrivilegeEscalation=false, readOnlyRootFilesystem=true, capabilities.drop=[ALL], seccompProfile=RuntimeDefault', '[log-cleanup] observability_requirements: Aucune exigence spécifiée', '[log-cleanup] ingress: Aucun ingress demandé', '[log-cleanup] rbac: Création du ServiceAccount dédié log-cleanup-sa']
- ⚠️ Champs laissés ouverts : ['[log-cleanup] replicas: non pertinent pour un CronJob', '[log-cleanup] labels: vide', '[log-cleanup] ports: vide', '[log-cleanup] env_vars: vide']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'ops' généré (une seule fois, déterministe)
  - [log-cleanup] PersistentVolumeClaim externe généré pour le stockage persistant demandé
  - [log-cleanup] CronJob.spec.schedule = '0 3 * * *'
- Avertissements : ["[log-cleanup] Taille du PVC 'shared-logs-volume' non spécifiée, supposée à '1Gi' par défaut.", "[log-cleanup] Le root filesystem est configuré en lecture seule (hardening) ; vérifiez que l'outil de nettoyage n'a pas besoin d'écrire dans des répertoires temporaires en dehors de /logs."]

### Agent 3 - Validation
- Champs traités : ['namespace', 'workload_type', 'image', 'cron_schedule', 'volumes', 'serviceAccount', 'rbac']
- Actions :
  - apiVersion present
  - kind present
  - metadata.name present
  - CronJob schedule matches cron_schedule
  - PVC name and volume claimName are consistent
  - ServiceAccount present despite rbac.enabled=false
  - Namespace consistency across all resources
  - YAML indentation and syntax valid

### Agent 4 - Énergie
- Champs traités : ['[log-cleanup] resource_hints', '[log-cleanup] constraints', '[log-cleanup] workload_type', '[log-cleanup] energy_goals', '[log-cleanup] traffic_windows', "[log-cleanup] energy_goals: Optimisation du dimensionnement des ressources pour limiter l'empreinte carbone lors de l'exécution périodique."]
- Actions :
  - [log-cleanup] workload_type='CronJob' : pas de HPA/ScaledObject généré (non applicable), uniquement dimensionnement resources.requests/limits.
  - [log-cleanup] Définition de resources.requests (100m CPU, 128Mi RAM) et resources.limits (200m CPU, 256Mi RAM) : valeurs prudentes pour un outil de nettoyage de logs, visant à éviter la sur-allocation.
  - [log-cleanup] Ajout de activeDeadlineSeconds: 900 pour forcer l'arrêt du job s'il dépasse 15 minutes, évitant ainsi la consommation inutile de ressources en cas de blocage.
  - [log-cleanup] Ajout de backoffLimit: 2 pour limiter les tentatives de redémarrage en cas d'échec, réduisant le gaspillage énergétique lié aux crash-loops.
  - [log-cleanup] Absence de HPA/KEDA car le workload_type est 'CronJob' (non applicable).
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['PersistentVolumeClaim/shared-logs-volume']."]

### Agent 5 - Vérification finale
- Champs traités : ['architecture_type', 'namespace', 'component_name', 'workload_type', 'image', 'cron_schedule', 'volumes', 'constraints', 'energy_goals']
- Actions :
  - yaml.safe_load_all OK on 4 documents
  - Cross-reference CronJob -> ServiceAccount (log-cleanup-sa) OK
  - Cross-reference CronJob -> PVC (shared-logs-volume) OK
  - Resource quantities (cpu: 100m, memory: 128Mi) valid k8s format
  - Namespace consistency (ops) across all resources OK
  - Contrôle déterministe Python : OK
- Avertissements : ["PVC storage size '1Gi' is a default assumption from Agent 2 as it was not specified in the NormalizedSpec."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | ops | manifest (Namespace, ServiceAccount, CronJob, PVC) |
| components[0].component_name | log-cleanup | manifest (CronJob name=log-cleanup) |
| components[0].workload_type | CronJob | manifest (Kind: CronJob) |
| components[0].image | myregistry/cleanup-tool:1.0 | manifest (CronJob container image) |
| components[0].cron_schedule | 0 3 * * * | manifest (CronJob spec.schedule) |
| components[0].volumes[0] | shared-logs-volume | manifest (PVC name=shared-logs-volume, CronJob volumeMount) |
| components[0].constraints[0] | activeDeadlineSeconds: 900 | manifest (CronJob spec.jobTemplate.spec.activeDeadlineSeconds) |
| components[0].constraints[1] | backoffLimit: 2 | manifest (CronJob spec.jobTemplate.spec.backoffLimit) |
| energy_goals | Optimisation dimensionnement | manifest (CronJob resources.requests/limits via Agent 4) |

## 7. ⚠️ À vérifier / relancer si besoin

- [log-cleanup] env_vars: vide
- [log-cleanup] labels: vide
- [log-cleanup] ports: vide
- [log-cleanup] replicas: non pertinent pour un CronJob

## Métriques d'exécution

- Latence totale du run : **452.401 s** (dont pipeline seul : 452.401 s)
- Appels LLM : **8** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 449.215 s (moyenne 56.152 s/appel)
- Tokens consommés : **25563** (20490 prompt + 5073 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 70.432 | 5362 |
| Agent 1 - Analyse (self-check) | 2 | 49.341 | 2255 |
| Agent 1 - Analyse (réparation) | 1 | 83.609 | 1998 |
| Agent 2 - Template | 1 | 79.914 | 6523 |
| Agent 3 - Validation | 1 | 51.062 | 2266 |
| Agent 4 - Énergie | 1 | 46.29 | 2833 |
| Agent 5 - Vérification finale | 1 | 68.565 | 4326 |