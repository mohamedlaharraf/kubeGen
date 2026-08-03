# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie un site web statique appelé "landing-page" (image nginx:1.27,
namespace "web"), servi sur le port 80. Un seul réplica suffit, pas de
base de données ni de stockage persistant. Accessible depuis internet
via le domaine "www.exemple.com", sans TLS pour l'instant.


## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `landing-page` (Deployment)

## 3. Auto-vérification Agent 1

- Auto-check réussi : **True**
- Tentatives de réparation internes : 0

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[landing-page]']
- Actions :
  - Extraction initiale + 0 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))

### Agent 2 - Template
- Champs traités : ['namespace', '[landing-page] component_name (nom du deployment, service, ingress, serviceaccount)', '[landing-page] workload_type (Deployment)', '[landing-page] image (nginx:1.27)', '[landing-page] replicas (1)', '[landing-page] labels (app: landing-page)', '[landing-page] ports (port 80 http exposé)', '[landing-page] env_vars (aucun demande)', '[landing-page] volumes (aucun demande)', '[landing-page] sidecars (aucun demande)', '[landing-page] depends_on (aucun)', '[landing-page] ingress (enabled, host www.exemple.com, path /)', '[landing-page] rbac (enabled=false, ServiceAccount dedie cree sans roles)', '[landing-page] namespace (web)', '[landing-page] config_maps (aucun)', '[landing-page] network_policy (non active)', '[landing-page] deployment_strategy (non active)', '[landing-page] cron_schedule (non applicable pour Deployment)', '[landing-page] security_requirements: Application de la posture de securite par defaut (runAsNonRoot, readOnlyRootFilesystem, drop ALL capabilities, RuntimeDefault seccompProfile)', '[landing-page] ingress: ingress.enabled=true', '[landing-page] ingress: ingress.host=www.exemple.com', '[landing-page] ingress: ingress.path=/', '[landing-page] ingress: ingress.api_style=ingress', '[landing-page] rbac: rbac.enabled=false (creation exclusive du ServiceAccount landing-page-sa sans privileges addionnels)']
- ⚠️ Champs laissés ouverts : ["[landing-page] resources.requests/limits (delegue a l'Agent 4)", "[landing-page] HPA / Autoscaling (delegue a l'Agent 4)"]
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'web' généré (une seule fois, déterministe)
  - [landing-page] Ingress généré (host=www.exemple.com)
- Avertissements : ["[landing-page] Conteneur configure avec readOnlyRootFilesystem: true par defaut. Nginx peut necessiter des volumes emptyDir sur /var/cache/nginx et /var/run si des erreurs d'ecriture surviennent au demarrage."]

### Agent 3 - Validation
- Champs traités : ['namespace', 'architecture_type', 'components[0].component_name', 'components[0].workload_type', 'components[0].image', 'components[0].replicas', 'components[0].labels', 'components[0].ports', 'components[0].env_vars', 'components[0].volumes', 'components[0].sidecars', 'components[0].ingress', 'components[0].rbac', 'components[0].observability_style', 'components[0].cron_schedule']
- Actions :
  - Présence et validité des champs apiVersion, kind, et metadata sur toutes les ressources
  - Cohérence du namespace 'web' sur l'ensemble des ressources
  - Correspondance stricte des selectors et labels entre Service et Deployment (app: landing-page)
  - Association correcte du ServiceAccount landing-page-sa dans le Deployment
  - Configuration Ingress pointant exactement sur le Service landing-page et le port 80
  - Conformité du conteneur (image nginx:1.27, port 80 TCP) avec la NormalizedSpec

### Agent 4 - Énergie
- Champs traités : ['[landing-page] resource_hints', '[landing-page] energy_goals', '[landing-page] traffic_windows', '[landing-page] constraints', '[landing-page] workload_type', '[landing-page] replicas']
- Actions :
  - [landing-page] Ajout des requêtes et limites de ressources prudentes (requests: cpu 50m, memory 64Mi / limits: cpu 200m, memory 128Mi) adaptées à un serveur web d'accueil léger.
  - [landing-page] Ajout d'un HorizontalPodAutoscaler (HPA) classique basé sur l'utilisation CPU (minReplicas: 1, maxReplicas: 5, cible: 70%) car aucune fenêtre temporelle spécifique n'a été demandée.
  - [landing-page] Ajout de sondes de santé livenessProbe et readinessProbe configurées en tcpSocket sur le port 80 pour éviter le gaspillage de ressources par des pods inactifs ou défaillants.

### Agent 5 - Vérification finale
- Champs traités : ['syntax_validation', 'cross_references_validation', 'traceability_matrix_construction', 'audit_fields_left_open']
- Actions :
  - yaml.safe_load_all OK sur 6 documents Kubernetes
  - Validation des types et quantites Kubernetes (50m, 200m, 64Mi, 128Mi)
  - Verification des references croisees : HPA/landing-page-hpa pointe correctement vers Deployment/landing-page
  - Verification du selector du Service landing-page aligne avec les labels du Pod (app=landing-page)
  - Verification du backend Ingress landing-page pointant vers Service/landing-page:80
  - Verification du ServiceAccount landing-page-sa reference dans le Pod spec
  - Coherence globale du namespace 'web' valide sur tous les documents
  - Contrôle déterministe Python : OK
- Avertissements : ["[landing-page] Conteneur configure avec readOnlyRootFilesystem: true par defaut. Nginx peut necessiter des volumes emptyDir sur /var/cache/nginx et /var/run si des erreurs d'ecriture surviennent au demarrage."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | web | manifest (Namespace/web + metadata.namespace sur toutes les ressources) |
| components[0].component_name | landing-page | manifest (Deployment, Service, Ingress, SA, HPA) |
| components[0].image | nginx:1.27 | manifest (Deployment spec.template.spec.containers[0].image) |
| components[0].replicas | 1 | manifest (Deployment spec.replicas=1, HPA minReplicas=1) |
| components[0].ports[0] | 80 (TCP, exposed) | manifest (Service port 80 -> Deployment containerPort 80) |
| components[0].ingress | host=www.exemple.com, path=/ | manifest (Ingress landing-page) |
| components[0].rbac | enabled=False | manifest (ServiceAccount landing-page-sa cree sans Roles/RoleBindings) |
| Agent 4 - Resources & Autoscaling | requests/limits CPU/RAM + HPA + Probes | manifest (Deployment resources/probes + HPA landing-page-hpa) |

## 7. ⚠️ À vérifier / relancer si besoin

- [landing-page] HPA / Autoscaling (delegue a l'Agent 4)
- [landing-page] resources.requests/limits (delegue a l'Agent 4)

## Métriques d'exécution

- Latence totale du run : **145.689 s** (dont pipeline seul : 145.689 s)
- Appels LLM : **10** (4 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 136.426 s (moyenne 13.643 s/appel)
- Tokens consommés : **24022** (18804 prompt + 5218 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 14.299 | 5194 |
| Agent 1 - Analyse (self-check) | 1 | 28.934 | 933 |
| Agent 2 - Template | 3 (2 échoué(s)) | 33.792 | 6752 |
| Agent 3 - Validation | 1 | 22.738 | 2760 |
| Agent 4 - Énergie | 1 | 14.753 | 3387 |
| Agent 5 - Vérification finale | 3 (2 échoué(s)) | 21.909 | 4996 |