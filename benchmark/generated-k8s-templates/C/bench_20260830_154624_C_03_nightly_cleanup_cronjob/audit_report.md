# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Crée une tâche planifiée "log-cleanup" (image myregistry/cleanup-tool:1.0, namespace "ops") qui s'exécute tous les jours à 3h du matin pour purger les logs de plus de 30 jours sur un volume partagé "shared-logs" (PVC existant, montage en lecture-écriture). Pas besoin de port réseau. La tâche doit s'arrêter automatiquement si elle dépasse 15 minutes d'exécution, et ne pas relancer plus de 2 tentatives en cas d'échec.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `log-cleanup` (CronJob)

- Auto-check réussi : **True**
- Tentatives de réparation internes : 2
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].volumes[0].mount_path` : Quel est le chemin de montage exact pour le volume shared-logs ? → hypothèse retenue : */logs* (confiance medium)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[log-cleanup]']
- Actions :
  - Extraction initiale + 2 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : aucune détectée
- Avertissements : ['Quel est le chemin de montage exact pour le volume shared-logs ?']

### Agent 2 - Template
- Champs traités : ['namespace', '[log-cleanup] component_name', '[log-cleanup] workload_type', '[log-cleanup] image', '[log-cleanup] cron_schedule', '[log-cleanup] volumes: PVC généré séparément pour CronJob', '[log-cleanup] rbac: ServiceAccount créé, pas de Role/Binding', '[log-cleanup] security_requirements: hardening par défaut appliqué', '[log-cleanup] observability_requirements: aucun demandé', '[log-cleanup] ingress: aucun demandé', '[log-cleanup] service_mesh_routing: aucun demandé', '[log-cleanup] config_maps: aucune demandée', '[log-cleanup] network_policy: aucune demandée', '[log-cleanup] deployment_strategy: non applicable pour CronJob', '[log-cleanup] namespace', '[log-cleanup] security_requirements: Application du securityContext durci : runAsNonRoot, allowPrivilegeEscalation=false, readOnlyRootFilesystem=true, capabilities.drop=[ALL], seccompProfile=RuntimeDefault', '[log-cleanup] observability_requirements: Aucune exigence spécifiée', '[log-cleanup] ingress: Aucun ingress demandé', '[log-cleanup] rbac: Création du ServiceAccount dédié log-cleanup-sa']
- ⚠️ Champs laissés ouverts : ["[log-cleanup] replicas: non applicable pour la définition d'un CronJob (géré par le contrôleur de job)"]
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'ops' généré (une seule fois, déterministe)
  - [log-cleanup] PersistentVolumeClaim externe généré pour le stockage persistant demandé
  - [log-cleanup] CronJob.spec.schedule = '0 3 * * *'
- Avertissements : ["[log-cleanup] Taille du PVC 'shared-logs' supposée à '1Gi' car non spécifiée dans la spec."]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'component_name', 'workload_type', 'image', 'volumes', 'cron_schedule', 'rbac.enabled']
- Actions :
  - apiVersion présent
  - kind présent
  - metadata.name présent
  - cohérence ServiceAccount/CronJob
  - cohérence PVC/CronJob
  - schedule CronJob valide et fidèle à la spec
  - structure YAML valide
  - ServiceAccount présent malgré rbac.enabled=false

### Agent 4 - Énergie
- Champs traités : ['[log-cleanup] energy_goals', '[log-cleanup] resource_hints', '[log-cleanup] traffic_windows', '[log-cleanup] constraints', '[log-cleanup] workload_type', '[log-cleanup] replicas']
- Actions :
  - [log-cleanup] workload_type='CronJob' : pas de HPA/ScaledObject généré (non applicable), uniquement dimensionnement resources.requests/limits.
  - [log-cleanup] Dimensionnement minimal des ressources (requests: 100m/128Mi, limits: 200m/256Mi) basé sur l'application_context (tâche batch ponctuelle de nettoyage), évitant ainsi le sur-provisionnement.
  - [log-cleanup] Pas de HPA ni de ScaledObject générés car le workload_type est 'CronJob', ce qui rend le scaling horizontal non applicable.
  - [log-cleanup] Pas de PodDisruptionBudget (PDB) car replicas=1 et le profil n'exige pas de disponibilité continue.
  - [log-cleanup] Configuration de activeDeadlineSeconds=900 pour répondre à la contrainte d'arrêt automatique après 15 minutes, évitant la consommation inutile de ressources par des pods zombies.
  - [log-cleanup] Configuration de backoffLimit=2 pour limiter le nombre de tentatives en cas d'échec selon les contraintes fournies.
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['PersistentVolumeClaim/shared-logs']."]

### Agent 5 - Vérification finale
- Champs traités : ['namespace', 'cron_schedule', 'constraints', 'volumes', 'image', 'security_requirements']
- Actions :
  - yaml.safe_load_all OK sur 4 documents
  - Types de ressources k8s validés (CronJob, ServiceAccount, Namespace, PVC)
  - Quantités de ressources (cpu: 100m, memory: 128Mi) syntaxiquement correctes
  - Références croisées validées : CronJob -> ServiceAccount (log-cleanup-sa) OK
  - Références croisées validées : CronJob -> PVC (shared-logs) OK
  - Cohérence des namespaces (ops) sur tous les documents OK
  - Contrôle déterministe Python : OK

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| components[0].cron_schedule | 0 3 * * * | manifest (CronJob/log-cleanup.spec.schedule) |
| components[0].constraints[0] | S'arrêter automatiquement si l'exécution dépasse 15 minutes | manifest (CronJob/log-cleanup.spec.jobTemplate.spec.template.spec.activeDeadlineSeconds = 900) |
| components[0].constraints[1] | Ne pas relancer plus de 2 tentatives en cas d'échec | manifest (CronJob/log-cleanup.spec.jobTemplate.spec.backoffLimit = 2) |
| components[0].volumes[0] | shared-logs | manifest (PVC/shared-logs et CronJob/log-cleanup.spec.jobTemplate.spec.template.spec.volumes) |
| components[0].image | myregistry/cleanup-tool:1.0 | manifest (CronJob/log-cleanup.spec.jobTemplate.spec.template.spec.containers[0].image) |

## 7. ⚠️ À vérifier / relancer si besoin

- [log-cleanup] replicas: non applicable pour la définition d'un CronJob (géré par le contrôleur de job)

## Métriques d'exécution

- Latence totale du run : **650.566 s** (dont pipeline seul : 650.566 s)
- Appels LLM : **11** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 647.553 s (moyenne 58.868 s/appel)
- Tokens consommés : **33602** (27588 prompt + 6014 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 85.25 | 6281 |
| Agent 1 - Analyse (self-check) | 3 | 78.794 | 3589 |
| Agent 1 - Analyse (réparation) | 2 | 239.581 | 4212 |
| Agent 1 - Analyse (contraintes globales) | 1 | 17.311 | 1095 |
| Agent 2 - Template | 1 | 69.386 | 6556 |
| Agent 3 - Validation | 1 | 45.512 | 2964 |
| Agent 4 - Énergie | 1 | 44.98 | 4042 |
| Agent 5 - Vérification finale | 1 | 66.74 | 4863 |