"""
tests/test_agent3_unmapped_isolation.py

Bug réel corrigé : Agent 3 régénère tout le YAML via un appel LLM. Sans
isolation explicite, rien ne garantissait qu'il préserve le bloc
best-effort (`unmapped_requirements`, généré par l'Agent 2) — un LLM peut
tout à fait juger ce bloc "hors sujet" et l'omettre en réécrivant le
manifeste. `_split_off_unmapped_block` isole ce bloc AVANT l'appel LLM et
le réinjecte APRÈS, par code, quoi qu'ait fait le LLM entre-temps.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.agent3_validation import _split_off_unmapped_block, run_agent3, UNMAPPED_MARKER  # noqa: E402
import agents.agent3_validation as a3  # noqa: E402
from schemas import PipelineState, NormalizedSpec  # noqa: E402


MANIFEST_WITH_UNMAPPED = (
    "apiVersion: apps/v1\n"
    "kind: Deployment\n"
    "metadata:\n"
    "  name: analytics-api\n"
    "---\n"
    "apiVersion: v1\n"
    "kind: Service\n"
    "metadata:\n"
    "  name: analytics-api\n"
    "---\n"
    f"{UNMAPPED_MARKER} — non vérifiée, à valider manuellement.\n"
    "apiVersion: postgres-operator.crunchydata.com/v1beta1\n"
    "kind: PostgresCluster\n"
    "metadata:\n"
    "  name: analytics-db\n"
)


def test_split_isolates_unmapped_block():
    core, unmapped = _split_off_unmapped_block(MANIFEST_WITH_UNMAPPED)
    assert "PostgresCluster" not in core
    assert "analytics-api" in core
    assert "PostgresCluster" in unmapped
    assert UNMAPPED_MARKER in unmapped


def test_split_with_no_unmapped_block_returns_everything_as_core():
    manifest = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: x\n"
    core, unmapped = _split_off_unmapped_block(manifest)
    assert core == manifest
    assert unmapped == ""


def test_split_with_multiple_unmapped_documents():
    manifest = (
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: x\n"
        "---\n"
        f"{UNMAPPED_MARKER}\nkind: Foo\n"
        "---\n"
        f"{UNMAPPED_MARKER}\nkind: Bar\n"
    )
    core, unmapped = _split_off_unmapped_block(manifest)
    assert "kind: Foo" in unmapped and "kind: Bar" in unmapped
    assert "Foo" not in core and "Bar" not in core


def test_agent3_survives_llm_dropping_the_unmapped_block(monkeypatch):
    """Reproduit le risque exact : le LLM de l'Agent 3, en régénérant le
    YAML, "oublie" le bloc best-effort. Il doit quand même réapparaître
    dans manifest_v2_yaml, réinjecté par code."""

    def fake_llm_drops_unmapped(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        # Le LLM ne renvoie QUE le core, comme s'il avait "nettoyé" le
        # bloc best-effort en le jugeant hors sujet.
        core_only = (
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: analytics-api\n"
            "---\napiVersion: v1\nkind: Service\nmetadata:\n  name: analytics-api\n"
        )
        return json.dumps({
            "manifest_yaml": core_only,
            "checks_passed": ["apiVersion présent"],
            "checks_failed_and_fixed": [],
            "fields_addressed": ["component_name"],
            "fields_left_open": [],
            "warnings": [],
        })

    monkeypatch.setattr(a3, "call_llm", fake_llm_drops_unmapped)

    spec = NormalizedSpec.model_validate({
        "namespace": "data",
        "raw_user_request": "test",
        "components": [{"component_name": "analytics-api", "image": "x:1"}],
    })
    state = PipelineState(user_request="test", spec=spec, manifest_v1_yaml=MANIFEST_WITH_UNMAPPED)

    result_state = run_agent3(state)

    assert result_state.error is None
    assert "PostgresCluster" in result_state.manifest_v2_yaml
    assert "analytics-api" in result_state.manifest_v2_yaml
