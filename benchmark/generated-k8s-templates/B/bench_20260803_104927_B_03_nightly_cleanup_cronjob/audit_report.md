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
  - `components[0].volumes[0].mount_path` : Quel est le chemin de montage exact dans le conteneur pour le volume 'shared-logs' ? → hypothèse retenue : */var/log/shared* (confiance medium)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[log-cleanup]']
- Actions :
  - Extraction initiale + 1 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ["Quel est le chemin de montage exact dans le conteneur pour le volume 'shared-logs' ?"]

### Agent 2 - Template
- Champs traités : ['namespace', "[log-cleanup] component_name: utilisé pour metadata.name ('log-cleanup')", "[log-cleanup] namespace: défini à 'ops'", '[log-cleanup] workload_type: généré en tant que CronJob (batch/v1)', "[log-cleanup] cron_schedule: configuré à '0 3 * * *' dans spec.schedule", "[log-cleanup] image: 'myregistry/cleanup-tool:1.0' dans le conteneur principal", '[log-cleanup] replicas: 1 (traité dans la logique du CronJob)', '[log-cleanup] labels: app=log-cleanup appliqués aux métadonnées et aux pods', '[log-cleanup] ports: aucun port demandé, aucun Service généré', "[log-cleanup] env_vars: aucune variable d'environnement configurée", "[log-cleanup] volumes: PVC 'shared-logs' généré et monté sur '/var/log/shared'", '[log-cleanup] sidecars: aucun sidecar demandé', '[log-cleanup] depends_on: aucune dépendance déclarée', '[log-cleanup] security_requirements: hardening par défaut appliqué sur le Pod et le conteneur', '[log-cleanup] observability_requirements: aucune exigence spécifiée', '[log-cleanup] ingress: aucun Ingress configuré (ingress=None)', "[log-cleanup] rbac: rbac.enabled=False, ServiceAccount 'log-cleanup-sa' créé selon le principe de moindre privilège", '[log-cleanup] service_mesh_routing: aucune règle de routage demandée', '[log-cleanup] observability_style: annotations par défaut (aucune métrique configurée)', '[log-cleanup] config_maps: aucune ConfigMap demandée', '[log-cleanup] network_policy: aucune NetworkPolicy demandée', '[log-cleanup] deployment_strategy: aucun déploiement progressif demandé', '[log-cleanup] security_requirements: Hardening de sécurité par défaut appliqué : runAsNonRoot=true, allowPrivilegeEscalation=false, readOnlyRootFilesystem=true, capabilities drop ALL, seccompProfile RuntimeDefault.', '[log-cleanup] observability_requirements: Aucune exigence particulière spécifiée.', '[log-cleanup] ingress: Aucune exposition externe demandée.', "[log-cleanup] rbac: ServiceAccount dédié 'log-cleanup-sa' créé sans privilèges API supplémentaires (rbac.enabled=false)."]
- ⚠️ Champs laissés ouverts : ["[log-cleanup] resources.requests/limits: laissé à la charge de l'Agent 4 (dimensionnement)", "[log-cleanup] hpa/vpa: non applicable pour CronJob / laissé à l'Agent 4"]
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'ops' généré (une seule fois, déterministe)
  - [log-cleanup] PersistentVolumeClaim externe généré pour le stockage persistant demandé
  - [log-cleanup] CronJob.spec.schedule = '0 3 * * *'
- Avertissements : ["[log-cleanup] Taille non spécifiée pour le PVC 'shared-logs', valeur par défaut '1Gi' utilisée."]

### Agent 3 - Validation
- Champs traités : ['namespace', 'architecture_type', 'components.component_name', 'components.workload_type', 'components.image', 'components.cron_schedule', 'components.volumes', 'components.rbac', 'components.sidecars', 'components.ports', 'components.env_vars', 'components.ingress']
- Actions :
  - apiVersion et kind valides pour chaque ressource (Namespace, ServiceAccount, PVC, CronJob)
  - Namespace 'ops' appliqué de manière cohérente
  - CronJob schedule '0 3 * * *' aligné avec la spec
  - PersistentVolumeClaim 'shared-logs' correctement déclaré et référencé dans spec.template.spec.volumes
  - ServiceAccount 'log-cleanup-sa' présent et associé au CronJob
  - Image du conteneur conforme à la NormalizedSpec ('myregistry/cleanup-tool:1.0')
  - SecurityContext et profils de sécurité valides et bien placés

### Agent 4 - Énergie
- Champs traités : ['[log-cleanup] workload_type', '[log-cleanup] replicas', '[log-cleanup] resource_hints', '[log-cleanup] traffic_windows', '[log-cleanup] constraints', '[log-cleanup] energy_goals']
- Actions :
  - [log-cleanup] workload_type='CronJob' : pas de HPA/ScaledObject généré (non applicable), uniquement dimensionnement resources.requests/limits.
  - [log-cleanup] Dimensionnement prudent des ressources (requests: 50m CPU, 64Mi mémoire ; limits: 200m CPU, 128Mi mémoire) adapté à un job de nettoyage de logs en l'absence de resource_hints explicites.
  - [log-cleanup] Ajout des limites d'exécution activeDeadlineSeconds=900 (15 min) et backoffLimit=2 dans la spec du job pour éviter la surconsommation de ressources en cas de blocage ou d'échecs répétés.
  - [log-cleanup] Absence de HPA/ScaledObject volontaire : le type de workload est un CronJob (pas de réplicas permanents à scaler).
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['PersistentVolumeClaim/shared-logs']."]

### Agent 5 - Vérification finale
- Champs traités : ['architecture_type', 'namespace', 'components[0].component_name', 'components[0].workload_type', 'components[0].image', 'components[0].cron_schedule', 'components[0].volumes', 'components[0].constraints', 'components[0].rbac', 'components[0].security_requirements', 'components[0].resource_hints']
- Actions :
  - yaml.safe_load_all OK sur 4 documents (ServiceAccount, CronJob, Namespace, PersistentVolumeClaim)
  - Contraintes de types k8s valide : cpu ('50m', '200m'), memory ('64Mi', '128Mi'), storage ('1Gi')
  - Types entiers valides pour activeDeadlineSeconds (900) et backoffLimit (2)
  - Nommage et cohérence des espaces de noms (namespace: ops) vérifiés sur toutes les ressources
  - Référence croisée du ServiceAccount 'log-cleanup-sa' valide dans le CronJob
  - Référence croisée du PVC 'shared-logs' valide dans spec.template.spec.volumes
  - Contrôle déterministe Python : OK
- Avertissements : ["Hypothèse retenue pour la taille par défaut du PVC : '1Gi' (non spécifiée dans la requête utilisateur).", "Hypothèse retenue pour le chemin de montage du volume partagé : '/var/log/shared'."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | ops | manifest (Namespace metadata.name=ops & namespace=ops sur toutes les ressources) |
| components[0].component_name | log-cleanup | manifest (CronJob metadata.name=log-cleanup) |
| components[0].workload_type | CronJob | manifest (CronJob apiVersion=batch/v1, kind=CronJob) |
| components[0].cron_schedule | 0 3 * * * | manifest (CronJob spec.schedule='0 3 * * *') |
| components[0].image | myregistry/cleanup-tool:1.0 | manifest (CronJob containers[0].image) |
| components[0].constraints[0] | Durée maximale d'exécution : 15 minutes | manifest (CronJob spec.jobTemplate.spec.activeDeadlineSeconds=900) |
| components[0].constraints[1] | Nombre maximum de tentatives : 2 | manifest (CronJob spec.jobTemplate.spec.backoffLimit=2) |
| components[0].volumes[0] | shared-logs (PVC, mountPath=/var/log/shared) | manifest (PVC name=shared-logs + volumeMounts mountPath=/var/log/shared) |
| components[0].rbac | enabled=False (ServiceAccount dédié) | manifest (ServiceAccount metadata.name=log-cleanup-sa) |

## 7. ⚠️ À vérifier / relancer si besoin

- [log-cleanup] hpa/vpa: non applicable pour CronJob / laissé à l'Agent 4
- [log-cleanup] resources.requests/limits: laissé à la charge de l'Agent 4 (dimensionnement)

## Métriques d'exécution

- Latence totale du run : **325.904 s** (dont pipeline seul : 325.904 s)
- Appels LLM : **16** (7 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 321.479 s (moyenne 20.092 s/appel)
- Tokens consommés : **28804** (22496 prompt + 6308 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 2 (1 échoué(s)) | 39.139 | 5411 |
| Agent 1 - Analyse (self-check) | 2 | 63.402 | 2360 |
| Agent 1 - Analyse (réparation) | 1 | 36.081 | 1921 |
| Agent 1 - Analyse (réparation schéma) | 1 | 25.013 | 2071 |
| Agent 2 - Template | 2 (1 échoué(s)) | 60.225 | 6755 |
| Agent 3 - Validation | 1 | 16.984 | 2425 |
| Agent 4 - Énergie | 4 (3 échoué(s)) | 57.319 | 2896 |
| Agent 5 - Vérification finale | 3 (2 échoué(s)) | 23.316 | 4965 |