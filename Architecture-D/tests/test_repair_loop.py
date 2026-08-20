"""
tests/test_repair_loop.py — vérifie le mécanisme central de l'Architecture C :
la boucle bornée agent5 -> repair -> agent5.

Deux scénarios, mockant call_llm dans chaque module qui l'importe
localement (from llm_client import call_llm lie une référence locale par
module -- patcher llm_client.call_llm seul n'affecterait pas ces
références déjà importées) :

1. test_repair_loop_fixes_gap_and_stops : un gap détecté, réparé avec
   succès, revérifié -> le pipeline s'arrête proprement après 1 seule
   tentative, sans repair_requests restantes.
2. test_repair_loop_bounded_when_gap_never_resolved : un gap JAMAIS résolu
   (pire cas) -> la boucle s'arrête quand même après MAX_REPAIR_ATTEMPTS,
   sans jamais tourner indéfiniment ni planter.
"""
import json
import re
from unittest.mock import patch

import pytest

from config import settings
from graph import build_pipeline
from schemas import PipelineState
from tests._debate_fakes import dispatch_agent4_debate_passthrough

PATCH_TARGETS = [
    "agents.agent1_analyse.call_llm",
    "agents.agent2_template.call_llm",
    "agents.agent3_validation.call_llm",
    "agents.agent4_debate.call_llm",
    "agents.agent5_verification.call_llm",
    "agents.agent_repair.call_llm",
]


@pytest.fixture(autouse=True)
def _fake_api_key():
    original = settings.GOOGLE_API_KEY
    settings.GOOGLE_API_KEY = "fake-key-for-testing"
    yield
    settings.GOOGLE_API_KEY = original


def _base_extraction_response():
    return json.dumps({
        "raw_user_request": "test", "namespace": "web", "architecture_type": "single",
        "components": [{"component_name": "web", "workload_type": "Deployment",
                         "image": "nginx:1.27", "replicas": 1}],
        "global_constraints": [{
            "text": "Tous les conteneurs doivent avoir le label team=platform",
            "scope": "all_containers", "category": "labeling",
        }],
        "unmapped_requirements": [], "ambiguities": [],
    })


_DEPLOYMENT_WITHOUT_LABEL = (
    "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: web\n"
    "  namespace: web\nspec:\n  replicas: 1\n"
    "  selector: {matchLabels: {app: web}}\n"
    "  template:\n    metadata: {labels: {app: web}}\n"
    "    spec:\n      containers:\n      - {name: web, image: nginx:1.27}\n"
)


def test_repair_loop_fixes_gap_and_stops():
    call_counts: dict[str, int] = {}

    def fake_call_llm(system_prompt, user_prompt, agent_name="", **kwargs):
        call_counts[agent_name] = call_counts.get(agent_name, 0) + 1
        n = call_counts[agent_name]

        if agent_name == "Agent 1 - Analyse (extraction)":
            return _base_extraction_response()
        if agent_name == "Agent 1 - Analyse (self-check)":
            return json.dumps({"gaps": []})
        if agent_name == "Agent 1 - Analyse (contraintes globales)":
            return json.dumps({"global_constraints": []})
        if agent_name == "Agent 2 - Template":
            return json.dumps({"manifest_yaml": _DEPLOYMENT_WITHOUT_LABEL,
                                "fields_addressed": [], "fields_left_open": []})
        if agent_name == "Agent 3 - Validation":
            m = user_prompt.split("Manifeste à valider :\n", 1)[1].split("\n\nNormalizedSpec")[0]
            return json.dumps({"manifest_yaml": m})
        if agent_name.startswith("Agent4-Debate-"):
            return dispatch_agent4_debate_passthrough(agent_name, user_prompt)
        if agent_name == "Agent 5 - Vérification finale":
            manifest = user_prompt.split("Manifeste final (avant vérification) :\n", 1)[1].split("\n\nNormalizedSpec")[0]
            if n == 1:
                assert "team: platform" not in manifest
                return json.dumps({
                    "manifest_yaml": manifest, "unresolved_items": [],
                    "repair_requests": [{
                        "target_resource": "Deployment/web", "target_agent": "agent2_template",
                        "missing_constraint": "label team=platform absent",
                        "reason": "global_constraints[0] non respectée",
                    }],
                    "fields_addressed": [], "warnings": [],
                })
            assert "team: platform" in manifest, (
                "la revérification doit lire le manifeste RÉPARÉ, pas "
                "l'original -- régression du bug déjà corrigé une fois "
                "(Agent 5 lisait manifest_v3_yaml au lieu de "
                "manifest_final_yaml sur le 2e passage)"
            )
            return json.dumps({"manifest_yaml": manifest, "unresolved_items": [],
                                "repair_requests": [], "fields_addressed": [], "warnings": []})
        if agent_name == "Réparation ciblée":
            return json.dumps({
                "corrected_document": {
                    "apiVersion": "apps/v1", "kind": "Deployment",
                    "metadata": {"name": "web", "namespace": "web"},
                    "spec": {"replicas": 1, "selector": {"matchLabels": {"app": "web"}},
                             "template": {"metadata": {"labels": {"app": "web", "team": "platform"}},
                                          "spec": {"containers": [{"name": "web", "image": "nginx:1.27"}]}}},
                },
                "applied": True, "note": "label ajouté",
            })
        raise AssertionError(f"agent_name non mocké : {agent_name!r}")

    patchers = [patch(t, side_effect=fake_call_llm) for t in PATCH_TARGETS]
    for p in patchers:
        p.start()
    try:
        result = build_pipeline().invoke(PipelineState(user_request="test"))
    finally:
        for p in patchers:
            p.stop()

    assert result.get("error") is None
    assert result.get("repair_attempt") == 1
    assert result.get("repair_requests") == []
    assert "team: platform" in result.get("manifest_final_yaml", "")
    assert call_counts["Agent 5 - Vérification finale"] == 2
    assert call_counts["Réparation ciblée"] == 1


def test_repair_loop_bounded_when_gap_never_resolved():
    call_counts: dict[str, int] = {}

    def fake_call_llm(system_prompt, user_prompt, agent_name="", **kwargs):
        call_counts[agent_name] = call_counts.get(agent_name, 0) + 1

        if agent_name == "Agent 1 - Analyse (extraction)":
            return json.dumps({
                "raw_user_request": "test", "namespace": "web", "architecture_type": "single",
                "components": [{"component_name": "web", "workload_type": "Deployment",
                                 "image": "nginx:1.27", "replicas": 1}],
                "global_constraints": [], "unmapped_requirements": [], "ambiguities": [],
            })
        if agent_name == "Agent 1 - Analyse (self-check)":
            return json.dumps({"gaps": []})
        if agent_name == "Agent 1 - Analyse (contraintes globales)":
            return json.dumps({"global_constraints": []})
        if agent_name == "Agent 2 - Template":
            return json.dumps({"manifest_yaml": _DEPLOYMENT_WITHOUT_LABEL,
                                "fields_addressed": [], "fields_left_open": []})
        if agent_name == "Agent 3 - Validation":
            m = user_prompt.split("Manifeste à valider :\n", 1)[1].split("\n\nNormalizedSpec")[0]
            return json.dumps({"manifest_yaml": m})
        if agent_name.startswith("Agent4-Debate-"):
            return dispatch_agent4_debate_passthrough(agent_name, user_prompt)
        if agent_name == "Agent 5 - Vérification finale":
            manifest = user_prompt.split("Manifeste final (avant vérification) :\n", 1)[1].split("\n\nNormalizedSpec")[0]
            # Trouve TOUJOURS le même gap, quoi qu'il arrive -- pire cas.
            return json.dumps({
                "manifest_yaml": manifest, "unresolved_items": [],
                "repair_requests": [{
                    "target_resource": "Deployment/web", "target_agent": "agent2_template",
                    "missing_constraint": "gap jamais résolu (test du pire cas)",
                    "reason": "test",
                }],
                "fields_addressed": [], "warnings": [],
            })
        if agent_name == "Réparation ciblée":
            doc_text = user_prompt.split(
                "Document YAML actuel (représenté en JSON, structure identique) :\n", 1
            )[1].split("\n\nAgent d'origine")[0]
            doc = eval(doc_text, {"__builtins__": {}})  # dict Python repr, contexte de test uniquement
            return json.dumps({"corrected_document": doc, "applied": False, "note": "impossible de corriger"})
        raise AssertionError(f"non mocké : {agent_name!r}")

    patchers = [patch(t, side_effect=fake_call_llm) for t in PATCH_TARGETS]
    for p in patchers:
        p.start()
    try:
        result = build_pipeline().invoke(PipelineState(user_request="test pire cas"))
    finally:
        for p in patchers:
            p.stop()

    assert result.get("error") is None, "le pipeline doit terminer proprement, jamais planter"
    assert result.get("repair_attempt") == 2, "doit s'arrêter EXACTEMENT à la borne, ni avant ni après"
    assert call_counts["Réparation ciblée"] == 2
    assert call_counts["Agent 5 - Vérification finale"] == 3  # détection + 2 revérifications
    # Le dernier gap non résolu doit rester visible, pas disparaître silencieusement.
    assert len(result.get("repair_requests", [])) == 1
