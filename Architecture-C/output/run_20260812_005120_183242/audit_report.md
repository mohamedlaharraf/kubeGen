# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

> Déploie une application e-commerce avec frontend React (3 replicas, port 3000, exposé sur shop.mon-domaine.com), backend API Node.js (5 replicas, port 8080), Redis cache (1 replica, port 6379), namespace ecommerce

## 2. Architecture détectée

- Type : **microservices** (3 composant(s))
  - `frontend` (Deployment), dépend de: ['backend']
  - `backend` (Deployment), dépend de: ['redis']
  - `redis` (Deployment)

- Auto-check réussi : **True**
- Tentatives de réparation internes : 0
- Hypothèses faites faute de précision de l'utilisateur :
  - `components[0].image` : Quelle est l'image exacte à utiliser pour le frontend React ? → hypothèse retenue : *Utilisation de l'image 'nginx:alpine' par défaut pour servir l'application React.* (confiance medium)
  - `components[1].image` : Quelle est l'image exacte à utiliser pour l'API backend Node.js ? → hypothèse retenue : *Utilisation de l'image 'node:18-alpine' par défaut.* (confiance medium)
  - `components[2].image` : Quelle version exacte de Redis utiliser ? → hypothèse retenue : *Utilisation de l'image 'redis:7-alpine'.* (confiance high)

## 4. Rapports par agent

### Agent 1 - Analyse
- Champs traités : ['architecture_type', 'namespace', 'components[frontend]', 'components[backend]', 'components[redis]']
- Actions :
  - Extraction initiale + 0 passe(s) de réparation interne
  - Architecture détectée : microservices (3 composant(s))
  - Contraintes globales (blackboard) : aucune détectée
  - Réparation de schéma : 1 tentative(s)
- Avertissements : ["Quelle est l'image exacte à utiliser pour le frontend React ?", "Quelle est l'image exacte à utiliser pour l'API backend Node.js ?", 'Quelle version exacte de Redis utiliser ?']

## 7. Aucun point ouvert détecté ✅


## Métriques d'exécution

- Latence totale du run : **76.499 s** (dont pipeline seul : 76.499 s)
- Appels LLM : **8** (3 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 70.147 s (moyenne 8.768 s/appel)
- Tokens consommés : **19382** (15458 prompt + 3924 completion)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 1 | 26.412 | 6858 |
| Agent 1 - Analyse (self-check) | 1 | 5.157 | 1509 |
| Agent 1 - Analyse (contraintes globales) | 1 | 4.772 | 1040 |
| Agent 1 - Analyse (réparation schéma) | 1 | 15.147 | 2961 |
| Agent 2 - Template | 4 (3 échoué(s)) | 18.66 | 7014 |

## ⚠️ Le pipeline s'est arrêté en erreur

> Agent 2 - Template : exception non gérée : 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash\nPlease retry in 23.232724403s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '23s'}]}}