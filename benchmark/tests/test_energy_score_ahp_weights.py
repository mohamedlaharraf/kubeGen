"""benchmark/tests/test_energy_score_ahp_weights.py — vérifie que le
passage aux poids AHP (au lieu de poids choisis à la main) n'a rien
cassé dans le calcul du score énergie lui-même."""
import pytest

from benchmark.energy_score import score, _WEIGHTS


def test_weights_sum_to_100():
    assert sum(_WEIGHTS.values()) == pytest.approx(100.0, abs=0.1)


def test_weights_are_ordered_as_expected_from_pairwise_judgments():
    """Sanity check directionnel : sizing > autoscaling > node_scheduling
    > probes > disruption_budget, cohérent avec les jugements documentés
    dans energy_score.py (sizing jugé le plus important, PDB le moins)."""
    assert _WEIGHTS["resource_requests_limits"] > _WEIGHTS["autoscaling"]
    assert _WEIGHTS["autoscaling"] > _WEIGHTS["node_scheduling_efficiency"]
    assert _WEIGHTS["node_scheduling_efficiency"] > _WEIGHTS["probes"]
    assert _WEIGHTS["probes"] > _WEIGHTS["disruption_budget"]


def test_fully_optimized_deployment_scores_high():
    docs = [{
        "kind": "Deployment", "apiVersion": "apps/v1",
        "metadata": {"name": "api"},
        "spec": {
            "replicas": 3,
            "template": {"spec": {
                "affinity": {"nodeAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": {}}},
                "containers": [{
                    "name": "api",
                    "resources": {"requests": {"cpu": "100m", "memory": "128Mi"},
                                  "limits": {"cpu": "200m", "memory": "256Mi"}},
                    "livenessProbe": {"httpGet": {"path": "/", "port": 8080}},
                    "readinessProbe": {"httpGet": {"path": "/ready", "port": 8080}},
                }],
            }},
        },
    }, {
        "kind": "HorizontalPodAutoscaler", "apiVersion": "autoscaling/v2",
        "metadata": {"name": "api-hpa"},
        "spec": {"scaleTargetRef": {"name": "api"}, "minReplicas": 2, "maxReplicas": 10},
    }, {
        "kind": "PodDisruptionBudget", "apiVersion": "policy/v1",
        "metadata": {"name": "api-pdb"},
        "spec": {"minAvailable": 1},
    }]
    result = score(docs)
    assert result.score is not None
    assert result.score > 95  # tous les critères applicables sont satisfaits


def test_bare_deployment_with_nothing_scores_low():
    docs = [{
        "kind": "Deployment", "apiVersion": "apps/v1",
        "metadata": {"name": "api"},
        "spec": {"replicas": 1, "template": {"spec": {"containers": [{"name": "api"}]}}},
    }]
    result = score(docs)
    assert result.score is not None
    assert result.score < 20  # rien n'est configuré


def test_empty_docs_returns_none_score():
    result = score([])
    assert result.score is None
