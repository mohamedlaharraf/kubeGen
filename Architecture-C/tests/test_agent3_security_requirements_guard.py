"""
tests/test_agent3_security_requirements_guard.py — vérifie qu'Agent 3 ne
contredit plus une posture de sécurité explicitement demandée par la spec
(bug réel observé : scénario "kernel-debugger" où privileged/root étaient
sciemment requis, mais flagués comme validation_error puis "corrigés" par
le Générateur, avant qu'Agent 5/la réparation ne rétablisse la demande
originale -- deux mécanismes qui se contredisaient faute de contexte
partagé).
"""
import json
from unittest.mock import patch

import pytest

from config import settings
from agents.agent3_validation import _explicitly_requested, run_agent3
from schemas import PipelineState, NormalizedSpec, ServiceComponent, ValidationError


@pytest.fixture(autouse=True)
def _fake_api_key():
    original = settings.GOOGLE_API_KEY
    settings.GOOGLE_API_KEY = "fake-key-for-testing"
    yield
    settings.GOOGLE_API_KEY = original


# --- unité pure : _explicitly_requested -----------------------------------

def test_suppresses_privileged_error_when_explicitly_requested():
    error = ValidationError(
        rule="privileged-container",
        message="Le conteneur utilise privileged: true, risque majeur",
        resource="Deployment/kernel-debugger",
    )
    reqs = {"kernel-debugger": ["Mode privilégié et accès aux capabilities noyau (privileged: true)"]}
    assert _explicitly_requested(error, reqs) is True


def test_does_not_suppress_a_real_unrequested_security_gap():
    error = ValidationError(
        rule="privileged-container",
        message="Conteneur privilégié détecté",
        resource="Deployment/other-api",
    )
    reqs = {"other-api": ["Hardening par défaut standard"]}
    assert _explicitly_requested(error, reqs) is False


def test_does_not_suppress_when_component_has_no_requirements_at_all():
    error = ValidationError(rule="privileged-container", message="x", resource="Deployment/x")
    assert _explicitly_requested(error, {}) is False


def test_does_not_cross_contaminate_between_components():
    """Une exigence explicite sur UN composant ne doit pas supprimer une
    erreur détectée sur un AUTRE composant."""
    error = ValidationError(rule="privileged-container", message="x", resource="Deployment/api-b")
    reqs = {"api-a": ["Mode privilégié requis (privileged: true)"]}  # composant différent
    assert _explicitly_requested(error, reqs) is False


# --- intégration : run_agent3 complet --------------------------------------

def test_run_agent3_filters_out_error_matching_explicit_requirement():
    spec = NormalizedSpec(
        raw_user_request="x", namespace="ops", architecture_type="single",
        components=[ServiceComponent(
            component_name="kernel-debugger", workload_type="Deployment", image="x:latest",
            security_requirements=[
                "Mode privilégié et accès aux capabilities noyau (privileged: true)",
                "Exécution en root (runAsUser: 0)",
            ],
        )],
    )
    state = PipelineState(
        user_request="x", spec=spec,
        manifest_v1_yaml=(
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: kernel-debugger\n  namespace: ops\n"
            "spec:\n  template:\n    spec:\n      containers:\n"
            "      - name: kernel-debugger\n        securityContext: {privileged: true, runAsUser: 0}\n"
        ),
    )

    def fake_call_llm(system_prompt, user_prompt, agent_name="", **kwargs):
        # Le LLM (mal informé, ou ignorant l'instruction) flague quand
        # même -- c'est le filet DÉTERMINISTE qui doit rattraper.
        manifest = user_prompt.split("Manifeste à valider :\n", 1)[1].split("\n\nNormalizedSpec")[0]
        return json.dumps({
            "manifest_yaml": manifest,
            "checks_passed": [], "checks_failed_and_fixed": [],
            "validation_errors": [
                {"rule": "privileged-container", "message": "privileged: true détecté, risque majeur",
                 "resource": "Deployment/kernel-debugger"},
                {"rule": "run-as-root-user", "message": "runAsUser: 0, exécution en root",
                 "resource": "Deployment/kernel-debugger"},
            ],
            "fields_addressed": [], "fields_left_open": [], "warnings": [],
        })

    with patch("agents.agent3_validation.call_llm", side_effect=fake_call_llm):
        result = run_agent3(state)

    assert result.error is None
    assert result.validation_errors == [], (
        "les deux erreurs correspondent à des security_requirements "
        "explicites -- elles doivent être filtrées, pas déclencher la boucle"
    )
    report = result.reports[-1]
    assert any("supprimée" in w for w in report.warnings), (
        "la suppression doit rester visible dans l'audit, pas silencieuse"
    )


def test_run_agent3_keeps_error_unrelated_to_any_explicit_requirement():
    spec = NormalizedSpec(
        raw_user_request="x", namespace="web", architecture_type="single",
        components=[ServiceComponent(
            component_name="api", workload_type="Deployment", image="x:1.0",
            security_requirements=["Hardening par défaut standard"],
        )],
    )
    state = PipelineState(
        user_request="x", spec=spec,
        manifest_v1_yaml=(
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: api\n  namespace: web\n"
            "spec:\n  template:\n    spec:\n      containers:\n"
            "      - name: api\n        securityContext: {privileged: true}\n"
        ),
    )

    def fake_call_llm(system_prompt, user_prompt, agent_name="", **kwargs):
        manifest = user_prompt.split("Manifeste à valider :\n", 1)[1].split("\n\nNormalizedSpec")[0]
        return json.dumps({
            "manifest_yaml": manifest,
            "checks_passed": [], "checks_failed_and_fixed": [],
            "validation_errors": [{
                "rule": "privileged-container", "message": "privileged: true non justifié",
                "resource": "Deployment/api",
            }],
            "fields_addressed": [], "fields_left_open": [], "warnings": [],
        })

    with patch("agents.agent3_validation.call_llm", side_effect=fake_call_llm):
        result = run_agent3(state)

    assert result.error is None
    assert len(result.validation_errors) == 1, "un vrai gap, non demandé, doit rester détecté"
    assert result.validation_errors[0].rule == "privileged-container"
