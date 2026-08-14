# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie un site web statique appelé "landing-page" (image nginx:1.27,
namespace "web"), servi sur le port 80. Un seul réplica suffit, pas de
base de données ni de stockage persistant. Accessible depuis internet
via le domaine "www.exemple.com", sans TLS pour l'instant.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `landing-page` (Deployment)

- Auto-check réussi : **True**
- Tentatives de réparation internes : 0

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[landing-page]']
- Actions :
  - Extraction initiale + 0 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : aucune détectée

### Agent 2 - Template
- Champs traités : ['namespace', '[landing-page] component_name: landing-page utilisé comme nom de ressource', '[landing-page] workload_type: Deployment généré avec succès', '[landing-page] image: nginx:1.27 positionnée', '[landing-page] replicas: 1 configuré', '[landing-page] labels: app=landing-page appliqués aux ressources', '[landing-page] ports: port http (80/TCP) exposé sur le conteneur et le Service', '[landing-page] namespace: web appliqué à toutes les ressources', '[landing-page] env_vars: aucune variable définie, rien à ajouter', '[landing-page] volumes: aucun volume PVC demandé, aucun volume rattaché', '[landing-page] sidecars: aucun sidecar défini, conteneur unique', '[landing-page] depends_on: aucune dépendance directe', '[landing-page] cron_schedule: non applicable pour un Deployment', '[landing-page] config_maps: aucune ConfigMap demandée', '[landing-page] network_policy: non demandée explicite', '[landing-page] deployment_strategy: stratégie par défaut Deployment utilisée', '[landing-page] security_requirements: Application des bonnes pratiques de sécurité par défaut (runAsNonRoot, capabilities.drop ALL, seccompProfile RuntimeDefault, allowPrivilegeEscalation false)', '[landing-page] security_requirements: Isolation via un ServiceAccount dédié (landing-page-sa)', "[landing-page] observability_requirements: Aucune exigence d'observabilité spécifique fournie dans observability_requirements", "[landing-page] ingress: Création de l'Ingress networking.k8s.io/v1 ciblant le Service landing-page sur le port 80", '[landing-page] ingress: Hôte configuré sur www.exemple.com et chemin / avec Prefix', '[landing-page] rbac: ServiceAccount landing-page-sa créé', '[landing-page] rbac: rbac.enabled est false : aucun Role/RoleBinding créé selon la politique de moindre privilège']
- ⚠️ Champs laissés ouverts : ["[landing-page] resources.requests/limits et HPA: à traiter par l'Agent 4", '[landing-page] TLS désactivé (tls=false), aucun certificat configuré']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'web' généré (une seule fois, déterministe)
  - [landing-page] Ingress généré (host=www.exemple.com)
- Avertissements : ["[landing-page] L'image nginx par défaut tente parfois d'écrire dans /var/cache/nginx ; readOnlyRootFilesystem n'a pas été forcé à true pour éviter un crash au démarrage sans volume temporaire tmpfs."]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'architecture_type', 'components', 'component_name', 'workload_type', 'image', 'replicas', 'labels', 'ports', 'env_vars', 'volumes', 'sidecars', 'security_requirements', 'ingress', 'rbac', 'observability_style', 'cron_schedule', 'global_constraints']
- Actions :
  - apiVersion et kind valides pour toutes les ressources
  - Coherence du namespace 'web' sur toutes les ressources
  - Labels et selectors alignes entre Deployment et Service
  - ServiceAccount correctement reference dans le PodSpec
  - Configuration Ingress alignee avec le Service backend et le port 80
  - Structure conforme a la NormalizedSpec

### Agent 4 - Énergie
- Champs traités : ['[landing-page] component_name', '[landing-page] workload_type', '[landing-page] replicas', '[landing-page] resource_hints', '[landing-page] energy_goals', '[landing-page] traffic_windows', '[landing-page] constraints', '[landing-page] energy_goals: Un seul réplica (empreinte énergétique minimale)']
- Actions :
  - [landing-page] Dimensionnement minimaliste des ressources (requests: 10m CPU / 16Mi mémoire, limits: 100m CPU / 32Mi mémoire) adapté à un site web statique nginx à faible trafic pour minimiser l'empreinte énergétique.
  - [landing-page] Absence de HPA : l'objectif énergétique explicite demande 'un seul réplica' et le composant est un site statique sans besoin de variation de charge dynamique, ajouter un HPA serait un sur-provisionnement inutile.
  - [landing-page] Absence de PodDisruptionBudget : non nécessaire pour un workload à réplica unique (replicas = 1) et à trafic minimal.
  - [landing-page] Ajout de livenessProbe et readinessProbe via tcpSocket sur le port 80 pour détecter et recycler les pods défaillants sans supposer d'endpoint HTTP particulier.

### Agent 5 - Vérification finale
- Champs traités : ['manifest_syntax_validation', 'k8s_types_and_units', 'cross_resource_references', 'traceability_matrix', 'global_constraints_check']
- Actions :
  - yaml.safe_load_all OK sur 5 documents (ServiceAccount, Deployment, Service, Ingress, Namespace)
  - Validation des types et quantites K8s OK (10m, 100m, 16Mi, 32Mi)
  - Coherence des labels/selectors OK (app=landing-page)
  - Coherence du ServiceAccount OK (landing-page-sa)
  - Coherence Ingress -> Service OK (landing-page:80)
  - Unicite du namespace OK (web)
  - Contrôle déterministe Python : OK

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | web | manifest (Namespace name=web + metadata.namespace sur tous les objets) |
| components[0].component_name | landing-page | manifest (Deployment nom=landing-page, Service nom=landing-page) |
| components[0].image | nginx:1.27 | manifest (Deployment container landing-page image=nginx:1.27) |
| components[0].replicas | 1 | manifest (Deployment spec.replicas=1) |
| components[0].ports[0] | 80/TCP | manifest (Deployment containerPort=80, Service port=80 targetPort=80) |
| components[0].ingress | host=www.exemple.com, path=/, tls=false | manifest (Ingress landing-page-ingress host=www.exemple.com path=/ service.name=landing-page service.port=80) |
| components[0].energy_goals[0] | Un seul réplica (empreinte énergétique minimale) | manifest (Deployment spec.replicas=1, pas de HPA instancié) |
| components[0].resource_hints | Site web statique nginx à faible consommation de ressources | manifest (Deployment resources requests cpu=10m memory=16Mi, limits cpu=100m memory=32Mi) |

## 7. ⚠️ À vérifier / relancer si besoin

- [landing-page] TLS désactivé (tls=false), aucun certificat configuré
- [landing-page] resources.requests/limits et HPA: à traiter par l'Agent 4

## Métriques d'exécution

- Latence totale du run : **90.599 s** (dont pipeline seul : 90.599 s)
- Appels LLM : **10** (3 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 82.08 s (moyenne 8.208 s/appel)
- Tokens consommés : **28210** (23343 prompt + 4867 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 20.532 | 6086 |
| Agent 1 - Analyse (self-check) | 1 | 2.244 | 927 |
| Agent 1 - Analyse (contraintes globales) | 1 | 5.166 | 1047 |
| Agent 2 - Template | 1 | 11.233 | 6960 |
| Agent 3 - Validation | 2 (1 échoué(s)) | 17.856 | 3374 |
| Agent 4 - Énergie | 3 (2 échoué(s)) | 11.325 | 4350 |
| Agent 5 - Vérification finale | 1 | 13.724 | 5466 |