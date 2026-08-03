"""tests/test_cost_estimate.py — tests du dimensionnement basé métriques et
du calculateur de coût estimé (utils/cost_estimate.py)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.cost_estimate import (  # noqa: E402
    HistoricalMetrics, size_from_metrics, estimate_monthly_cost,
    PricingTable, _parse_quantity,
)


def test_parse_quantity_cpu_millicores():
    assert _parse_quantity("500m") == pytest.approx(0.5)
    assert _parse_quantity("2") == pytest.approx(2.0)


def test_parse_quantity_memory_binary_units():
    assert _parse_quantity("1Gi") == pytest.approx(1024 ** 3)
    assert _parse_quantity("512Mi") == pytest.approx(512 * 1024 ** 2)


def test_parse_quantity_invalid_raises():
    with pytest.raises(ValueError):
        _parse_quantity("pas-une-quantite")


def test_size_from_metrics_uses_p50_for_requests_p95_for_limits():
    metrics = HistoricalMetrics(cpu_p50="100m", cpu_p95="200m",
                                 memory_p50="128Mi", memory_p95="256Mi")
    sizing = size_from_metrics(metrics, safety_margin=1.0)

    assert sizing["requests"]["cpu"] == "100m"
    assert sizing["limits"]["cpu"] == "200m"
    assert sizing["requests"]["memory"] == "128Mi"
    assert sizing["limits"]["memory"] == "256Mi"
    assert "métriques" in sizing["source"]


def test_size_from_metrics_applies_safety_margin_on_limits_only():
    metrics = HistoricalMetrics(cpu_p50="100m", cpu_p95="200m",
                                 memory_p50="100Mi", memory_p95="200Mi")
    sizing = size_from_metrics(metrics, safety_margin=1.5)

    assert sizing["requests"]["cpu"] == "100m"  # inchangé
    assert sizing["limits"]["cpu"] == "300m"    # 200m * 1.5


def test_estimate_monthly_cost_scales_with_replicas():
    cost_1 = estimate_monthly_cost("api", "500m", "512Mi", replicas=1)
    cost_3 = estimate_monthly_cost("api", "500m", "512Mi", replicas=3)
    # Tolérance élargie pour absorber l'arrondi à 2 décimales fait dans la fonction
    assert cost_3.monthly_cost_eur == pytest.approx(cost_1.monthly_cost_eur * 3, abs=0.02)


def test_estimate_monthly_cost_custom_pricing():
    cheap = PricingTable(eur_per_vcpu_hour=0.01, eur_per_gb_ram_hour=0.001, hours_per_month=730)
    expensive = PricingTable(eur_per_vcpu_hour=0.10, eur_per_gb_ram_hour=0.02, hours_per_month=730)

    cost_cheap = estimate_monthly_cost("api", "1", "1Gi", replicas=1, pricing=cheap)
    cost_expensive = estimate_monthly_cost("api", "1", "1Gi", replicas=1, pricing=expensive)
    assert cost_expensive.monthly_cost_eur > cost_cheap.monthly_cost_eur


def test_estimate_monthly_cost_is_positive_and_reasonable():
    cost = estimate_monthly_cost("api", "250m", "512Mi", replicas=3)
    # Doit être positif et dans un ordre de grandeur plausible pour un
    # petit service (pas 0, pas des milliers d'euros)
    assert 0 < cost.monthly_cost_eur < 100
