# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie un site web statique appelé "landing-page" (image nginx:1.27, namespace "web"), servi sur le port 80. Un seul réplica suffit, pas de base de données ni de stockage persistant. Accessible depuis internet via le domaine "www.exemple.com", sans TLS pour l'instant.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `landing-page` (Deployment)

- Auto-check réussi : **True**
- Tentatives de réparation internes : 0
- Hypothèses faites faute de précision de l'utilisateur :
  - `workload_type` : Le type de workload n'est pas spécifié, s'agit-il d'un Deployment standard ? → hypothèse retenue : *Deployment* (confiance high)
  - `ingress.path` : Le chemin d'accès pour le domaine n'est pas précisé. → hypothèse retenue : */* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[landing-page]']
- Actions :
  - Extraction initiale + 0 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : aucune détectée
- Avertissements : ["Le type de workload n'est pas spécifié, s'agit-il d'un Deployment standard ?", "Le chemin d'accès pour le domaine n'est pas précisé."]

### Agent 2 - Template
- Champs traités : ['namespace', '[landing-page] component_name', '[landing-page] workload_type', '[landing-page] image', '[landing-page] replicas', '[landing-page] labels', '[landing-page] ports', '[landing-page] env_vars: aucun', '[landing-page] volumes: aucun', '[landing-page] sidecars: aucun', '[landing-page] depends_on: aucun', '[landing-page] security_requirements: hardening par défaut', '[landing-page] observability_requirements: aucun', '[landing-page] ingress', '[landing-page] rbac: ServiceAccount uniquement', '[landing-page] service_mesh_routing: aucun', '[landing-page] observability_style', '[landing-page] cron_schedule: non applicable', '[landing-page] config_maps: aucun', '[landing-page] network_policy: aucun', '[landing-page] deployment_strategy: aucun', '[landing-page] namespace', '[landing-page] security_requirements: Application du securityContext durci par défaut (runAsNonRoot, allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities.drop: ALL, seccompProfile: RuntimeDefault)', '[landing-page] observability_requirements: observability_style: annotations (aucune exigence spécifique)', '[landing-page] ingress: Création de la ressource Ingress pour le host www.exemple.com', '[landing-page] rbac: Création du ServiceAccount landing-page-sa']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'web' généré (une seule fois, déterministe)
  - [landing-page] Ingress généré (host=www.exemple.com)
- Avertissements : ['[landing-page] readOnlyRootFilesystem: true appliqué par défaut ; vérifier si nginx nécessite des accès en écriture (ex: /var/cache/nginx) et ajouter des volumes si nécessaire.']

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'replicas', 'image', 'ports', 'ingress', 'serviceAccount', 'labels', 'env_vars', 'volumes', 'sidecars']
- Actions :
  - apiVersion présent
  - kind présent
  - metadata.name présent
  - spec présent
  - Cohérence labels Deployment/Service
  - Référence Ingress -> Service correcte
  - Présence du ServiceAccount dédié
  - Indentation YAML valide
  - SecurityContext conforme aux bonnes pratiques

### Agent 4 - Énergie
- Champs traités : ['[landing-page] energy_goals', '[landing-page] resource_hints', '[landing-page] traffic_windows', '[landing-page] constraints', '[landing-page] replicas']
- Actions :
  - [landing-page] Dimensionnement minimal des ressources (CPU 50m/100m, Mem 64Mi/128Mi) car l'application_context indique un site statique à trafic minimal.
  - [landing-page] Pas de HPA — l'application_context indique un trafic minimal sans besoin de scaling, ajouter un HPA ici serait du sur-provisionnement inutile.
  - [landing-page] Pas de PDB — replicas=1 et faible criticité selon l'application_context.
  - [landing-page] Ajout de sondes livenessProbe et readinessProbe via tcpSocket sur le port 80 pour éviter la consommation de ressources par des pods zombies.

### Agent 5 - Vérification finale
- Champs traités : ['architecture_type', 'namespace', 'components[0].component_name', 'components[0].workload_type', 'components[0].image', 'components[0].replicas', 'components[0].labels', 'components[0].ports', 'components[0].ingress', 'components[0].rbac', 'global_constraints', 'unmapped_requirements']
- Actions :
  - yaml.safe_load_all OK sur 5 documents
  - Validation des types de ressources k8s : OK
  - Validation des quantités CPU/Mem (50m, 64Mi, etc.) : OK
  - Cohérence Service selector -> Deployment labels : OK
  - Cohérence Ingress backend -> Service name/port : OK
  - Cohérence Deployment serviceAccountName -> ServiceAccount name : OK
  - Contrôle déterministe Python : OK
- Avertissements : ["Le champ readOnlyRootFilesystem: true est appliqué par défaut pour le hardening ; si nginx nécessite d'écrire dans /var/cache/nginx, un volume emptyDir devra être ajouté."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | web | manifest (Namespace, Deployment, Service, Ingress, ServiceAccount) |
| components[0].component_name | landing-page | manifest (Deployment/Service/Ingress name) |
| components[0].image | nginx:1.27 | manifest (Deployment container image) |
| components[0].replicas | 1 | manifest (Deployment spec.replicas) |
| components[0].ingress.host | www.exemple.com | manifest (Ingress spec.rules[0].host) |
| application_context | trafic minimal | Agent 4 Report (Dimensionnement CPU 50m/100m, Mem 64Mi/128Mi) |
| components[0].ports[0].container_port | 80 | manifest (Deployment containerPort, Service targetPort, Ingress port) |

## 7. Aucun point ouvert détecté ✅


## Métriques d'exécution

- Latence totale du run : **370.276 s** (dont pipeline seul : 370.276 s)
- Appels LLM : **7** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 367.533 s (moyenne 52.505 s/appel)
- Tokens consommés : **27672** (23164 prompt + 4508 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 58.294 | 6192 |
| Agent 1 - Analyse (self-check) | 1 | 15.92 | 1006 |
| Agent 1 - Analyse (contraintes globales) | 1 | 14.461 | 1047 |
| Agent 2 - Template | 1 | 105.027 | 6743 |
| Agent 3 - Validation | 1 | 52.119 | 3227 |
| Agent 4 - Énergie | 1 | 52.838 | 4310 |
| Agent 5 - Vérification finale | 1 | 68.874 | 5147 |