"""
tests/test_repair_field_preservation.py — vérifie le filet de sécurité
contre la perte silencieuse de champs par le noeud de réparation ciblée
(agents/agent_repair.py). Rejoue le bug réel observé en production :
une réparation qui rétablissait `privileged`/`runAsUser` sur le
securityContext d'un conteneur a fait disparaître `readOnlyRootFilesystem`
au passage, sans que rien ne le signale.
"""
import json
from unittest.mock import patch

import pytest

from config import settings
from agents.agent_repair import (
    _merge_preserving_missing_fields,
    _restored_paths,
    _pair_list_items_by_name,
    run_repair,
)
from schemas import PipelineState, RepairRequest


@pytest.fixture(autouse=True)
def _fake_api_key():
    original = settings.GOOGLE_API_KEY
    settings.GOOGLE_API_KEY = "fake-key-for-testing"
    yield
    settings.GOOGLE_API_KEY = original


ORIGINAL_DOC = {
    "kind": "Deployment",
    "metadata": {"name": "kernel-debugger", "namespace": "ops"},
    "spec": {"template": {"spec": {"containers": [{
        "name": "kernel-debugger",
        "securityContext": {
            "privileged": False, "runAsUser": 10001, "runAsNonRoot": True,
            "readOnlyRootFilesystem": False, "allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
        },
    }]}}},
}

# Le correcteur reconstruit le JSON, corrige privileged/runAsUser comme
# demandé, mais "oublie" readOnlyRootFilesystem -- exactement le bug observé.
CORRECTED_DOC_MISSING_FIELD = {
    "kind": "Deployment",
    "metadata": {"name": "kernel-debugger", "namespace": "ops"},
    "spec": {"template": {"spec": {"containers": [{
        "name": "kernel-debugger",
        "securityContext": {
            "privileged": True, "runAsUser": 0, "runAsNonRoot": False,
            "allowPrivilegeEscalation": True, "capabilities": {"drop": ["ALL"]},
        },
    }]}}},
}


# --- unités pures : merge / diff -----------------------------------------

def test_restored_paths_detects_field_dropped_inside_a_list_item():
    """Le cas exact du bug : le champ manquant est dans un élément de
    LISTE (containers), pas au premier niveau du dict."""
    paths = _restored_paths(ORIGINAL_DOC, CORRECTED_DOC_MISSING_FIELD)
    assert paths == ["spec.template.spec.containers[kernel-debugger].securityContext.readOnlyRootFilesystem"]


def test_merge_restores_missing_field_while_keeping_intentional_changes():
    merged = _merge_preserving_missing_fields(ORIGINAL_DOC, CORRECTED_DOC_MISSING_FIELD)
    sc = merged["spec"]["template"]["spec"]["containers"][0]["securityContext"]
    assert sc["readOnlyRootFilesystem"] is False  # restauré
    assert sc["privileged"] is True                # correction volontaire préservée
    assert sc["runAsUser"] == 0                     # correction volontaire préservée
    assert sc["runAsNonRoot"] is False               # correction volontaire préservée


def test_merge_is_noop_when_nothing_is_missing():
    identical = json.loads(json.dumps(ORIGINAL_DOC))  # copie profonde
    assert _restored_paths(ORIGINAL_DOC, identical) == []
    assert _merge_preserving_missing_fields(ORIGINAL_DOC, identical) == identical


def test_pair_list_items_returns_none_without_reliable_name_key():
    """Pas de clé `name` fiable -> abandon du pairing, pas de faux positif."""
    assert _pair_list_items_by_name([{"foo": 1}], [{"foo": 2}]) is None
    assert _pair_list_items_by_name([], [{"name": "x"}]) is None


def test_merge_does_not_restore_a_field_the_corrector_never_had():
    """Un champ absent de l'original ET du corrigé ne doit évidemment pas
    apparaître comme "restauré" -- seule une perte réelle compte."""
    original = {"a": 1}
    corrected = {"a": 2}
    assert _restored_paths(original, corrected) == []


# --- intégration : run_repair complet -------------------------------------

def test_run_repair_restores_dropped_field_and_logs_it():
    """Bout en bout : run_repair() doit produire un manifeste où le champ
    oublié est bien restauré, ET le signaler explicitement dans le
    rapport (pas silencieusement)."""
    def fake_call_llm(system_prompt, user_prompt, agent_name="", **kwargs):
        assert agent_name == "Réparation ciblée"
        return json.dumps({
            "corrected_document": CORRECTED_DOC_MISSING_FIELD,
            "applied": True,
            "note": "Rétablissement des privilèges demandés explicitement.",
        })

    manifest_yaml = (
        "kind: Deployment\nmetadata:\n  name: kernel-debugger\n  namespace: ops\n"
        "spec:\n  template:\n    spec:\n      containers:\n"
        "      - name: kernel-debugger\n        securityContext:\n"
        "          privileged: false\n          runAsUser: 10001\n"
        "          runAsNonRoot: true\n          readOnlyRootFilesystem: false\n"
        "          allowPrivilegeEscalation: false\n"
        "          capabilities: {drop: [ALL]}\n"
    )
    state = PipelineState(
        user_request="test",
        manifest_final_yaml=manifest_yaml,
        repair_requests=[RepairRequest(
            target_resource="Deployment/kernel-debugger",
            target_agent="agent2_template",
            missing_constraint="Rétablir privileged: true et runAsUser: 0",
            reason="Exigence explicite de la spec pour cet outil de diagnostic.",
        )],
    )

    with patch("agents.agent_repair.call_llm", side_effect=fake_call_llm):
        result = run_repair(state)

    assert result.error is None
    assert "readOnlyRootFilesystem: false" in result.manifest_final_yaml
    assert "privileged: true" in result.manifest_final_yaml

    report = result.reports[-1]
    assert any("restauré" in action for action in report.actions), (
        "la restauration automatique doit être visible dans le rapport, "
        "pas seulement appliquée silencieusement"
    )
