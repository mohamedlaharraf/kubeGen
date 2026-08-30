"""
benchmark/ahp.py — Analytic Hierarchy Process (Saaty, 1980).

Dérive des poids DÉFENDABLES à partir d'une matrice de comparaisons par
paires, plutôt que des poids choisis à la main. Le point central d'AHP,
souvent oublié quand on ne garde que "la formule du vecteur propre" : le
**ratio de cohérence (CR)**. Une matrice de jugements peut être
mathématiquement traitée même si elle est incohérente (A >> B >> C mais
C >> A) — CR quantifie cette incohérence et permet de refuser des poids
qui reposent sur des jugements contradictoires, au lieu de produire un
chiffre qui a l'air rigoureux sans l'être.

Convention : `matrix[i][j]` = combien le critère i est plus important que
le critère j, sur l'échelle de Saaty (1 = importance égale, 3 = un peu
plus important, 5 = nettement plus important, 7 = très nettement, 9 =
extrême ; valeurs intermédiaires 2/4/6/8 possibles ; matrix[j][i] doit
être l'inverse 1/matrix[i][j] -- c'est à l'appelant de construire une
matrice réciproque valide, `compute_weights` ne le vérifie pas lui-même
au-delà du calcul de CR, qui le révèle indirectement s'il est élevé).
"""
from __future__ import annotations

from dataclasses import dataclass

# Indice aléatoire (Random Index) de Saaty, pour n=1..10 -- valeur de
# référence utilisée pour normaliser CI en CR. Une matrice n x n
# entièrement aléatoire aurait, en moyenne, ce niveau d'incohérence.
_RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}

# Seuil usuel (Saaty) : au-delà, la matrice est jugée trop incohérente
# pour que les poids qui en sortent soient dignes de confiance.
CONSISTENCY_THRESHOLD = 0.10


@dataclass
class AHPResult:
    weights: dict[str, float]        # somme = 1.0
    consistency_ratio: float
    is_consistent: bool              # consistency_ratio < CONSISTENCY_THRESHOLD
    lambda_max: float                # valeur propre principale (diagnostic)


def compute_weights(labels: list[str], matrix: list[list[float]]) -> AHPResult:
    """
    `labels[i]` nomme la ligne/colonne i de `matrix`. Retourne les poids
    (méthode de la moyenne des lignes normalisées -- approximation
    standard du vecteur propre principal, suffisante en pratique et
    beaucoup plus lisible qu'une décomposition propre complète pour ce
    genre de matrice de petite taille) ainsi que le ratio de cohérence.

    N'échoue PAS si CR >= CONSISTENCY_THRESHOLD -- retourne quand même les
    poids, avec `is_consistent=False`, pour que l'appelant décide quoi en
    faire (les rejeter, les utiliser en le signalant, etc.) plutôt que de
    lever une exception qui casserait un run pour un problème de méthode,
    pas de données.
    """
    n = len(labels)
    if n < 1 or any(len(row) != n for row in matrix):
        raise ValueError("La matrice doit être carrée, de même taille que `labels`.")

    col_sums = [sum(matrix[i][j] for i in range(n)) for j in range(n)]
    normalized = [[matrix[i][j] / col_sums[j] for j in range(n)] for i in range(n)]
    weights_list = [sum(row) / n for row in normalized]

    # lambda_max : moyenne de (M . w)_i / w_i -- diagnostic standard AHP
    weighted_sum = [sum(matrix[i][j] * weights_list[j] for j in range(n)) for i in range(n)]
    lambda_max = sum(weighted_sum[i] / weights_list[i] for i in range(n)) / n

    ci = (lambda_max - n) / (n - 1) if n > 1 else 0.0
    ri = _RANDOM_INDEX.get(n, 1.49)
    cr = (ci / ri) if ri > 0 else 0.0

    return AHPResult(
        weights=dict(zip(labels, weights_list)),
        consistency_ratio=round(cr, 4),
        is_consistent=cr < CONSISTENCY_THRESHOLD,
        lambda_max=round(lambda_max, 4),
    )
