"""
tests/test_generator_validator_loop.py — vérifie le DEUXIÈME mécanisme
de boucle de l'Architecture C : agent3_validation <-> agent2_generator_fix,
sur des `ValidationError` de schéma/sécurité, borné par MAX_ITERATIONS.

Distinct de tests/test_repair_loop.py (qui couvre la boucle agent5<->repair
sur des `RepairRequest`/global_constraints) : deux mécanismes indépendants,
deux fichiers de test indépendants.
"""
import json
import re
from unittest.mock import patch

import pytest

from config import settings
from graph import build_pipeline
from schemas import PipelineState

PATCH_TARGETS = [
    "agents.agent1_analyse.call_llm",
    "agents.agent2_template.call_llm",
    "agents.agent3_validation.call_llm",
    "agents.agent4_energie.call_llm",
    "agents.agent5_verification.call_llm",
    "agents.agent_repair.call_llm",
]

_DEPLOYMENT_NO_SECURITY_CONTEXT = (
    "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: api\n"
    "  namespace: web\nspec:\n  replicas: 1\n"
    "  selector: {matchLabels: {app: api}}\n"
    "  template:\n    metadata: {labels: {app: api}}\n"
    "    spec:\n      containers:\n      - {name: api, image: myregistry/api:1.0}\n"
)
_DEPLOYMENT_WITH_SECURITY_CONTEXT = (
    "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: api\n"
    "  namespace: web\nspec:\n  replicas: 1\n"
    "  selector: {matchLabels: {app: api}}\n"
    "  template:\n    metadata: {labels: {app: api}}\n"
    "    spec:\n      containers:\n      - name: api\n"
    "        image: myregistry/api:1.0\n"
    "        securityContext: {runAsNonRoot: true, allowPrivilegeEscalation: false}\n"
)


@pytest.fixture(autouse=True)
def _fake_api_key():
    original = settings.GOOGLE_API_KEY
    settings.GOOGLE_API_KEY = "fake-key-for-testing"
    yield
    settings.GOOGLE_API_KEY = original


def _extraction_response():
    return json.dumps({
        "raw_user_request": "test", "namespace": "web", "architecture_type": "single",
        "application_context": "API interne à trafic modéré.",
        "components": [{"component_name": "api", "workload_type": "Deployment",
                         "image": "myregistry/api:1.0", "replicas": 1}],
        "global_constraints": [], "unmapped_requirements": [], "ambiguities": [],
    })


def test_generator_validator_loop_fixes_error_and_proceeds():
    """Agent 3 détecte un securityContext manquant, Agent 2 le corrige sur
    retour, Agent 3 revalide propre -> le pipeline continue normalement
    vers Agent 4, en une seule itération."""
    call_counts: dict[str, int] = {}

    def fake_call_llm(system_prompt, user_prompt, agent_name="", **kwargs):
        call_counts[agent_name] = call_counts.get(agent_name, 0) + 1
        n = call_counts[agent_name]

        if agent_name == "Agent 1 - Analyse (extraction)":
            return _extraction_response()
        if agent_name == "Agent 1 - Analyse (self-check)":
            return json.dumps({"gaps": []})
        if agent_name == "Agent 1 - Analyse (contraintes globales)":
            return json.dumps({"global_constraints": []})
        if agent_name == "Agent 2 - Template":
            return json.dumps({"manifest_yaml": _DEPLOYMENT_NO_SECURITY_CONTEXT,
                                "fields_addressed": [], "fields_left_open": []})
        if agent_name == "Agent 3 - Validation":
            manifest = user_prompt.split("Manifeste à valider :\n", 1)[1].split("\n\nNormalizedSpec")[0]
            if n == 1:
                assert "securityContext" not in manifest
                return json.dumps({
                    "manifest_yaml": manifest,  # rien de mécanique à corriger
                    "checks_passed": [], "checks_failed_and_fixed": [],
                    "validation_errors": [{
                        "rule": "missing-security-context",
                        "message": "Aucun securityContext sur le conteneur 'api'",
                        "resource": "Deployment/api",
                    }],
                    "fields_addressed": [], "fields_left_open": [], "warnings": [],
                })
            # 2e passage (après correction du Générateur) : propre
            assert "securityContext" in manifest, (
                "la revalidation doit lire le manifeste CORRIGÉ (current_yaml "
                "mis à jour par run_generator_fix)"
            )
            return json.dumps({
                "manifest_yaml": manifest, "checks_passed": [], "checks_failed_and_fixed": [],
                "validation_errors": [], "fields_addressed": [], "fields_left_open": [], "warnings": [],
            })
        if agent_name == "Agent 2 - Correction sur retour":
            assert "missing-security-context" in user_prompt
            return json.dumps({
                "manifest_yaml": _DEPLOYMENT_WITH_SECURITY_CONTEXT,
                "fixes_applied": ["Deployment/api : ajout securityContext"],
                "notes": [],
            })
        if agent_name == "Agent 4 - Énergie":
            m = re.search(r"Manifeste validé de ce composant :\n(.*?)\n\nContexte", user_prompt, re.DOTALL)
            return json.dumps({"manifest_yaml": m.group(1) if m else "", "fields_addressed": []})
        if agent_name == "Agent 5 - Vérification finale":
            manifest = user_prompt.split("Manifeste final (avant vérification) :\n", 1)[1].split("\n\nNormalizedSpec")[0]
            return json.dumps({"manifest_yaml": manifest, "unresolved_items": [],
                                "repair_requests": [], "fields_addressed": [], "warnings": []})
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
    assert result.get("iteration_count") == 1
    assert result.get("validation_errors") == []
    assert "securityContext" in result.get("manifest_final_yaml", "")
    assert call_counts["Agent 3 - Validation"] == 2
    assert call_counts["Agent 2 - Correction sur retour"] == 1
    # La boucle de réparation (mécanisme distinct) ne doit PAS s'être
    # déclenchée ici -- rien à voir avec des global_constraints.
    assert call_counts.get("Réparation ciblée", 0) == 0


def test_generator_validator_loop_bounded_when_error_never_resolved():
    """Pire cas : l'erreur n'est jamais corrigée -> la boucle s'arrête à
    MAX_ITERATIONS et le pipeline continue quand même (pas de blocage)."""
    call_counts: dict[str, int] = {}

    def fake_call_llm(system_prompt, user_prompt, agent_name="", **kwargs):
        call_counts[agent_name] = call_counts.get(agent_name, 0) + 1

        if agent_name == "Agent 1 - Analyse (extraction)":
            return _extraction_response()
        if agent_name == "Agent 1 - Analyse (self-check)":
            return json.dumps({"gaps": []})
        if agent_name == "Agent 1 - Analyse (contraintes globales)":
            return json.dumps({"global_constraints": []})
        if agent_name == "Agent 2 - Template":
            return json.dumps({"manifest_yaml": _DEPLOYMENT_NO_SECURITY_CONTEXT,
                                "fields_addressed": [], "fields_left_open": []})
        if agent_name == "Agent 3 - Validation":
            manifest = user_prompt.split("Manifeste à valider :\n", 1)[1].split("\n\nNormalizedSpec")[0]
            # Trouve TOUJOURS la même erreur, quoi qu'il arrive -- pire cas.
            return json.dumps({
                "manifest_yaml": manifest, "checks_passed": [], "checks_failed_and_fixed": [],
                "validation_errors": [{
                    "rule": "missing-security-context",
                    "message": "jamais corrigé (test du pire cas)",
                    "resource": "Deployment/api",
                }],
                "fields_addressed": [], "fields_left_open": [], "warnings": [],
            })
        if agent_name == "Agent 2 - Correction sur retour":
            # Ne corrige RIEN -- renvoie le manifeste inchangé à chaque fois.
            return json.dumps({"manifest_yaml": _DEPLOYMENT_NO_SECURITY_CONTEXT,
                                "fixes_applied": [], "notes": ["correction impossible"]})
        if agent_name == "Agent 4 - Énergie":
            m = re.search(r"Manifeste validé de ce composant :\n(.*?)\n\nContexte", user_prompt, re.DOTALL)
            return json.dumps({"manifest_yaml": m.group(1) if m else "", "fields_addressed": []})
        if agent_name == "Agent 5 - Vérification finale":
            manifest = user_prompt.split("Manifeste final (avant vérification) :\n", 1)[1].split("\n\nNormalizedSpec")[0]
            return json.dumps({"manifest_yaml": manifest, "unresolved_items": [],
                                "repair_requests": [], "fields_addressed": [], "warnings": []})
        raise AssertionError(f"non mocké : {agent_name!r}")

    patchers = [patch(t, side_effect=fake_call_llm) for t in PATCH_TARGETS]
    for p in patchers:
        p.start()
    try:
        result = build_pipeline().invoke(PipelineState(user_request="test pire cas"))
    finally:
        for p in patchers:
            p.stop()

    assert result.get("error") is None, "le pipeline doit terminer proprement, jamais planter/bloquer"
    assert result.get("iteration_count") == settings.MAX_ITERATIONS
    assert call_counts["Agent 2 - Correction sur retour"] == settings.MAX_ITERATIONS
    # Agent 3 tourne 1 (détection initiale) + MAX_ITERATIONS (une revalidation par tentative)
    assert call_counts["Agent 3 - Validation"] == settings.MAX_ITERATIONS + 1
    # Le pipeline doit quand même arriver jusqu'au bout (pas de blocage).
    assert call_counts.get("Agent 4 - Énergie", 0) == 1
    assert call_counts.get("Agent 5 - Vérification finale", 0) == 1
    # L'erreur résiduelle doit rester visible, pas disparaître silencieusement.
    assert len(result.get("validation_errors", [])) == 1
