# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie une API de paiement Node.js appelée "checkout-api", image
myregistry/checkout:1.4.2, namespace "payments". Elle doit tourner en 3
réplicas, exposer le port 8080 en HTTP. Elle a besoin d'une variable
d'environnement NODE_ENV=production et d'un mot de passe base de données
DB_PASSWORD à lire depuis le secret "checkout-db-secret". Le trafic est
très faible la nuit (entre minuit et 6h) et très élevé entre 9h et midi :
je veux que ça scale automatiquement pour économiser de l'énergie/coût
aux heures creuses, avec un minimum de 2 réplicas et un maximum de 8.
Pas de stockage persistant nécessaire. La sécurité est primordiale.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `checkout-api` (Deployment)

## 3. Auto-vérification Agent 1

- Auto-check réussi : **True**
- Tentatives de réparation internes : 0
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].env_vars[1].secret_key` : Quelle est la clé exacte à lire dans le secret checkout-db-secret ? → hypothèse retenue : *Utilisation de DB_PASSWORD comme clé interne du Secret* (confiance medium)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[checkout-api]']
- Actions :
  - Extraction initiale + 0 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ['Quelle est la clé exacte à lire dans le secret checkout-db-secret ?']

### Agent 2 - Template
- Champs traités : ['namespace', '[checkout-api] component_name', '[checkout-api] workload_type', '[checkout-api] image', '[checkout-api] replicas', '[checkout-api] labels', '[checkout-api] ports', '[checkout-api] env_vars', '[checkout-api] volumes: aucun demande, rien a faire', '[checkout-api] sidecars: aucun demande, rien a faire', '[checkout-api] depends_on: aucun demande, rien a faire', '[checkout-api] cron_schedule: non applicable pour un Deployment', '[checkout-api] config_maps: aucun demande, rien a faire', '[checkout-api] network_policy: non specifie', '[checkout-api] deployment_strategy: aucun demande, utilisation du Deployment standard', '[checkout-api] namespace', "[checkout-api] security_requirements: Exigence de securite globale maximale: application d'un securityContext durci (runAsNonRoot, allowPrivilegeEscalation: false, readOnlyRootFilesystem, capabilities drop ALL, seccomp RuntimeDefault) et exposition via Service ClusterIP", '[checkout-api] observability_requirements: observability_requirements: aucun demande explicite', '[checkout-api] ingress: ingress: aucun Ingress ou Gateway API demande', "[checkout-api] rbac: Creation d'un ServiceAccount dedie checkout-api-sa sans Role/RoleBinding associe (rbac.enabled=false, principe du moindre privilege)"]
- ⚠️ Champs laissés ouverts : ["[checkout-api] resources.requests/limits (gere par l'Agent 4)", "[checkout-api] HPA (gere par l'Agent 4)"]
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'payments' généré (une seule fois, déterministe)

### Agent 3 - Validation
- Champs traités : ['namespace', 'architecture_type', 'components.component_name', 'components.workload_type', 'components.image', 'components.replicas', 'components.labels', 'components.ports', 'components.env_vars', 'components.volumes', 'components.sidecars', 'components.ingress', 'components.rbac', 'components.cron_schedule']
- Actions :
  - apiVersion et kind valide pour toutes les ressources
  - Présence et appartenance au Namespace 'payments'
  - Labels et Selectors alignés entre Deployment et Service (app: checkout-api)
  - Référence ServiceAccount (checkout-api-sa) correcte dans Deployment
  - Nombre de répliques (3), conteneur, port (8080/TCP) et variables d'environnement conformes à la NormalizedSpec
  - Absence de sidecars/ingress/volumes à traiter en conformité avec la spec

### Agent 4 - Énergie
- Champs traités : ['[checkout-api] energy_goals', '[checkout-api] resource_hints', '[checkout-api] traffic_windows', '[checkout-api] replicas', '[checkout-api] workload_type', '[checkout-api] constraints', '[checkout-api] energy_goals: Autoscaling automatique pour économiser énergie/coût aux heures creuses', '[checkout-api] energy_goals: Réduction de la capacité nocturne quand le trafic est très faible']
- Actions :
  - [checkout-api] Ajout des requêtes et limites de ressources CPU/mémoire (requests: 100m/256Mi, limits: 500m/512Mi) sur le conteneur checkout-api pour dimensionner raisonnablement le composant sans gaspillage.
  - [checkout-api] Ajout de livenessProbe et readinessProbe basées sur tcpSocket (port 8080) afin d'éviter la persistance de pods zombies non fonctionnels tout en évitant les faux positifs HTTP.
  - [checkout-api] Création d'un ScaledObject KEDA configuré avec minReplicas=2 et maxReplicas=8, intégrant un trigger cron pour la fenêtre nocturne à faible trafic (00:00 à 06:00, cible 2 répliques) et un trigger CPU à 60% pour la réactivité.
  - [checkout-api] Ajout d'un PodDisruptionBudget (minAvailable=1) pour maintenir la haute disponibilité lors du rescheduling.
- Avertissements : ["[checkout-api] L'utilisation du CRD ScaledObject nécessite l'opérateur KEDA installé sur le cluster (https://keda.sh). Alternative sans dépendance externe : utiliser un HorizontalPodAutoscaler classique réactif au CPU avec minReplicas=2 et maxReplicas=8 (scaling moins ciblé sur les heures creuses).", "[checkout-api] Le fuseau horaire n'étant pas renseigné dans la fenêtre de trafic, la valeur par défaut 'UTC' a été utilisée pour l'expression cron du ScaledObject."]

### Agent 5 - Vérification finale
- Champs traités : ['syntax_validation', 'cross_resource_references', 'label_selectors_consistency', 'ports_and_probes_consistency', 'traceability_audit']
- Actions :
  - yaml.safe_load_all OK sur les 6 documents du manifeste
  - Types des quantites Kubernetes valides (cpu: 100m/500m, memory: 256Mi/512Mi)
  - References de ServiceAccount 'checkout-api-sa' valide dans Deployment
  - Selector app=checkout-api coherent entre Deployment, Service et PodDisruptionBudget
  - scaleTargetRef du ScaledObject pointe correctement vers le Deployment 'checkout-api'
  - Ports et probes alignes sur le port conteneur 8080/TCP
  - Tous les objets sont correctement assignes au namespace 'payments'
  - Contrôle déterministe Python : OK
- Avertissements : ["L'utilisation de la ressource ScaledObject (keda.sh/v1alpha1) necessite le deploiement prealable de l'operateur KEDA sur le cluster Kubernetes.", "Fuseau horaire UTC applique par defaut pour la fenetre d'autoscaling nocturne KEDA."]

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | payments | manifest (Namespace/payments et metadata.namespace sur tous les objets) |
| components[0].component_name | checkout-api | manifest (metadata.name sur Deployment, Service, SA, PDB, ScaledObject) |
| components[0].workload_type | Deployment | manifest (Deployment kind=Deployment nom=checkout-api) |
| components[0].image | myregistry/checkout:1.4.2 | manifest (Deployment container[0].image) |
| components[0].replicas | 3 | manifest (Deployment spec.replicas=3) |
| components[0].ports[0] | port 8080 HTTP expose | manifest (Deployment containerPort 8080 & Service port 8080) |
| components[0].env_vars[0] | NODE_ENV=production | manifest (Deployment env NODE_ENV) |
| components[0].env_vars[1] | DB_PASSWORD depuis secret checkout-db-secret | manifest (Deployment env valueFrom.secretKeyRef) |
| components[0].security_requirements | Exigence de securite globale maximale | manifest (Deployment securityContext: runAsNonRoot, readOnlyRootFilesystem, allowPrivilegeEscalation=false, capabilities drop ALL, seccomp RuntimeDefault) |
| components[0].energy_goals[0] | Autoscaling automatique pour economiser energie/cout aux heures creuses | manifest (ScaledObject minReplicaCount=2, maxReplicaCount=8, trigger CPU 60%) |
| components[0].energy_goals[1] | Reduction de la capacite nocturne quand le trafic est tres faible | manifest (ScaledObject trigger cron 00:00-06:00 desiredReplicas=2) |
| components[0].traffic_windows | 00:00-06:00 (low, target 2) & 09:00-12:00 (high, target 8) | manifest (ScaledObject triggers cron et cpu) |

## 7. ⚠️ À vérifier / relancer si besoin

- [checkout-api] HPA (gere par l'Agent 4)
- [checkout-api] resources.requests/limits (gere par l'Agent 4)

## Métriques d'exécution

- Latence totale du run : **142.968 s** (dont pipeline seul : 142.968 s)
- Appels LLM : **9** (2 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 136.227 s (moyenne 15.136 s/appel)
- Tokens consommés : **28949** (21805 prompt + 7144 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 15.325 | 5854 |
| Agent 1 - Analyse (self-check) | 1 | 12.945 | 1507 |
| Agent 1 - Analyse (réparation schéma) | 1 | 25.308 | 2657 |
| Agent 2 - Template | 3 (2 échoué(s)) | 15.968 | 6645 |
| Agent 3 - Validation | 1 | 11.748 | 2581 |
| Agent 4 - Énergie | 1 | 39.954 | 3690 |
| Agent 5 - Vérification finale | 1 | 14.978 | 6015 |