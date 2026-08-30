"""benchmark/tests/test_ahp.py — vérifie le module AHP générique."""
import pytest

from benchmark.ahp import compute_weights, CONSISTENCY_THRESHOLD


def test_equal_importance_matrix_gives_equal_weights():
    """Tous les critères jugés d'importance égale (matrice de 1) -> poids
    strictement égaux, et parfaitement cohérent par construction (CR=0)."""
    labels = ["a", "b", "c"]
    matrix = [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
    result = compute_weights(labels, matrix)
    assert result.weights["a"] == pytest.approx(1 / 3, abs=1e-6)
    assert result.weights["b"] == pytest.approx(1 / 3, abs=1e-6)
    assert result.weights["c"] == pytest.approx(1 / 3, abs=1e-6)
    assert result.consistency_ratio == pytest.approx(0.0, abs=1e-6)
    assert result.is_consistent is True


def test_weights_sum_to_one():
    labels = ["a", "b", "c", "d", "e"]
    matrix = [
        [1, 2, 3, 5, 4],
        [1/2, 1, 2, 4, 3],
        [1/3, 1/2, 1, 3, 2],
        [1/5, 1/4, 1/3, 1, 1/2],
        [1/4, 1/3, 1/2, 2, 1],
    ]
    result = compute_weights(labels, matrix)
    assert sum(result.weights.values()) == pytest.approx(1.0, abs=1e-9)


def test_dominant_criterion_gets_highest_weight():
    """Un critère jugé nettement plus important que les deux autres doit
    ressortir avec le poids le plus élevé -- sanity check directionnel."""
    labels = ["dominant", "b", "c"]
    matrix = [
        [1, 8, 8],
        [1/8, 1, 1],
        [1/8, 1, 1],
    ]
    result = compute_weights(labels, matrix)
    assert result.weights["dominant"] > result.weights["b"]
    assert result.weights["dominant"] > result.weights["c"]
    assert result.weights["dominant"] > 0.7  # nettement dominant


def test_incoherent_matrix_is_flagged_not_silently_accepted():
    """Matrice délibérément incohérente (jugements contradictoires en
    cycle : a>b, b>c, c>a, tous fortement) -- doit ressortir avec un CR
    élevé et is_consistent=False, PAS une exception, PAS un chiffre
    silencieusement traité comme fiable."""
    labels = ["a", "b", "c"]
    matrix = [
        [1,   9,   1/9],
        [1/9, 1,   9],
        [9,   1/9, 1],
    ]
    result = compute_weights(labels, matrix)
    assert result.consistency_ratio > CONSISTENCY_THRESHOLD
    assert result.is_consistent is False
    # Les poids sont quand même retournés (l'appelant décide quoi en faire)
    assert sum(result.weights.values()) == pytest.approx(1.0, abs=1e-9)


def test_energy_score_matrix_used_in_production_is_consistent():
    """La matrice réellement utilisée dans energy_score.py doit rester
    cohérente -- si ce test casse un jour après une modification de la
    matrice, c'est le signal qu'il faut revoir les jugements avant de
    changer les poids en production."""
    from benchmark.energy_score import _AHP_RESULT
    assert _AHP_RESULT.is_consistent
    assert _AHP_RESULT.consistency_ratio < CONSISTENCY_THRESHOLD


def test_mcda_ranking_matrix_used_in_production_is_consistent():
    from benchmark.mcda_ranking import _AHP_RESULT
    assert _AHP_RESULT.is_consistent
    assert _AHP_RESULT.consistency_ratio < CONSISTENCY_THRESHOLD


def test_rejects_non_square_matrix():
    with pytest.raises(ValueError):
        compute_weights(["a", "b"], [[1, 2, 3], [1, 1, 1]])
