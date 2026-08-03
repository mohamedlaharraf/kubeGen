"""
tests/test_agent1_schema_recovery.py

Bug réel de production (run réel contre l'API Gemini, pas un mock) : le LLM
a créé un `components[1]` invalide pour représenter un opérateur PostgreSQL
(`workload_type: "PostgresCluster"`, `image: null`) au lieu d'utiliser
`unmapped_requirements`, et `cert_manager_issuer_kind` est arrivé à `null`.
Avant ce correctif, `NormalizedSpec.model_validate()` levait une
`ValidationError` non rattrapée : TOUT le pipeline s'arrêtait, y compris
pour la partie de la demande parfaitement valide.

Ces tests verrouillent la cascade de récupération :
1. Coercion tolérante des champs enum "administratifs" (schemas.py).
2. Réparation ciblée via un second appel LLM sur les erreurs Pydantic exactes.
3. Filet de sécurité final : retrait déterministe des composants
   fautifs (sans LLM) si la réparation échoue encore.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import agents.agent1_analyse as a1  # noqa: E402
from schemas import PipelineState  # noqa: E402


BROKEN_SPEC = {
    "architecture_type": "single",
    "namespace": "data",
    "components": [
        {"component_name": "analytics-api", "workload_type": "Deployment",
         "image": "myregistry/analytics:2.0", "replicas": 1, "labels": {},
         "ports": [{"container_port": 8080}], "env_vars": [], "volumes": [],
         "sidecars": [], "depends_on": [], "energy_goals": [], "resource_hints": None,
         "traffic_windows": [], "constraints": [], "security_requirements": [],
         "observability_requirements": [],
         "ingress": {"enabled": True, "cert_manager_issuer_kind": None}},
        # Composant invalide : workload_type hors énumération + image manquante,
        # reproduction fidèle du bug réel (le LLM a tenté de représenter un
        # opérateur PostgreSQL comme un "component" classique).
        {"component_name": "postgres-cluster", "workload_type": "PostgresCluster", "image": None,
         "replicas": 3, "labels": {}, "ports": [], "env_vars": [], "volumes": [],
         "sidecars": [], "depends_on": [], "energy_goals": [], "resource_hints": None,
         "traffic_windows": [], "constraints": [], "security_requirements": [],
         "observability_requirements": []},
    ],
    "raw_user_request": "analytics-api + opérateur PostgreSQL...",
    "ambiguities": [], "unmapped_requirements": [],
    "coverage": {"requirements_detected": [], "requirements_mapped": [],
                 "requirements_unmapped": [], "repair_attempts": 0, "self_check_passed": True},
}

REPAIRED_SPEC = dict(BROKEN_SPEC)
REPAIRED_SPEC["components"] = [BROKEN_SPEC["components"][0]]
REPAIRED_SPEC["unmapped_requirements"] = [
    {"text": "opérateur PostgreSQL 3 instances réplication synchrone",
     "suggested_kind": "PostgresCluster"}
]


def test_cert_manager_issuer_kind_null_does_not_crash_extraction(monkeypatch):
    """Le champ enum administratif à l'origine directe du crash observé
    (cert_manager_issuer_kind=None) ne doit plus jamais lever d'erreur,
    testé ici via le chemin complet de l'Agent 1."""
    valid_only_spec = dict(BROKEN_SPEC)
    valid_only_spec["components"] = [BROKEN_SPEC["components"][0]]

    def fake_llm(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "gaps" in system_prompt.lower() or "AUTO-VÉRIFICATION" in system_prompt:
            return json.dumps({"gaps": []})
        return json.dumps(valid_only_spec)

    monkeypatch.setattr(a1, "call_llm", fake_llm)
    state = a1.run_agent1(PipelineState(user_request="test"))

    assert state.error is None
    assert state.spec is not None
    assert state.spec.components[0].ingress.cert_manager_issuer_kind == "ClusterIssuer"


def test_invalid_component_recovered_via_schema_repair(monkeypatch):
    """Reproduction du bug réel : extraction produit un composant invalide,
    la réparation de schéma (2e appel LLM, ciblé sur les erreurs Pydantic
    exactes) corrige en le déplaçant vers unmapped_requirements."""
    def fake_llm(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "gaps" in system_prompt.lower() or "AUTO-VÉRIFICATION" in system_prompt:
            return json.dumps({"gaps": []})
        if "RÉPARATION DE SCHÉMA" in system_prompt:
            return json.dumps(REPAIRED_SPEC)
        return json.dumps(BROKEN_SPEC)

    monkeypatch.setattr(a1, "call_llm", fake_llm)
    state = a1.run_agent1(PipelineState(user_request="test"))

    assert state.error is None
    assert state.spec is not None
    assert [c.component_name for c in state.spec.components] == ["analytics-api"]
    assert len(state.spec.unmapped_requirements) == 1
    assert state.spec.unmapped_requirements[0].suggested_kind == "PostgresCluster"


def test_invalid_component_dropped_when_llm_repair_never_succeeds(monkeypatch):
    """Filet de sécurité final : si le LLM de réparation s'entête et
    renvoie systématiquement le JSON cassé, le composant fautif est retiré
    de façon DÉTERMINISTE (sans nouvel appel LLM) plutôt que de faire
    planter tout le pipeline. La partie valide (analytics-api) survit."""
    def fake_llm_stubborn(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "gaps" in system_prompt.lower() or "AUTO-VÉRIFICATION" in system_prompt:
            return json.dumps({"gaps": []})
        return json.dumps(BROKEN_SPEC)  # ne corrige jamais, même en réparation

    monkeypatch.setattr(a1, "call_llm", fake_llm_stubborn)
    state = a1.run_agent1(PipelineState(user_request="test"))

    assert state.error is None
    assert state.spec is not None
    assert [c.component_name for c in state.spec.components] == ["analytics-api"]
    report = state.reports[0]
    assert any("postgres-cluster" in w for w in report.warnings)


def test_root_level_validation_error_fails_cleanly_not_silently(monkeypatch):
    """Si l'erreur Pydantic concerne un champ RACINE (pas un components[i]
    précis), il n'y a pas de "partie fautive" isolable en sécurité -- le
    retrait déterministe ne doit RIEN retirer au hasard, et le pipeline
    doit échouer proprement (state.error) plutôt que de deviner."""
    root_broken_spec = dict(BROKEN_SPEC)
    root_broken_spec["components"] = [BROKEN_SPEC["components"][0]]
    # namespace doit être une string ; un type radicalement incompatible
    # (dict) déclenche une erreur de validation au niveau racine, non
    # rattachable à un components[i].
    root_broken_spec["namespace"] = {"not": "a string"}

    def fake_llm_never_fixes_root(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "gaps" in system_prompt.lower() or "AUTO-VÉRIFICATION" in system_prompt:
            return json.dumps({"gaps": []})
        return json.dumps(root_broken_spec)  # ne corrige jamais

    monkeypatch.setattr(a1, "call_llm", fake_llm_never_fixes_root)
    state = a1.run_agent1(PipelineState(user_request="test"))

    assert state.error is not None
    assert "Agent 1" in state.error
