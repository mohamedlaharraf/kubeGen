# Rapport de benchmark comparatif - Architectures A/B/C/D

Généré le 2026-08-30T18:06:00 · 6 scénarios · 4 architecture(s) évaluée(s).

> ⚠️ Architectures non encore implémentées au moment de ce run : elles n'apparaissent simplement pas dans ce tableau (voir `benchmark/adapters/__init__.py` pour le statut d'implémentation).

## Tableau comparatif (moyennes sur l'ensemble des scénarios)

| Architecture | Scénarios | Échecs | Latence moy. (s) | Tokens in moy. | Tokens out moy. | Coût moy. ($) | Coût total ($) | Validité k8s_validate (%) | Validité kube-linter (%) | Score énergie moy. (/100) |
|---|---|---|---|---|---|---|---|---|---|---|
| Architecture A - Agent unique (monolithique) | 6 | 0 | 24.625 | 740.5 | 815.5 | 0.0 | 0.002158 | 66.7% | 33.3% | 72.067 |
| Architecture B - Pipeline séquentiel (5 agents) | 6 | 0 | 729.515 | 28721 | 7641.667 | 0.006 | 0.033281 | 83.3% | 50.0% | 80.35 |
| Architecture C - Blackboard + réparation bornée | 6 | 0 | 758.514 | 34187.333 | 8615.333 | 0.006 | 0.038604 | 100.0% | 50.0% | 70.683 |
| Architecture D - Débat multi-agents (Consolidation/Sizing/Autoscaling + Juge) | 6 | 0 | 1137.329 | 63477.667 | 20237.167 | 0.013 | 0.080585 | 100.0% | 0.0% | 84.883 |

## Classement global (AHP + TOPSIS)

Poids des critères dérivés par AHP (Analytic Hierarchy Process) à partir d'une matrice de comparaisons par paires vérifiée cohérente (CR = 0.0243, seuil 0.10) — voir `benchmark/mcda_ranking.py` pour la matrice et sa justification. Classement des architectures par TOPSIS (distance à la solution idéale / anti-idéale) sur ces 4 critères pondérés : validité 56.6%, score énergie 20.7%, coût 13.3%, latence 9.4%.

| Rang | Architecture | Score TOPSIS (proximité à l'idéal) |
|---|---|---|
| 1 | Architecture C - Blackboard + réparation bornée | 0.6380 |
| 2 | Architecture A - Agent unique (monolithique) | 0.5471 |
| 3 | Architecture B - Pipeline séquentiel (5 agents) | 0.4974 |
| 4 | Architecture D - Débat multi-agents (Consolidation/Sizing/Autoscaling + Juge) | 0.4536 |

## Détail par scénario

| Architecture | Scénario | Latence (s) | Coût ($) | k8s_validate | kube-linter | Score énergie | Erreur |
|---|---|---|---|---|---|---|---|
| A_single_agent | 01_static_website | 21.28 | 0.000315 | ✔ | ✖ | 54.9 |  |
| A_single_agent | 02_simple_web_app_hpa | 24.69 | 0.000361 | ✔ | ✖ | 77.7 |  |
| A_single_agent | 03_nightly_cleanup_cronjob | 16.2 | 0.000251 | ✖ | ✔ | 72.1 |  |
| A_single_agent | 04_worker_queue_consumer | 22.25 | 0.000328 | ✖ | ✔ | 72.3 |  |
| A_single_agent | 05_internal_search_api_elasticsearch_vault | 31.02 | 0.000447 | ✔ | ✖ | 77.7 |  |
| A_single_agent | 06_analytics_api_postgres_pci_dapr | 32.31 | 0.000456 | ✔ | ✖ | 77.7 |  |
| B_pipeline | 01_static_website | 351.98 | 0.003724 | ✔ | ✖ | 82.8 |  |
| B_pipeline | 02_simple_web_app_hpa | 1165.759 | 0.006525 | ✔ | ✖ | 83.9 |  |
| B_pipeline | 03_nightly_cleanup_cronjob | 457.19 | 0.003825 | ✔ | ✔ | 72.1 |  |
| B_pipeline | 04_worker_queue_consumer | 878.616 | 0.005742 | ✖ | ✔ | 82.8 |  |
| B_pipeline | 05_internal_search_api_elasticsearch_vault | 709.155 | 0.006787 | ✔ | ✖ | 77.7 |  |
| B_pipeline | 06_analytics_api_postgres_pci_dapr | 814.389 | 0.006678 | ✔ | ✔ | 82.8 |  |
| C_blackboard | 01_static_website | 378.476 | 0.003894 | ✔ | ✔ | 54.9 |  |
| C_blackboard | 02_simple_web_app_hpa | 636.12 | 0.005601 | ✔ | ✖ | 83.9 |  |
| C_blackboard | 03_nightly_cleanup_cronjob | 655.796 | 0.004864 | ✔ | ✔ | 72.1 |  |
| C_blackboard | 04_worker_queue_consumer | 1017.307 | 0.007165 | ✔ | ✔ | 82.8 |  |
| C_blackboard | 05_internal_search_api_elasticsearch_vault | 1053.669 | 0.009006 | ✔ | ✖ | 46.5 |  |
| C_blackboard | 06_analytics_api_postgres_pci_dapr | 809.718 | 0.008074 | ✔ | ✖ | 83.9 |  |
| D_debate | 01_static_website | 1080.686 | 0.013437 | ✔ | ✖ | 72.1 |  |
| D_debate | 02_simple_web_app_hpa | 1063.932 | 0.01283 | ✔ | ✖ | 93.8 |  |
| D_debate | 03_nightly_cleanup_cronjob | 1049.224 | 0.011051 | ✔ | ✖ | 100.0 |  |
| D_debate | 04_worker_queue_consumer | 974.088 | 0.01123 | ✔ | ✖ | 100.0 |  |
| D_debate | 05_internal_search_api_elasticsearch_vault | 1136.236 | 0.013783 | ✔ | ✖ | 62.6 |  |
| D_debate | 06_analytics_api_postgres_pci_dapr | 1519.807 | 0.018254 | ✔ | ✖ | 80.8 |  |

## Notes méthodologiques

- **Validité syntaxique (k8s_validate)** : validateur déterministe commun (vendored depuis pipeline-kubegen), sans dépendance externe, appliqué de façon identique à toutes les architectures — voir `benchmark/validators/k8s_validate.py`.
- **Validité syntaxique (kube-linter)** : nécessite le binaire `kube-linter` sur le PATH ; `N/A` si absent (voir `benchmark/README.md`).
- **Score énergie** : rubrique pondérée (requests/limits, autoscaling, node scheduling, PodDisruptionBudget, probes), poids dérivés par AHP (matrice de comparaisons par paires vérifiée cohérente, CR < 0.10) plutôt que choisis à la main, normalisée sur les critères applicables à chaque scénario — voir `benchmark/energy_score.py` et `benchmark/ahp.py`.
- **Classement global** : AHP pour les poids des 4 critères (validité, énergie, coût, latence), TOPSIS pour classer les architectures par distance à la solution idéale/anti-idéale — voir `benchmark/mcda_ranking.py` et `benchmark/topsis.py`. Préféré à une moyenne pondérée simple parce qu'une architecture "bonne partout" doit être distinguée d'une architecture excellente sur un seul critère et médiocre ailleurs, à moyenne égale.
- **Coût monétaire** : extrapolé depuis `benchmark/pricing.py` (tarifs à re-vérifier avant publication, voir avertissement dans ce fichier).