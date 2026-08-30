"""tests/test_agent4_metrics_override.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.agent4_energie import _apply_metrics_override  # noqa: E402

BASE_YAML = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkout-api
spec:
  template:
    spec:
      containers:
        - name: checkout-api
          image: x:1.0
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
"""

VALID_METRICS = {"cpu_p50": "150m", "cpu_p95": "300m",
                  "memory_p50": "200Mi", "memory_p95": "350Mi"}


def test_override_replaces_requests_and_limits():
    new_yaml, applied = _apply_metrics_override(BASE_YAML, "checkout-api", VALID_METRICS)
    assert applied is True
    assert "cpu: 150m" in new_yaml  # requests = p50
    assert "memory: 200Mi" in new_yaml
    assert "cpu: 100m" not in new_yaml  # ancienne valeur LLM/heuristique disparue


def test_override_no_match_leaves_yaml_and_returns_false():
    new_yaml, applied = _apply_metrics_override(BASE_YAML, "unknown-component", VALID_METRICS)
    assert applied is False
    assert new_yaml == BASE_YAML  # inchangé


def test_override_invalid_metrics_format_degrades_gracefully():
    new_yaml, applied = _apply_metrics_override(
        BASE_YAML, "checkout-api", {"cpu_p50": "nawak"}
    )
    assert applied is False
    assert new_yaml == BASE_YAML


def test_override_invalid_yaml_degrades_gracefully():
    new_yaml, applied = _apply_metrics_override("not: [valid yaml", "checkout-api", VALID_METRICS)
    assert applied is False
