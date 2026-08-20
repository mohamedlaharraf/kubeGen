"""tests/test_admission_policies.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.admission_policies import generate_admission_policy_skeletons  # noqa: E402


def test_known_pattern_resource_limits_generates_policy():
    r = generate_admission_policy_skeletons(["exige des limits de ressources sur tous les pods"])
    assert len(r["addressed"]) == 1
    assert r["left_open"] == []
    assert "require-resource-limits" in r["manifest_yaml"]
    assert "kind: ClusterPolicy" in r["manifest_yaml"]


def test_unknown_pattern_is_left_open_not_hallucinated():
    r = generate_admission_policy_skeletons(["ne jamais autoriser plus de 3 conteneurs par pod"])
    assert r["addressed"] == []
    assert len(r["left_open"]) == 1
    assert r["manifest_yaml"] == ""


def test_multiple_descriptions_matching_same_pattern_deduplicated():
    r = generate_admission_policy_skeletons([
        "exige des limits CPU", "exige aussi des limits mémoire",
    ])
    # Les deux matchent le même pattern -> une seule policy générée
    assert r["manifest_yaml"].count("kind: ClusterPolicy") == 1


def test_generated_policies_default_to_audit_not_enforce():
    r = generate_admission_policy_skeletons(["exige des limits de ressources"])
    assert "validationFailureAction: Audit" in r["manifest_yaml"]
    assert "Enforce" not in r["manifest_yaml"]


def test_empty_input_produces_nothing():
    r = generate_admission_policy_skeletons([])
    assert r == {"manifest_yaml": "", "addressed": [], "left_open": []}
