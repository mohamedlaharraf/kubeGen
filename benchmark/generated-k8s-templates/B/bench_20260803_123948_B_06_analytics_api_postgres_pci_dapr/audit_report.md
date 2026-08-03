# Rapport d'audit du pipeline

## 1. Demande utilisateur (vue par l'Agent 1 uniquement)

_(indisponible)_

## 3. Auto-vérification Agent 1


## 4. Rapports par agent

## 7. Aucun point ouvert détecté ✅


## Métriques d'exécution

- Latence totale du run : **16.553 s** (dont pipeline seul : 16.553 s)
- Appels LLM : **6** (6 échoué(s)/retenté(s))
- Latence cumulée des appels LLM : 5.632 s (moyenne 0.939 s/appel)
- Tokens consommés : _inconnus_ (mode offline, ou le SDK n'a pas renvoyé `usage_metadata` pour cet appel)

| Agent | Appels | Latence cumulée (s) | Tokens |
|---|---|---|---|
| Agent 1 - Analyse (extraction) | 6 (6 échoué(s)) | 5.632 | inconnu |

## ⚠️ Le pipeline s'est arrêté en erreur

> Agent 1 - Analyse : exception non gérée : ClientError: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash\nPlease retry in 47.648545533s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '47s'}]}}