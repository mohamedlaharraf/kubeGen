"""benchmark/tests/test_mcda_ranking.py — teste compute_ranking() bout en
bout, avec des agrégats proches de ce que produit
report.aggregate_by_architecture() sur de vraies données de benchmark."""
import pytest

from benchmark.mcda_ranking import compute_ranking


def _aggregate(label, validity, energy, cost, latency):
    return {
        "architecture_label": label,
        "k8s_validate_validity_rate_pct": validity,
        "avg_energy_score": energy,
        "avg_cost_usd": cost,
        "avg_latency_seconds": latency,
    }


def test_architecture_strong_on_everything_ranks_first():
    aggregates = {
        "A": _aggregate("Architecture A", validity=100, energy=90, cost=0.005, latency=20),
        "B": _aggregate("Architecture B", validity=70, energy=60, cost=0.02, latency=90),
    }
    result = compute_ranking(aggregates)
    assert result.ranking[0] == "A"
    assert result.excluded == {}


def test_missing_criterion_excludes_architecture_not_crash():
    aggregates = {
        "A": _aggregate("Architecture A", validity=100, energy=90, cost=0.005, latency=20),
        "B": _aggregate("Architecture B", validity=70, energy=60, cost=None, latency=90),  # coût inconnu
    }
    result = compute_ranking(aggregates)
    assert result.ranking == ["A"]
    assert "B" in result.excluded
    assert "cost" in result.excluded["B"]


def test_all_missing_returns_empty_ranking_not_crash():
    aggregates = {
        "A": _aggregate("Architecture A", validity=None, energy=None, cost=None, latency=None),
    }
    result = compute_ranking(aggregates)
    assert result.ranking == []
    assert result.scores == {}
    assert "A" in result.excluded


def test_weights_sum_to_one_and_are_traceable():
    aggregates = {
        "A": _aggregate("Architecture A", validity=100, energy=90, cost=0.005, latency=20),
    }
    result = compute_ranking(aggregates)
    assert sum(result.weights.values()) == pytest.approx(1.0, abs=1e-9)
    assert set(result.weights.keys()) == {"validity_rate", "energy_score", "cost", "latency"}


def test_empty_aggregates_returns_empty_result():
    result = compute_ranking({})
    assert result.ranking == []
    assert result.excluded == {}
