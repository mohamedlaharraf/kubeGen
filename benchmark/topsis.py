"""
benchmark/topsis.py — TOPSIS (Technique for Order of Preference by
Similarity to Ideal Solution ; Hwang & Yoon, 1981).

Classe des ALTERNATIVES (ici : les architectures A/B/C/D) sur plusieurs
critères hétérogènes -- certains "plus haut = mieux" (bénéfice, ex: score
énergie), d'autres "plus bas = mieux" (coût, ex: latence). Contrairement
à une moyenne pondérée naïve, TOPSIS mesure la distance de chaque
alternative à une solution idéale (le meilleur score possible sur chaque
critère, même si aucune alternative réelle ne les atteint tous à la
fois) ET à une solution anti-idéale -- une alternative qui est "assez
bonne partout" est mieux classée qu'une alternative excellente sur un
critère et médiocre sur un autre, même à moyenne pondérée égale.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class TOPSISResult:
    scores: dict[str, float]          # alternative -> coefficient de proximité (0..1, plus haut = mieux classé)
    ranking: list[str]                # alternatives triées du meilleur au moins bon


def rank(
    alternatives: list[str],
    criteria: list[str],
    decision_matrix: dict[str, dict[str, float]],
    weights: dict[str, float],
    benefit_criteria: set[str],
) -> TOPSISResult:
    """
    `decision_matrix[alt][crit]` : valeur brute observée. `weights` :
    poids par critère (typiquement dérivés par `ahp.compute_weights`,
    mais n'importe quelle source de poids sommant à 1 convient).
    `benefit_criteria` : sous-ensemble de `criteria` où "plus haut est
    meilleur" (ex: validity_rate, energy_score) -- tout le reste est
    traité comme un critère de coût ("plus bas est meilleur", ex: cost,
    latency).
    """
    if not alternatives:
        return TOPSISResult(scores={}, ranking=[])

    # 1. Normalisation vectorielle par colonne (norme euclidienne) --
    # rend les critères comparables malgré des unités/échelles différentes
    # (secondes vs dollars vs pourcentage) sans avoir besoin de bornes
    # min/max arbitraires.
    norm_denom = {
        c: math.sqrt(sum(decision_matrix[a].get(c, 0.0) ** 2 for a in alternatives)) or 1.0
        for c in criteria
    }
    normalized = {
        a: {c: decision_matrix[a].get(c, 0.0) / norm_denom[c] for c in criteria}
        for a in alternatives
    }

    # 2. Pondération
    weighted = {
        a: {c: normalized[a][c] * weights.get(c, 0.0) for c in criteria}
        for a in alternatives
    }

    # 3. Solutions idéale (meilleure) et anti-idéale (pire), critère par critère
    ideal_best = {}
    ideal_worst = {}
    for c in criteria:
        values = [weighted[a][c] for a in alternatives]
        if c in benefit_criteria:
            ideal_best[c], ideal_worst[c] = max(values), min(values)
        else:
            ideal_best[c], ideal_worst[c] = min(values), max(values)

    # 4. Distances euclidiennes aux deux solutions de référence
    def _distance(a: str, ref: dict[str, float]) -> float:
        return math.sqrt(sum((weighted[a][c] - ref[c]) ** 2 for c in criteria))

    dist_best = {a: _distance(a, ideal_best) for a in alternatives}
    dist_worst = {a: _distance(a, ideal_worst) for a in alternatives}

    # 5. Coefficient de proximité : proche de 1 = proche de l'idéal ET
    # loin de l'anti-idéal -- c'est la synthèse en un seul score.
    scores = {
        a: round(dist_worst[a] / (dist_best[a] + dist_worst[a]), 4)
        if (dist_best[a] + dist_worst[a]) > 0 else 0.0
        for a in alternatives
    }

    ranking = sorted(alternatives, key=lambda a: scores[a], reverse=True)
    return TOPSISResult(scores=scores, ranking=ranking)
