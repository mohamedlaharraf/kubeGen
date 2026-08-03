# Rapport de benchmark comparatif - Architectures A/B/C/D

Généré le 2026-08-03T13:15:18 · 1 scénarios · 1 architecture(s) évaluée(s).

> ⚠️ Architectures non encore implémentées au moment de ce run : elles n'apparaissent simplement pas dans ce tableau (voir `benchmark/adapters/__init__.py` pour le statut d'implémentation).

## Tableau comparatif (moyennes sur l'ensemble des scénarios)

| Architecture | Scénarios | Échecs | Latence moy. (s) | Tokens in moy. | Tokens out moy. | Coût moy. ($) | Coût total ($) | Validité k8s_validate (%) | Validité kube-linter (%) | Score énergie moy. (/100) |
|---|---|---|---|---|---|---|---|---|---|---|
| Architecture B - Pipeline séquentiel (5 agents) | 1 | 1 | 40.255 | N/A | N/A | N/A | 0 | 0.0% | N/A | N/A |

## Détail par scénario

| Architecture | Scénario | Latence (s) | Coût ($) | k8s_validate | kube-linter | Score énergie | Erreur |
|---|---|---|---|---|---|---|---|
| B_pipeline | 08_stateful_message_broker | 40.255 | N/A | ✖ | N/A | N/A | main.py a retourné le code 2 : > Agent 1 - Analyse : excepti |

## Notes méthodologiques

- **Validité syntaxique (k8s_validate)** : validateur déterministe commun (vendored depuis pipeline-kubegen), sans dépendance externe, appliqué de façon identique à toutes les architectures — voir `benchmark/validators/k8s_validate.py`.
- **Validité syntaxique (kube-linter)** : nécessite le binaire `kube-linter` sur le PATH ; `N/A` si absent (voir `benchmark/README.md`).
- **Score énergie** : rubrique statique pondérée (requests/limits, autoscaling, node scheduling, PodDisruptionBudget, probes), normalisée sur les critères applicables à chaque scénario — voir `benchmark/energy_score.py` pour le détail des poids.
- **Coût monétaire** : extrapolé depuis `benchmark/pricing.py` (tarifs à re-vérifier avant publication, voir avertissement dans ce fichier).