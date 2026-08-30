# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie une API de paiement Node.js appelée "checkout-api", image myregistry/checkout:1.4.2, namespace "payments". Elle doit tourner en 3 réplicas, exposer le port 8080 en HTTP. Elle a besoin d'une variable d'environnement NODE_ENV=production et d'un mot de passe base de données DB_PASSWORD à lire depuis le secret "checkout-db-secret". Le trafic est très faible la nuit (entre minuit et 6h) et très élevé entre 9h et midi : je veux que ça scale automatiquement pour économiser de l'énergie/coût aux heures creuses, avec un minimum de 2 réplicas et un maximum de 8. Pas de stockage persistant nécessaire. La sécurité est primordiale.

## 2. Architecture détectée

- Type : **single** (1 composant(s))
  - `checkout-api` (Deployment)

- Auto-check réussi : **True**
- Tentatives de réparation internes : 1
- ⚠️ Exigences jamais couvertes : ['Runtime: Node.js']
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].env_vars[1].secret_key` : Quelle est la clé exacte à l'intérieur du secret 'checkout-db-secret' ? → hypothèse retenue : *La clé est identique au nom de la variable d'environnement : 'DB_PASSWORD'* (confiance medium)
  - `components[0].ingress` : L'API doit-elle être accessible depuis l'extérieur du cluster ? → hypothèse retenue : *L'utilisateur demande d'exposer le port 8080, ce qui est traduit par un Service Kubernetes interne. Aucun Ingress n'est créé car aucun domaine ou accès public n'est mentionné.* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[checkout-api]']
- ⚠️ Champs laissés ouverts : ['Runtime: Node.js', "unmapped_requirements: {'requirement': 'Runtime/Langage: Node.js', 'suggested_kind': 'runtime'} (suggested_kind=runtime)"]
- Actions :
  - Extraction initiale + 1 passe(s) de réparation interne
  - Architecture détectée : single (1 composant(s))
  - Contraintes globales (blackboard) : aucune détectée
- Avertissements : ["Quelle est la clé exacte à l'intérieur du secret 'checkout-db-secret' ?", "L'API doit-elle être accessible depuis l'extérieur du cluster ?"]

### Agent 2 - Template
- Champs traités : ['namespace', '[checkout-api] component_name', '[checkout-api] workload_type', '[checkout-api] image', '[checkout-api] replicas', '[checkout-api] labels: vide, labels standards appliqués', '[checkout-api] ports: exposé via Service ClusterIP', '[checkout-api] env_vars: NODE_ENV et DB_PASSWORD (secretKeyRef)', '[checkout-api] volumes: aucun demandé', '[checkout-api] sidecars: aucun demandé', '[checkout-api] depends_on: vide', '[checkout-api] security_requirements: hardening appliqué', '[checkout-api] observability_requirements: vide', '[checkout-api] ingress: None', '[checkout-api] rbac: enabled=False, ServiceAccount créé', '[checkout-api] service_mesh_routing: vide', '[checkout-api] observability_style: annotations (aucune métrique définie)', '[checkout-api] cron_schedule: non applicable', '[checkout-api] config_maps: vide', '[checkout-api] network_policy: None (générée via security_requirements)', '[checkout-api] deployment_strategy: None', '[checkout-api] namespace', "[checkout-api] security_requirements: La sécurité est primordiale -> Application d'un securityContext durci (runAsNonRoot, readOnlyRootFilesystem, drop capabilities) et d'une NetworkPolicy restreignant l'ingress au namespace.", '[checkout-api] observability_requirements: Aucune exigence fournie', '[checkout-api] ingress: Aucun ingress demandé', '[checkout-api] rbac: Création du ServiceAccount dédié checkout-api-sa']
- ⚠️ Champs laissés ouverts : ['unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.']
- Actions :
  - Génération du manifeste structurel de base (sans énergie)
  - Hardening de sécurité (securityContext, NetworkPolicy si pertinent)
  - Configuration observabilité (annotations Prometheus si pertinent)
  - ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés
  - Namespace 'payments' généré (une seule fois, déterministe)
  - Génération BEST-EFFORT (non vérifiée) pour 1 exigence(s) hors du schéma structuré : ["{'requirement': 'Runtime/Langage: Node.js', 'suggested_kind': 'runtime'}"]

### Agent 3 - Validation (itération 0)
- Champs traités : ['namespace', 'component_name', 'workload_type', 'image', 'replicas', 'ports', 'env_vars', 'volumes', 'sidecars', 'rbac', 'security_requirements']
- Actions :
  - apiVersion présent
  - kind présent
  - metadata.name présent
  - cohérence selector Service / labels Deployment
  - ServiceAccount présent malgré rbac.enabled: false
  - securityContext strict aligné avec security_requirements
  - env_vars fidèles à la NormalizedSpec
  - replicas fidèles à la NormalizedSpec
  - ports fidèles à la NormalizedSpec
  - indentation YAML valide

### Agent 4 - Débat multi-agents (Énergie)
- Champs traités : ['[checkout-api] resources', '[checkout-api] affinity', '[checkout-api] nodeSelector', '[checkout-api] autoscaling', '[checkout-api] probes']
- Actions :
  - [checkout-api] Débat conclu : 1 tour(s) de critique, 1 conflit(s) réel(s) relevé(s), scores {'consolidation': 9.0, 'sizing': 10.0, 'autoscaling': 10.0}.
  - [checkout-api] Éléments retenus par stratégie : {'resources': 'sizing', 'affinity': 'consolidation', 'nodeSelector': 'consolidation', 'autoscaling': 'autoscaling', 'probes': 'sizing'}
  - [checkout-api] The final manifest is a fusion of the three strategies, as they are complementary. The conflict regarding resource requests (100m vs 150m) was resolved in favor of the Sizing strategy; given the 'critical' nature of the payment API in the application_context, the 1.8x CPU ratio (150m request / 270m limit) provides the necessary stability and avoids the 'slack' risk identified in the critiques. The Consolidation strategy's placement logic (shared nodepool and preferred podAffinity) is retained to maximize bin-packing, while the Autoscaling strategy's KEDA ScaledObject is integrated to meet the energy goals for off-peak hours. The use of 'preferred' affinity ensures that scaling up to 8 replicas is not blocked by strict placement constraints. TCP probes from Sizing/Consolidation are included to ensure reliability during scaling events.
- Avertissements : ["Documents non associés à un composant connu, conservés tels quels (non optimisés énergétiquement) : ['/']."]

### Agent 5 - Vérification finale
- Champs traités : ['energy_goals', 'resource_hints', 'traffic_windows', 'security_requirements', 'env_vars', 'namespace']
- ⚠️ Champs laissés ouverts : ['Runtime/Langage: Node.js (Requirement non-structurel, traité en best-effort via commentaire, ne correspond à aucune ressource K8s)', "1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : '{'requirement': 'Runtime/Langage: Node.js', 'suggested_kind': 'runtime'}' (kind supposé: runtime)"]
- Actions :
  - yaml.safe_load_all OK sur 7 documents
  - Cross-reference Service (selector) -> Deployment (labels) OK
  - Cross-reference ScaledObject (scaleTargetRef) -> Deployment (name) OK
  - Cross-reference Deployment (serviceAccountName) -> ServiceAccount (name) OK
  - Cross-reference NetworkPolicy (podSelector) -> Deployment (labels) OK
  - K8s resource quantities (cpu/memory) valid
  - Contrôle déterministe Python : OK

## 5. Matrice de traçabilité (Agent 5)

| Champ spec | Valeur | Résolu dans |
|---|---|---|
| energy_goals[0] | économiser de l'énergie/coût aux heures creuses | manifest (ScaledObject/checkout-api-scaledobject via cron triggers) |
| components[0].resource_hints | minimum de 2 réplicas et un maximum de 8 | manifest (ScaledObject/checkout-api-scaledobject minReplicaCount=2, maxReplicaCount=8) |
| components[0].traffic_windows | 00:00-06:00 (low), 09:00-12:00 (high) | manifest (ScaledObject/checkout-api-scaledobject cron triggers) |
| components[0].security_requirements | La sécurité est primordiale | manifest (Deployment/checkout-api securityContext + NetworkPolicy/checkout-api-netpol) |
| components[0].env_vars | NODE_ENV, DB_PASSWORD | manifest (Deployment/checkout-api env) |

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- {'requirement': 'Runtime/Langage: Node.js', 'suggested_kind': 'runtime'} (kind supposé : `runtime`)

## 7. ⚠️ À vérifier / relancer si besoin

- 1 exigence(s) générée(s) en mode BEST-EFFORT, hors du schéma structuré habituel — non couvertes par les cross-vérifications spécifiques (contrairement au reste du manifeste), à valider manuellement avant tout déploiement réel : '{'requirement': 'Runtime/Langage: Node.js', 'suggested_kind': 'runtime'}' (kind supposé: runtime)
- Runtime/Langage: Node.js (Requirement non-structurel, traité en best-effort via commentaire, ne correspond à aucune ressource K8s)
- Runtime: Node.js
- unmapped_requirements: 1 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: 1 fragment(s) généré(s) en best-effort, non vérifié(s) par les contrôles habituels (pas de cross-référence, pas de connaissance du schéma OpenAPI de ce kind) — à valider manuellement avant tout déploiement.
- unmapped_requirements: {'requirement': 'Runtime/Langage: Node.js', 'suggested_kind': 'runtime'} (suggested_kind=runtime)

## Métriques d'exécution

- Latence totale du run : **1061.739 s** (dont pipeline seul : 1061.739 s)
- Appels LLM : **16** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 1338.404 s (moyenne 83.65 s/appel)
- Tokens consommés : **81539** (62836 prompt + 18703 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 78.546 | 6848 |
| Agent 1 - Analyse (self-check) | 2 | 198.838 | 3360 |
| Agent 1 - Analyse (réparation) | 1 | 81.849 | 3121 |
| Agent 1 - Analyse (contraintes globales) | 1 | 21.484 | 1152 |
| Agent 2 - Template | 1 | 93.393 | 8117 |
| Agent 2 - Template (best-effort) | 1 | 160.267 | 6981 |
| Agent 3 - Validation | 1 | 61.424 | 4182 |
| Agent4-Debate-Strategy-consolidation | 1 | 57.409 | 3455 |
| Agent4-Debate-Strategy-sizing | 1 | 64.879 | 3447 |
| Agent4-Debate-Strategy-autoscaling | 1 | 85.327 | 3929 |
| Agent4-Debate-Strategy-consolidation-Critique | 1 | 70.238 | 6673 |
| Agent4-Debate-Strategy-sizing-Critique | 1 | 85.505 | 6955 |
| Agent4-Debate-Strategy-autoscaling-Critique | 1 | 92.602 | 7339 |
| Agent4-Debate-Judge | 1 | 71.116 | 8096 |
| Agent 5 - Vérification finale | 1 | 115.527 | 7884 |