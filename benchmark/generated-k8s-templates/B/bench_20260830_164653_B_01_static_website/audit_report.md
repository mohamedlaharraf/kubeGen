# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie un site web statique appelé "landing-page" (image nginx:1.27, namespace "web"), servi sur le port 80. Un seul réplica suffit, pas de base de données ni de stockage persistant. Accessible depuis internet via le domaine "www.exemple.com", sans TLS pour l'instant.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `landing-page` (Deployment)

## 3. Auto-vérification Agent 1

- Auto-check réussi : **True**
- Tentatives de réparation internes : 0
- Hypothèses faites faute de précision de l'utilisateur :
  - `ingress.path` : Le chemin d'accès spécifique n'est pas mentionné. → hypothèse retenue : *Utilisation du chemin racine '/'* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[landing-page]']
- Actions :
  - Extraction initiale + 0 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
- Avertissements : ["Le chemin d'accès spécifique n'est pas mentionné."]

### Agent 2 - Template
- Champs traités : ['namespace', '[landing-page] component_name: utilisé pour metadata.name et ServiceAccount', '[landing-page] workload_type: Deployment généré', '[landing-page] image: nginx:1.27 configurée', '[landing-page] replicas: 1 configuré', '[landing-page] labels: app: landing-page appliqué', '[landing-page] ports: port 80 configuré et Service créé car expose_service=true', '[landing-page] env_vars: aucun demandé, rien à faire', '[landing-page] volumes: aucun demandé, rien à faire', '[landing-page] sidecars: aucun demandé, rien à faire', '[landing-page] depends_on: aucun demandé, rien à faire', '[landing-page] security_requirements: vide, application du hardening par défaut', '[landing-page] observability_requirements: vide, aucune configuration ajoutée', '[landing-page] ingress: Ingress créé pour www.exemple.com, tls=false', '[landing-page] rbac: enabled=false, seul le ServiceAccount est créé', '[landing-page] service_mesh_routing: vide, rien à faire', '[landing-page] observability_style: annotations (mais aucune exigence de métriques fournie)', '[landing-page] cron_schedule: non applicable pour Deployment', '[landing-page] config_maps: vide, rien à faire', '[landing-page] network_policy: None, rien à faire', '[landing-page] deployment_strategy: None, Deployment standard utilisé', '[landing-page] namespace: web appliqué à toutes les ressources', '[landing-page] security_requirements: Application du hardening par défaut : runAsNonRoot: true, allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities.drop: [ALL], seccompProfile: RuntimeDefault', '[landing-page] observability_requirements: Aucune exigence fournie', '[landing-page] ingress: Création de la ressource Ingress avec host www.exemple.com et path /', '[landing-page] rbac: Création du ServiceAccount landing-page-sa']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'web' généré (une seule fois, déterministe)
  - [landing-page] Ingress généré (host=www.exemple.com)
- Avertissements : ["[landing-page] readOnlyRootFilesystem: true appliqué par défaut ; l'image nginx peut nécessiter des répertoires d'écriture (ex: /var/cache/nginx) pour fonctionner, ce qui n'a pas été spécifié dans les volumes."]

### Agent 3 - Validation
- Champs traités : ['namespace', 'replicas', 'image', 'ports', 'ingress', 'serviceAccount', 'labels', 'env_vars', 'volumes', 'sidecars']
- Actions :
  - apiVersion présent
  - kind présent
  - metadata.name présent
  - spec présent
  - Sélecteurs Deployment et Service alignés (app: landing-page)
  - Ingress référence correctement le Service landing-page sur le port 80
  - ServiceAccount présent malgré rbac.enabled=false
  - Indentation YAML valide
  - Types de champs corrects

### Agent 4 - Énergie
- Champs traités : ['[landing-page] energy_goals', '[landing-page] resource_hints', '[landing-page] traffic_windows', '[landing-page] constraints', '[landing-page] workload_type', '[landing-page] replicas', '[landing-page] energy_goals: Optimisation du dimensionnement des ressources pour éviter le gaspillage (over-provisioning)', "[landing-page] energy_goals: Mise en place d'un scaling automatique pour adapter la consommation à la charge réelle"]
- Actions :
  - [landing-page] Ajout de resources.requests (100m CPU, 128Mi RAM) et limits (500m CPU, 256Mi RAM) basées sur un profil Nginx standard pour optimiser la densité du nœud.
  - [landing-page] Création d'un HorizontalPodAutoscaler (HPA) avec un min de 1 et un max de 3 réplicas, ciblant 70% d'utilisation CPU pour réduire l'empreinte énergétique en période de faible trafic.
  - [landing-page] Ajout de livenessProbe et readinessProbe via tcpSocket sur le port 80 pour éviter le maintien de pods zombies consommant des ressources inutilement.
  - [landing-page] Ajout d'un PodDisruptionBudget (minAvailable: 1) pour garantir la disponibilité tout en permettant des opérations de maintenance énergétique sur les nœuds.

### Agent 5 - Vérification finale
- Champs traités : ['architecture_type', 'namespace', 'component_name', 'workload_type', 'image', 'replicas', 'labels', 'ports', 'ingress', 'rbac', 'energy_goals']
- Actions :
  - yaml.safe_load_all OK sur 7 documents
  - Vérification des types k8s (quantités CPU/Memoire) : OK
  - Cohérence Service -> Deployment (selector app: landing-page) : OK
  - Cohérence Ingress -> Service (name: landing-page, port: 80) : OK
  - Cohérence HPA -> Deployment (name: landing-page) : OK
  - Cohérence PDB -> Deployment (selector app: landing-page) : OK
  - Cohérence Deployment -> ServiceAccount (name: landing-page-sa) : OK
  - Vérification isolation multi-composants : N/A (single component)
  - Contrôle déterministe Python : OK
- Avertissements : ["L'image nginx:1.27 avec readOnlyRootFilesystem: true peut échouer si nginx tente d'écrire dans /var/cache/nginx ou /var/run. Un volume emptyDir pourrait être nécessaire."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | web | manifest (tous les documents) |
| components[0].component_name | landing-page | manifest (Deployment, Service, Ingress, HPA, PDB) |
| components[0].image | nginx:1.27 | manifest (Deployment container image) |
| components[0].replicas | 1 | manifest (Deployment spec.replicas) |
| components[0].ports[0] | 80 | manifest (Deployment containerPort, Service port/targetPort) |
| components[0].ingress | www.exemple.com / | manifest (Ingress resource) |
| Agent 4: energy_goals (dimensionnement) | optimisation ressources | manifest (Deployment resources.requests/limits) |
| Agent 4: energy_goals (scaling) | HPA | manifest (HorizontalPodAutoscaler) |
| Agent 4: energy_goals (zombies) | probes | manifest (Deployment livenessProbe/readinessProbe) |
| Agent 4: energy_goals (maintenance) | PDB | manifest (PodDisruptionBudget) |

## 7. Aucun point ouvert détecté ✅


## Métriques d'exécution

- Latence totale du run : **343.734 s** (dont pipeline seul : 343.734 s)
- Appels LLM : **6** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 341.194 s (moyenne 56.866 s/appel)
- Tokens consommés : **24057** (18782 prompt + 5275 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 56.394 | 5208 |
| Agent 1 - Analyse (self-check) | 1 | 15.954 | 930 |
| Agent 2 - Template | 1 | 79.575 | 6780 |
| Agent 3 - Validation | 1 | 52.399 | 2565 |
| Agent 4 - Énergie | 1 | 55.26 | 3443 |
| Agent 5 - Vérification finale | 1 | 81.611 | 5131 |