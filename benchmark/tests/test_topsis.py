"""benchmark/tests/test_topsis.py — vérifie le module TOPSIS générique."""
import pytest

from benchmark.topsis import rank


def test_dominant_alternative_on_all_criteria_ranks_first():
    """Une alternative meilleure que toutes les autres sur TOUS les
    critères doit être classée première, quel que soit le poids."""
    alternatives = ["good", "bad"]
    criteria = ["speed", "cost"]
    decision_matrix = {
        "good": {"speed": 10, "cost": 1},   # rapide (bénéfice) ET pas cher (coût, donc bas=mieux)
        "bad": {"speed": 1, "cost": 10},    # lent ET cher
    }
    weights = {"speed": 0.5, "cost": 0.5}
    result = rank(alternatives, criteria, decision_matrix, weights, benefit_criteria={"speed"})
    assert result.ranking[0] == "good"
    assert result.scores["good"] > result.scores["bad"]


def test_balanced_alternative_beats_extreme_at_equal_weighted_average():
    """C'est LE point qui justifie TOPSIS plutôt qu'une moyenne pondérée
    simple : deux alternatives à moyenne pondérée strictement égale, mais
    l'une équilibrée sur les deux critères, l'autre extrême (excellente
    sur l'un, nulle sur l'autre) -- TOPSIS doit préférer l'équilibrée."""
    alternatives = ["balanced", "extreme"]
    criteria = ["a", "b"]
    decision_matrix = {
        "balanced": {"a": 5, "b": 5},    # moyenne pondérée = 5
        "extreme": {"a": 10, "b": 0},    # moyenne pondérée = 5, identique
    }
    weights = {"a": 0.5, "b": 0.5}
    result = rank(alternatives, criteria, decision_matrix, weights, benefit_criteria={"a", "b"})
    assert result.ranking[0] == "balanced"


def test_cost_criterion_favors_lower_value():
    """Un critère de coût (pas dans benefit_criteria) doit favoriser la
    valeur la plus BASSE, contrairement à un critère de bénéfice."""
    alternatives = ["cheap", "expensive"]
    criteria = ["price"]
    decision_matrix = {"cheap": {"price": 1}, "expensive": {"price": 100}}
    weights = {"price": 1.0}
    result = rank(alternatives, criteria, decision_matrix, weights, benefit_criteria=set())
    assert result.ranking[0] == "cheap"


def test_empty_alternatives_returns_empty_result():
    result = rank([], ["a"], {}, {"a": 1.0}, benefit_criteria={"a"})
    assert result.scores == {}
    assert result.ranking == []


def test_single_alternative_ranks_alone():
    result = rank(["only"], ["a"], {"only": {"a": 5}}, {"a": 1.0}, benefit_criteria={"a"})
    assert result.ranking == ["only"]


def test_mixed_benefit_and_cost_criteria_matches_manual_expectation():
    """Cas proche de l'usage réel (mcda_ranking.py) : 2 critères bénéfice,
    2 critères coût, une alternative meilleure sur tout doit gagner."""
    alternatives = ["arch_x", "arch_y"]
    criteria = ["validity", "energy", "cost", "latency"]
    decision_matrix = {
        "arch_x": {"validity": 100, "energy": 90, "cost": 0.01, "latency": 50},
        "arch_y": {"validity": 60, "energy": 40, "cost": 0.05, "latency": 200},
    }
    weights = {"validity": 0.5, "energy": 0.2, "cost": 0.15, "latency": 0.15}
    result = rank(
        alternatives, criteria, decision_matrix, weights,
        benefit_criteria={"validity", "energy"},
    )
    assert result.ranking[0] == "arch_x"


def test_missing_criterion_defaults_to_zero_not_crash():
    """Une alternative sans valeur pour un critère (dict.get -> absent)
    ne doit pas planter -- traité comme 0, pas une exception."""
    result = rank(
        ["a", "b"], ["x", "y"],
        {"a": {"x": 5, "y": 5}, "b": {"x": 5}},  # "b" n'a pas "y"
        {"x": 0.5, "y": 0.5}, benefit_criteria={"x", "y"},
    )
    assert "a" in result.ranking and "b" in result.ranking
