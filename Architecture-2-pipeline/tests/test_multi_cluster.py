"""tests/test_multi_cluster.py"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.multi_cluster import generate_applicationset_skeleton  # noqa: E402


def test_empty_target_clusters_produces_nothing():
    assert generate_applicationset_skeleton("api", [], "default") == ""


def test_generates_valid_yaml():
    y = generate_applicationset_skeleton("api", ["prod-eu", "prod-us"], "payments")
    doc = yaml.safe_load(y)
    assert doc["kind"] == "ApplicationSet"
    assert doc["metadata"]["name"] == "api-multicluster"


def test_one_entry_per_target_cluster():
    y = generate_applicationset_skeleton("api", ["a", "b", "c"], "default")
    doc = yaml.safe_load(y)
    elements = doc["spec"]["generators"][0]["list"]["elements"]
    assert {e["cluster"] for e in elements} == {"a", "b", "c"}


def test_placeholders_are_explicit_and_unmistakable():
    y = generate_applicationset_skeleton("api", ["prod"], "default")
    assert "REMPLACER" in y
    assert "REMPLACER-PAR-URL-API-DU-CLUSTER-prod" in y


def test_namespace_is_propagated_to_destination():
    y = generate_applicationset_skeleton("api", ["prod"], "custom-ns")
    doc = yaml.safe_load(y)
    assert doc["spec"]["template"]["spec"]["destination"]["namespace"] == "custom-ns"
