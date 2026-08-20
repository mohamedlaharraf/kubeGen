"""
tests/test_global_constraints_extraction.py — teste le filet de sécurité
ajouté après le bug PCI-DSS/PostgresCluster observé en production
(l'appel dédié à l'extraction des global_constraints n'avait pas été
suivi par le LLM). Deux niveaux :

1. Unités pures (_keyword_hits, _constraints_seem_to_cover,
   _merge_global_constraints) -- rapides, sans mock LLM.
2. Intégration (run_agent1 complet) -- vérifie que le mécanisme de
   rattrapage se déclenche VRAIMENT quand la première extraction dédiée
   revient vide malgré des indices lexicaux présents, et que ça reste
   silencieux (aucun rattrapage inutile) quand ce n'est pas le cas.
"""
import json
from unittest.mock import patch

import pytest

from config import settings
from agents.agent1_analyse import (
    _keyword_hits,
    _constraints_seem_to_cover,
    _merge_global_constraints,
    run_agent1,
)
from schemas import PipelineState


@pytest.fixture(autouse=True)
def _fake_api_key():
    original = settings.GOOGLE_API_KEY
    settings.GOOGLE_API_KEY = "fake-key-for-testing"
    yield
    settings.GOOGLE_API_KEY = original


# --- unités pures ------------------------------------------------------

def test_keyword_hits_detects_known_compliance_terms():
    text = "L'application doit être conforme PCI-DSS avec chiffrement au repos."
    hits = _keyword_hits(text)
    assert "pci-dss" in hits
    assert "chiffrement" in hits


def test_keyword_hits_empty_on_unrelated_text():
    assert _keyword_hits("Déploie une API simple sur le port 8080.") == []


def test_constraints_seem_to_cover_true_when_no_hits():
    assert _constraints_seem_to_cover([], []) is True


def test_constraints_seem_to_cover_false_when_hits_but_no_constraints():
    assert _constraints_seem_to_cover(["chiffrement"], []) is False


def test_constraints_seem_to_cover_true_when_keyword_echoed():
    constraints = [{"text": "Chiffrement au repos obligatoire", "scope": "all_volumes"}]
    assert _constraints_seem_to_cover(["chiffrement"], constraints) is True


def test_constraints_seem_to_cover_false_when_constraints_dont_mention_hit():
    """Le cas exact du bug observé : des contraintes existent, mais
    aucune ne correspond au signal détecté -- ne doit PAS être compté
    comme couvert juste parce que la liste n'est pas vide."""
    constraints = [{"text": "Labels obligatoires sur tous les pods", "scope": "all_components"}]
    assert _constraints_seem_to_cover(["chiffrement"], constraints) is False


def test_merge_global_constraints_dedupes_by_text():
    a = [{"text": "Chiffrement au repos", "scope": "all_volumes"}]
    b = [{"text": "chiffrement au repos", "scope": "all_volumes"}, {"text": "Autre", "scope": "specific"}]
    merged = _merge_global_constraints(a, b)
    assert len(merged) == 2  # dédupliqué malgré la casse différente
    assert merged[0]["text"] == "Chiffrement au repos"  # premier arrivé conservé


# --- intégration : run_agent1 complet -----------------------------------

def _mock_for(extraction_constraints, retry_constraints=None):
    call_counts: dict[str, int] = {}

    def fake_call_llm(system_prompt, user_prompt, agent_name="", **kwargs):
        call_counts[agent_name] = call_counts.get(agent_name, 0) + 1

        if agent_name == "Agent 1 - Analyse (extraction)":
            return json.dumps({
                "raw_user_request": "x", "namespace": "data", "architecture_type": "single",
                "components": [{"component_name": "analytics-api", "workload_type": "Deployment",
                                 "image": "x:1.0", "replicas": 1}],
                "global_constraints": [], "unmapped_requirements": [], "ambiguities": [],
            })
        if agent_name == "Agent 1 - Analyse (self-check)":
            return json.dumps({"gaps": []})
        if agent_name == "Agent 1 - Analyse (contraintes globales)":
            n = call_counts[agent_name]
            if n == 1:
                return json.dumps({"global_constraints": extraction_constraints})
            return json.dumps({"global_constraints": retry_constraints or []})
        raise AssertionError(f"non mocké dans ce test : {agent_name!r}")

    return fake_call_llm, call_counts


def test_run_agent1_no_retry_when_dedicated_extraction_succeeds():
    """Cas nominal : l'appel dédié trouve la contrainte du premier coup
    -- aucun rattrapage nécessaire, un seul appel."""
    fake_call_llm, call_counts = _mock_for(
        extraction_constraints=[{
            "text": "Chiffrement au repos obligatoire pour tous les volumes",
            "scope": "all_volumes", "category": "compliance",
        }]
    )
    with patch("agents.agent1_analyse.call_llm", side_effect=fake_call_llm):
        state = run_agent1(PipelineState(
            user_request="API avec chiffrement au repos pour tous les volumes, conforme PCI-DSS."
        ))

    assert state.error is None
    assert len(state.spec.global_constraints) == 1
    assert call_counts["Agent 1 - Analyse (contraintes globales)"] == 1  # pas de rattrapage


def test_run_agent1_retries_and_recovers_when_first_extraction_misses():
    """Le cas exact du bug : la demande contient des indices clairs de
    contrainte transversale, mais l'appel dédié revient vide au premier
    coup -- le rattrapage doit se déclencher ET aboutir si la 2e
    tentative trouve la contrainte."""
    fake_call_llm, call_counts = _mock_for(
        extraction_constraints=[],  # raté au premier coup
        retry_constraints=[{
            "text": "Chiffrement au repos obligatoire pour tous les volumes",
            "scope": "all_volumes", "category": "compliance",
        }],
    )
    with patch("agents.agent1_analyse.call_llm", side_effect=fake_call_llm):
        state = run_agent1(PipelineState(
            user_request="API avec chiffrement au repos pour tous les volumes, conforme PCI-DSS."
        ))

    assert state.error is None
    assert call_counts["Agent 1 - Analyse (contraintes globales)"] == 2  # rattrapage déclenché
    assert len(state.spec.global_constraints) == 1
    assert "hiffrement" in state.spec.global_constraints[0].text
    # Aucun signalement d'échec puisque le rattrapage a réussi.
    assert not any("EXTRACTION POTENTIELLEMENT MANQUÉE" in item
                   for item in state.spec.coverage.requirements_unmapped)


def test_run_agent1_flags_loudly_when_retry_also_fails():
    """Pire cas : même le rattrapage échoue -- le pipeline ne doit PAS
    planter, mais doit rendre l'échec visible dans coverage.requirements_unmapped
    plutôt que de le faire disparaître silencieusement."""
    fake_call_llm, call_counts = _mock_for(
        extraction_constraints=[],
        retry_constraints=[],  # échoue aussi
    )
    with patch("agents.agent1_analyse.call_llm", side_effect=fake_call_llm):
        state = run_agent1(PipelineState(
            user_request="API avec chiffrement au repos pour tous les volumes, conforme PCI-DSS."
        ))

    assert state.error is None, "un échec d'extraction ne doit jamais faire planter le pipeline"
    assert call_counts["Agent 1 - Analyse (contraintes globales)"] == 2
    assert state.spec.global_constraints == []
    assert any("EXTRACTION POTENTIELLEMENT MANQUÉE" in item
               for item in state.spec.coverage.requirements_unmapped)


def test_run_agent1_no_retry_when_no_keywords_present():
    """Pas d'indice lexical dans le texte -> pas de rattrapage déclenché,
    même si global_constraints est vide (cas parfaitement normal pour une
    demande sans contrainte transversale)."""
    fake_call_llm, call_counts = _mock_for(extraction_constraints=[])
    with patch("agents.agent1_analyse.call_llm", side_effect=fake_call_llm):
        state = run_agent1(PipelineState(user_request="Déploie une API simple sur le port 8080."))

    assert state.error is None
    assert call_counts["Agent 1 - Analyse (contraintes globales)"] == 1  # pas de 2e appel
    assert state.spec.global_constraints == []
