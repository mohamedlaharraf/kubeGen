"""
benchmark/mcda_ranking.py — classement global des architectures (A/B/C/D)
par analyse multicritère : AHP pour les poids, TOPSIS pour le classement.

Répond à un problème différent de energy_score.py (qui note UN manifeste
sur des sous-critères internes). Ici, les "alternatives" sont les
ARCHITECTURES elles-mêmes, et les critères sont hétérogènes par nature
(certains à minimiser -- coût, latence ; d'autres à maximiser -- validité,
score énergie) : c'est exactement le cas d'usage pour lequel TOPSIS existe,
plutôt qu'une simple moyenne pondérée qui traiterait "bas" et "haut"
identiquement sans distinction de sens.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ahp import compute_weights
from .topsis import rank as topsis_rank

# ---------------------------------------------------------------------------
# Poids DÉRIVÉS PAR AHP pour les 4 critères de comparaison du benchmark.
#
# Matrice de comparaisons par paires (échelle de Saaty) : justification
# résumée par ligne, pour un benchmark de GÉNÉRATION DE MANIFESTES K8S
# (pas un benchmark générique) :
#
# - validity_rate : un manifeste syntaxiquement/structurellement invalide
#   ne peut pas être déployé -- rend tout le reste (énergie, coût, temps)
#   sans objet. Nettement plus important que coût et latence (5), et
#   modérément plus important que le score énergie lui-même (3) : un
#   manifeste doit d'abord être VALIDE avant que son optimisation
#   énergétique ait un sens.
# - energy_score : c'est la question de recherche centrale de ce projet
#   (comparer les architectures sur leur capacité à produire des
#   manifestes énergétiquement efficaces) -- modérément plus important
#   que coût et latence (2), qui sont des préoccupations pratiques
#   d'adoption, pas la question de fond.
# - cost vs latency : les deux sont des critères d'EFFICACITÉ DU
#   PROCESSUS DE GÉNÉRATION (pas du manifeste produit), d'importance
#   comparable ; coût légèrement plus important (2) parce qu'il a un
#   impact direct et récurrent en production, alors que la latence de
#   génération est un coût ponctuel, one-shot par manifeste.
#
# Ratio de cohérence CR = 0.0243 (<< 0.10) : jugements cohérents entre eux.
# ---------------------------------------------------------------------------
_AHP_LABELS = ["validity_rate", "energy_score", "cost", "latency"]
_AHP_MATRIX = [
    #                 validity  energy  cost  latency
    [1,     3,    5,    5],     # validity_rate
    [1 / 3, 1,    2,    2],     # energy_score
    [1 / 5, 1 / 2, 1,   2],     # cost
    [1 / 5, 1 / 2, 1 / 2, 1],   # latency
]
_AHP_RESULT = compute_weights(_AHP_LABELS, _AHP_MATRIX)
assert _AHP_RESULT.is_consistent, (
    f"Matrice AHP des critères de classement incohérente "
    f"(CR={_AHP_RESULT.consistency_ratio}) -- revoir les jugements."
)
CRITERIA_WEIGHTS = _AHP_RESULT.weights  # {"validity_rate": ..., "energy_score": ..., "cost": ..., "latency": ...}

_BENEFIT_CRITERIA = {"validity_rate", "energy_score"}  # plus haut = mieux ; cost/latency = plus bas = mieux


@dataclass
class MCDARankingResult:
    scores: dict[str, float]              # architecture_id -> coefficient de proximité TOPSIS (0..1)
    ranking: list[str]                    # du meilleur au moins bon
    excluded: dict[str, str]               # architecture_id -> raison d'exclusion (donnée manquante)
    weights: dict[str, float]              # poids AHP utilisés (traçabilité)
    consistency_ratio: float


def compute_ranking(aggregates: dict[str, dict]) -> MCDARankingResult:
    """
    `aggregates` : sortie de `report.aggregate_by_architecture()`.

    Une architecture est EXCLUE du classement (pas plantée dessus) si un
    des 4 critères est `None` chez elle -- ex: coût inconnu parce
    qu'aucun run n'a eu de tokens connus. Un classement partiel avec les
    absences documentées est préférable à un classement qui masque
    silencieusement une donnée manquante par un 0 arbitraire (0 pour un
    coût "inconnu" serait lu comme "gratuit", ce qui avantagerait
    injustement l'architecture concernée).
    """
    decision_matrix: dict[str, dict[str, float]] = {}
    excluded: dict[str, str] = {}

    for arch_id, a in aggregates.items():
        row = {
            "validity_rate": a.get("k8s_validate_validity_rate_pct"),
            "energy_score": a.get("avg_energy_score"),
            "cost": a.get("avg_cost_usd"),
            "latency": a.get("avg_latency_seconds"),
        }
        missing = [k for k, v in row.items() if v is None]
        if missing:
            excluded[arch_id] = f"critère(s) manquant(s) : {missing}"
            continue
        decision_matrix[arch_id] = row

    alternatives = list(decision_matrix.keys())
    if not alternatives:
        return MCDARankingResult(
            scores={}, ranking=[], excluded=excluded,
            weights=CRITERIA_WEIGHTS, consistency_ratio=_AHP_RESULT.consistency_ratio,
        )

    topsis_result = topsis_rank(
        alternatives=alternatives,
        criteria=_AHP_LABELS,
        decision_matrix=decision_matrix,
        weights=CRITERIA_WEIGHTS,
        benefit_criteria=_BENEFIT_CRITERIA,
    )
    return MCDARankingResult(
        scores=topsis_result.scores, ranking=topsis_result.ranking, excluded=excluded,
        weights=CRITERIA_WEIGHTS, consistency_ratio=_AHP_RESULT.consistency_ratio,
    )
