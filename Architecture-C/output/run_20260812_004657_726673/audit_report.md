# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie une application e-commerce full-stack dans le namespace 'ecommerce' : frontend React (image myregistry/frontend:3.2.1, 3 replicas, port 3000, exposé sur shop.mon-domaine.com avec TLS, HPA min:2 max:6 CPU:70%, API_URL=http://backend-api:8080), backend API Node.js (image myregistry/backend:2.5.0, 5 replicas, port 8080, DB_URL depuis secret db-secret key url, HPA min:3 max:10 CPU:65%, Prometheus port 9090, sidecar Envoy), Redis cache (image redis:7.2-alpine, 1 replica, port 6379, stockage 5GB, interne), PostgreSQL CrunchyData (3 instances, réplication synchrone, chiffrement encrypted-gold, backups, 10GB, interne), Prometheus (1 replica, port 9090), Grafana (1 replica, port 3000, exposé sur monitoring.mon-domaine.com), Ingress avec TLS cert-manager (ClusterIssuer letsencrypt-prod) pour shop.mon-domaine.com, api.mon-domaine.com, monitoring.mon-domaine.com, NetworkPolicy: frontend->backend, backend->redis/postgres, securityContext runAsNonRoot, rotation clés 90 jours, KEDA pour backend (00h-06h:2, 09h-12h:10), PDB pour frontend (min:2) et backend (min:3), resources optimisées, probes HTTP pour services exposés, probes TCP pour services internes

## 2. Architecture détectée

- Type : **single** (0 composant(s))

## 2bis. Contraintes globales (blackboard)

Extraites séparément des composants par l'Agent 1, visibles par tout agent en aval qui filtre par portée — voir `schemas.GlobalConstraint` pour le mécanisme complet.

- **[all_containers/security]** securityContext runAsNonRoot
- **[all_components/security]** rotation clés 90 jours
- **[all_components/other]** probes HTTP pour services exposés, probes TCP pour services internes
- **[all_components/other]** resources optimisées
- **[specific/other]** probes HTTP pour services exposés
- **[specific/other]** probes TCP pour services internes

- Auto-check réussi : **False**
- Tentatives de réparation internes : 2
- ⚠️ Exigences jamais couvertes : ["Namespace 'ecommerce'", 'Composant PostgreSQL CrunchyData (3 instances, réplication synchrone, chiffrement, backups, 10GB) non défini.', 'Composant Grafana', 'Configuration KEDA (fenêtres temporelles 00h-06h:2, 09h-12h:10) absent de traffic_windows.', 'Composant Grafana (1 replica, port 3000, hôte dédié) non défini.', "Règles d'Ingress pour 'api.mon-domaine.com' et 'monitoring.mon-domaine.com' non couvertes dans l'objet ingress.", 'Composant Prometheus', 'Composant Backend API Node.js (image, réplicas, secrets, HPA, KEDA, sidecar Envoy) non présent dans la structure principale.', "Règles NetworkPolicy pour 'backend -> redis/postgres' non incluses dans la configuration réseau du frontend.", 'Composant Prometheus (1 replica, port 9090) non défini.', 'Composant Redis cache (image, réplicas, port, stockage 5GB) non défini dans un objet composant dédié.', 'Hôtes Ingress supplémentaires (api.mon-domaine.com, monitoring.mon-domaine.com)', 'Composant Backend API Node.js (et scaling KEDA 00h-06h:2, 09h-12h:10)', "Namespace 'ecommerce' absent des champs structurés principaux.", 'Composant PostgreSQL CrunchyData', "[EXTRACTION POTENTIELLEMENT MANQUÉE] Indices de contrainte transversale détectés dans le texte original (['chiffrement', 'encrypted']) mais aucune global_constraint n'a pu être extraite, même après une tentative dédiée avec indice explicite. Vérifiez manuellement si le texte contient une exigence de sécurité/conformité qui s'applique à plusieurs composants ou à toute l'application.", 'Sondes TCP pour services internes', 'PDB du backend (min: 3) manquant dans les contraintes.', 'Sondes TCP pour les services internes non configurées.', 'Règles NetworkPolicy backend->redis/postgres', 'Composant Redis cache']

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'global_constraints']
- ⚠️ Champs laissés ouverts : ["Namespace 'ecommerce'", 'Composant PostgreSQL CrunchyData (3 instances, réplication synchrone, chiffrement, backups, 10GB) non défini.', 'Composant Grafana', 'Configuration KEDA (fenêtres temporelles 00h-06h:2, 09h-12h:10) absent de traffic_windows.', 'Composant Grafana (1 replica, port 3000, hôte dédié) non défini.', "Règles d'Ingress pour 'api.mon-domaine.com' et 'monitoring.mon-domaine.com' non couvertes dans l'objet ingress.", 'Composant Prometheus', 'Composant Backend API Node.js (image, réplicas, secrets, HPA, KEDA, sidecar Envoy) non présent dans la structure principale.', "Règles NetworkPolicy pour 'backend -> redis/postgres' non incluses dans la configuration réseau du frontend.", 'Composant Prometheus (1 replica, port 9090) non défini.', 'Composant Redis cache (image, réplicas, port, stockage 5GB) non défini dans un objet composant dédié.', 'Hôtes Ingress supplémentaires (api.mon-domaine.com, monitoring.mon-domaine.com)', 'Composant Backend API Node.js (et scaling KEDA 00h-06h:2, 09h-12h:10)', "Namespace 'ecommerce' absent des champs structurés principaux.", 'Composant PostgreSQL CrunchyData', "[EXTRACTION POTENTIELLEMENT MANQUÉE] Indices de contrainte transversale détectés dans le texte original (['chiffrement', 'encrypted']) mais aucune global_constraint n'a pu être extraite, même après une tentative dédiée avec indice explicite. Vérifiez manuellement si le texte contient une exigence de sécurité/conformité qui s'applique à plusieurs composants ou à toute l'application.", 'Sondes TCP pour services internes', 'PDB du backend (min: 3) manquant dans les contraintes.', 'Sondes TCP pour les services internes non configurées.', 'Règles NetworkPolicy backend->redis/postgres', 'Composant Redis cache', 'unmapped_requirements: {\'requirement\': "Namespace \'ecommerce\'", \'suggested_kind\': \'namespace\'} (suggested_kind=namespace)', "unmapped_requirements: {'requirement': 'Composant Backend API Node.js (image myregistry/backend:2.5.0, 5 replicas, port 8080, DB_URL depuis secret, HPA min:3 max:10 CPU:65%, KEDA 00h-06h:2 09h-12h:10, sidecar Envoy, PDB min:3)', 'suggested_kind': 'component'} (suggested_kind=component)", "unmapped_requirements: {'requirement': 'Composant Redis cache (image redis:7.2-alpine, 1 replica, port 6379, stockage 5GB, sonde TCP, interne)', 'suggested_kind': 'component'} (suggested_kind=component)", "unmapped_requirements: {'requirement': 'Composant PostgreSQL CrunchyData (3 instances, réplication synchrone, chiffrement encrypted-gold, sauvegardes, 10GB, sonde TCP, interne)', 'suggested_kind': 'component'} (suggested_kind=component)", "unmapped_requirements: {'requirement': 'Composant Prometheus (1 replica, port 9090)', 'suggested_kind': 'component'} (suggested_kind=component)", "unmapped_requirements: {'requirement': 'Composant Grafana (1 replica, port 3000, exposé sur monitoring.mon-domaine.com)', 'suggested_kind': 'component'} (suggested_kind=component)", "unmapped_requirements: {'requirement': 'Hôtes Ingress supplémentaires (api.mon-domaine.com, monitoring.mon-domaine.com)', 'suggested_kind': 'ingress'} (suggested_kind=ingress)", "unmapped_requirements: {'requirement': 'Règles NetworkPolicy backend->redis/postgres', 'suggested_kind': 'network_policy'} (suggested_kind=network_policy)", "unmapped_requirements: {'requirement': 'Sondes de santé TCP pour services internes', 'suggested_kind': 'probes'} (suggested_kind=probes)"]
- Actions :
  - Extraction initiale + 2 passe(s) de réparation interne
  - Architecture détectée : single (0 composant(s))
  - Contraintes globales (blackboard) : 6 extraite(s) : ['securityContext runAsNonRoot', 'rotation clés 90 jours', 'probes HTTP pour services exposés, probes TCP pour services internes', 'resources optimisées', 'probes HTTP pour services exposés', 'probes TCP pour services internes']

## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)

Ces exigences ne correspondaient à AUCUN champ existant du schéma structuré. Plutôt que de les forcer dans un champ approximatif (ce qui produirait un audit faussement rassurant), elles ont été générées en best-effort par l'Agent 2 — **non couvertes par les cross-vérifications spécifiques du reste du pipeline** (pas de connaissance du schéma OpenAPI de ces `kind`, pas de cross-référence automatique). À valider manuellement avant tout déploiement réel.

- {'requirement': "Namespace 'ecommerce'", 'suggested_kind': 'namespace'} (kind supposé : `namespace`)
- {'requirement': 'Composant Backend API Node.js (image myregistry/backend:2.5.0, 5 replicas, port 8080, DB_URL depuis secret, HPA min:3 max:10 CPU:65%, KEDA 00h-06h:2 09h-12h:10, sidecar Envoy, PDB min:3)', 'suggested_kind': 'component'} (kind supposé : `component`)
- {'requirement': 'Composant Redis cache (image redis:7.2-alpine, 1 replica, port 6379, stockage 5GB, sonde TCP, interne)', 'suggested_kind': 'component'} (kind supposé : `component`)
- {'requirement': 'Composant PostgreSQL CrunchyData (3 instances, réplication synchrone, chiffrement encrypted-gold, sauvegardes, 10GB, sonde TCP, interne)', 'suggested_kind': 'component'} (kind supposé : `component`)
- {'requirement': 'Composant Prometheus (1 replica, port 9090)', 'suggested_kind': 'component'} (kind supposé : `component`)
- {'requirement': 'Composant Grafana (1 replica, port 3000, exposé sur monitoring.mon-domaine.com)', 'suggested_kind': 'component'} (kind supposé : `component`)
- {'requirement': 'Hôtes Ingress supplémentaires (api.mon-domaine.com, monitoring.mon-domaine.com)', 'suggested_kind': 'ingress'} (kind supposé : `ingress`)
- {'requirement': 'Règles NetworkPolicy backend->redis/postgres', 'suggested_kind': 'network_policy'} (kind supposé : `network_policy`)
- {'requirement': 'Sondes de santé TCP pour services internes', 'suggested_kind': 'probes'} (kind supposé : `probes`)

## 7. ⚠️ À vérifier / relancer si besoin

- Composant Backend API Node.js (et scaling KEDA 00h-06h:2, 09h-12h:10)
- Composant Backend API Node.js (image, réplicas, secrets, HPA, KEDA, sidecar Envoy) non présent dans la structure principale.
- Composant Grafana
- Composant Grafana (1 replica, port 3000, hôte dédié) non défini.
- Composant PostgreSQL CrunchyData
- Composant PostgreSQL CrunchyData (3 instances, réplication synchrone, chiffrement, backups, 10GB) non défini.
- Composant Prometheus
- Composant Prometheus (1 replica, port 9090) non défini.
- Composant Redis cache
- Composant Redis cache (image, réplicas, port, stockage 5GB) non défini dans un objet composant dédié.
- Configuration KEDA (fenêtres temporelles 00h-06h:2, 09h-12h:10) absent de traffic_windows.
- Hôtes Ingress supplémentaires (api.mon-domaine.com, monitoring.mon-domaine.com)
- Namespace 'ecommerce'
- Namespace 'ecommerce' absent des champs structurés principaux.
- PDB du backend (min: 3) manquant dans les contraintes.
- Règles NetworkPolicy backend->redis/postgres
- Règles NetworkPolicy pour 'backend -> redis/postgres' non incluses dans la configuration réseau du frontend.
- Règles d'Ingress pour 'api.mon-domaine.com' et 'monitoring.mon-domaine.com' non couvertes dans l'objet ingress.
- Sondes TCP pour les services internes non configurées.
- Sondes TCP pour services internes
- [EXTRACTION POTENTIELLEMENT MANQUÉE] Indices de contrainte transversale détectés dans le texte original (['chiffrement', 'encrypted']) mais aucune global_constraint n'a pu être extraite, même après une tentative dédiée avec indice explicite. Vérifiez manuellement si le texte contient une exigence de sécurité/conformité qui s'applique à plusieurs composants ou à toute l'application.
- unmapped_requirements: 9 exigence(s) générée(s) en best-effort — voir section 6 ci-dessus.
- unmapped_requirements: {'requirement': "Namespace 'ecommerce'", 'suggested_kind': 'namespace'} (suggested_kind=namespace)
- unmapped_requirements: {'requirement': 'Composant Backend API Node.js (image myregistry/backend:2.5.0, 5 replicas, port 8080, DB_URL depuis secret, HPA min:3 max:10 CPU:65%, KEDA 00h-06h:2 09h-12h:10, sidecar Envoy, PDB min:3)', 'suggested_kind': 'component'} (suggested_kind=component)
- unmapped_requirements: {'requirement': 'Composant Grafana (1 replica, port 3000, exposé sur monitoring.mon-domaine.com)', 'suggested_kind': 'component'} (suggested_kind=component)
- unmapped_requirements: {'requirement': 'Composant PostgreSQL CrunchyData (3 instances, réplication synchrone, chiffrement encrypted-gold, sauvegardes, 10GB, sonde TCP, interne)', 'suggested_kind': 'component'} (suggested_kind=component)
- unmapped_requirements: {'requirement': 'Composant Prometheus (1 replica, port 9090)', 'suggested_kind': 'component'} (suggested_kind=component)
- unmapped_requirements: {'requirement': 'Composant Redis cache (image redis:7.2-alpine, 1 replica, port 6379, stockage 5GB, sonde TCP, interne)', 'suggested_kind': 'component'} (suggested_kind=component)
- unmapped_requirements: {'requirement': 'Hôtes Ingress supplémentaires (api.mon-domaine.com, monitoring.mon-domaine.com)', 'suggested_kind': 'ingress'} (suggested_kind=ingress)
- unmapped_requirements: {'requirement': 'Règles NetworkPolicy backend->redis/postgres', 'suggested_kind': 'network_policy'} (suggested_kind=network_policy)
- unmapped_requirements: {'requirement': 'Sondes de santé TCP pour services internes', 'suggested_kind': 'probes'} (suggested_kind=probes)

## Métriques d'exécution

- Latence totale du run : **122.537 s** (dont pipeline seul : 122.537 s)
- Appels LLM : **8** (0 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 118.038 s (moyenne 14.755 s/appel)
- Tokens consommés : **22841** (16832 prompt + 6009 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 36.555 | 7734 |
| Agent 1 - Analyse (self-check) | 3 | 19.132 | 6130 |
| Agent 1 - Analyse (réparation) | 2 | 41.564 | 5829 |
| Agent 1 - Analyse (contraintes globales) | 2 | 20.787 | 3148 |

## ⚠️ Le pipeline s'est arrêté en erreur

> Agent 2 : aucun composant disponible dans la NormalizedSpec (Agent 1 a échoué).