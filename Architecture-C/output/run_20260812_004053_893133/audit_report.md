# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie un outil de diagnostic bas niveau appelé "kernel-debugger" (image myregistry/kdebug:latest, namespace "ops"). Pour des raisons de compatibilité avec des outils legacy internes, ce conteneur doit tourner en root avec un accès complet aux capabilities du noyau hôte (mode privilégié), et le système de fichiers du conteneur doit rester inscriptible. Un seul réplica, pas de port réseau exposé, pas de stockage persistant.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `kernel-debugger` (Deployment)

- Auto-check réussi : **True**
- Tentatives de réparation internes : 0
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].workload_type` : S'agit-il d'un Deployment long-running ou d'un Job/DaemonSet de diagnostic ? → hypothèse retenue : *Déploiement sous forme de Deployment à 1 réplica tel que demandé.* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[kernel-debugger]']
- Actions :
  - Extraction initiale + 0 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : aucune détectée
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ["S'agit-il d'un Deployment long-running ou d'un Job/DaemonSet de diagnostic ?"]

### Agent 2 - Template
- Champs traités : ['namespace', "[kernel-debugger] component_name: 'kernel-debugger' utilisé pour metadata.name et les labels", "[kernel-debugger] namespace: 'ops' appliqué à l'ensemble des ressources", "[kernel-debugger] workload_type: 'Deployment' utilisé pour la ressource principale", "[kernel-debugger] image: 'myregistry/kdebug:latest' configurée pour le conteneur principal", '[kernel-debugger] replicas: 1 configuré dans spec.replicas', "[kernel-debugger] labels: {'app': 'kernel-debugger'} appliqués aux métadonnées, pod template et selector", '[kernel-debugger] ports: aucun port exposé (liste vide)', "[kernel-debugger] env_vars: aucune variable d'environnement demandée", '[kernel-debugger] volumes: aucun volume persistent ou temporaire demandé', '[kernel-debugger] sidecars: aucun sidecar demandé', '[kernel-debugger] depends_on: aucune dépendance déclarée', '[kernel-debugger] cron_schedule: non applicable pour un Deployment', '[kernel-debugger] config_maps: aucune ConfigMap demandée', '[kernel-debugger] network_policy: aucune politique réseau spécifique demandée', '[kernel-debugger] deployment_strategy: stratégie standard du Deployment conservée', '[kernel-debugger] security_requirements: Exécution du conteneur en root requise : appliquée via securityContext.runAsNonRoot: false et runAsUser: 0', '[kernel-debugger] security_requirements: Mode privilégié (privileged: true) : appliqué via securityContext.privileged: true', '[kernel-debugger] security_requirements: Système de fichiers inscriptible : appliqué via securityContext.readOnlyRootFilesystem: false', '[kernel-debugger] observability_requirements: observability_requirements: aucune exigence explicite fournie', '[kernel-debugger] ingress: ingress: non configuré (None), aucune ressource Ingress/HTTPRoute créée', "[kernel-debugger] rbac: rbac.enabled: false - ServiceAccount 'kernel-debugger-sa' créé sans Role ni RoleBinding associés"]
- ⚠️ Champs laissés ouverts : ['[kernel-debugger] energy_goals: non géré par cet agent, délégué aux étapes ultérieures']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'ops' généré (une seule fois, déterministe)
- Avertissements : ["[kernel-debugger] ATTENTION SÉCURITÉ : Le conteneur 'kernel-debugger' est configuré en mode privilégié (privileged: true) et s'exécute en root (runAsUser: 0) sur un système de fichiers inscriptible conformément aux exigences explicites. Ces réglages accordent un accès étendu au noyau hôte et doivent être restreints aux seuls environnements de débogage autorisés."]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'components[0].component_name', 'components[0].workload_type', 'components[0].image', 'components[0].replicas', 'components[0].labels', 'components[0].ports', 'components[0].env_vars', 'components[0].volumes', 'components[0].sidecars', 'components[0].security_requirements', 'components[0].ingress', 'components[0].rbac', 'components[0].observability_style', 'components[0].cron_schedule', 'global_constraints']
- Actions :
  - apiVersion et kind absents ou invalides: Aucun (tous présents et valides)
  - Cohérence des namespaces ('ops') sur toutes les ressources
  - Alignement des selectors Deployment spec.selector.matchLabels avec template.metadata.labels
  - ServiceAccount 'kernel-debugger-sa' présent et associé au Deployment
  - Validation des securityContext spécifiques autorisés par security_requirements (privileged, root, rootfs inscriptible)
- Avertissements : ["Le conteneur 'kernel-debugger' est exécuté en mode privilégié avec runAsUser: 0 et readOnlyRootFilesystem: false, ce qui est validé conformément aux security_requirements explicites de la NormalizedSpec."]

### Agent 4 - Énergie
- Champs traités : ['[kernel-debugger] resource_hints', '[kernel-debugger] traffic_windows', '[kernel-debugger] energy_goals', '[kernel-debugger] constraints', '[kernel-debugger] replicas']
- Actions :
  - [kernel-debugger] Dimensionnement minimal des ressources CPU (50m request / 200m limit) et Mémoire (64Mi request / 256Mi limit) adapté à un outil de débogage ponctuel sans trafic continu.
  - [kernel-debugger] Pas de HPA — le profil applicatif correspond à un outil d'administration interne statique sans besoin de scaling automatique.
  - [kernel-debugger] Pas de PodDisruptionBudget — composant à réplique unique (replicas=1) et faible criticité globale.
  - [kernel-debugger] Ajout de livenessProbe et readinessProbe via exec pour éviter de maintenir des instances zombies en cas de dysfonctionnement.
- Avertissements : ["[kernel-debugger] Aucun port réseau n'étant spécifié pour le conteneur kernel-debugger, des sondes de santé de type 'exec' ([true]) ont été configurées. À ajuster selon les capacités de l'image myregistry/kdebug:latest."]

### Agent 5 - Vérification finale
- Champs traités : ['manifest_yaml', 'syntax_checks', 'syntax_fixes', 'traceability_matrix', 'unresolved_items', 'repair_requests']
- Actions :
  - yaml.safe_load_all OK sur 3 documents (ServiceAccount, Deployment, Namespace)
  - Types de données Kubernetes valides (quantités CPU/Mémoire, entiers, booléens)
  - Coherence du selector 'app: kernel-debugger' avec les labels du template de Pod
  - ServiceAccount 'kernel-debugger-sa' existant et correctement référencé dans le Pod
  - Namespace 'ops' déclaré et appliqué uniformément à toutes les ressources
  - Contrôle déterministe Python : OK
- Avertissements : ['Le conteneur tourne en mode privilégié (privileged: true) avec UID 0 et un système de fichiers inscriptible conformément aux contraintes de débogage noyau explicites.']

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| namespace | ops | Namespace (metadata.name=ops) et metadata.namespace de toutes les ressources |
| components[0].component_name | kernel-debugger | Deployment (metadata.name=kernel-debugger) |
| components[0].workload_type | Deployment | Deployment (kind=Deployment) |
| components[0].image | myregistry/kdebug:latest | Deployment (spec.template.spec.containers[0].image) |
| components[0].replicas | 1 | Deployment (spec.replicas=1) |
| components[0].security_requirements | root, privileged: true, readOnlyRootFilesystem: false | Deployment (spec.template.spec.containers[0].securityContext) |
| energy_goals | non spécifiés dans la spec (dimensionnement minimal) | Agent 4 (resources requests/limits définies, probes ajoutées) |

## 7. ⚠️ À vérifier / relancer si besoin

- [kernel-debugger] energy_goals: non géré par cet agent, délégué aux étapes ultérieures

## Métriques d'exécution

- Latence totale du run : **107.271 s** (dont pipeline seul : 107.271 s)
- Appels LLM : **8** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 101.389 s (moyenne 12.674 s/appel)
- Tokens consommés : **28853** (24119 prompt + 4734 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 15.72 | 6176 |
| Agent 1 - Analyse (self-check) | 1 | 11.993 | 1040 |
| Agent 1 - Analyse (contraintes globales) | 1 | 3.171 | 1076 |
| Agent 1 - Analyse (réparation schéma) | 1 | 11.15 | 2059 |
| Agent 2 - Template | 1 | 11.223 | 6573 |
| Agent 3 - Validation | 1 | 11.505 | 2948 |
| Agent 4 - Énergie | 1 | 14.823 | 3885 |
| Agent 5 - Vérification finale | 1 | 21.803 | 5096 |