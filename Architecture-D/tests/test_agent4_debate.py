"""
tests/test_agent4_debate.py — tests dédiés au sous-système de débat
multi-agents (Architecture D), qui remplace l'Agent 4 unique
d'Architecture C.

Couvre les 3 critères d'acceptation du cahier des charges :
  1. Fan-out réellement parallèle (threads, pas une boucle séquentielle
     déguisée) pour les 3 agents-stratégies.
  2. Échange effectif de critiques entre stratégies (désaccord détecté et
     tranché, pas un simple satisfecit systématique).
  3. Le Juge produit un raisonnement (`reasoning`) ET un YAML consolidé.

Complète (sans les dupliquer) les tests d'intégration bout-en-bout de
tests/test_pipeline.py, qui utilisent un mock "passthrough"/"HPA" simple
sans exercer le désaccord entre stratégies.
"""

import json
import threading
import time

import agents.agent4_debate as a4d
from agents.agent4_debate import run_agent4_debate
from config import settings
from schemas import NormalizedSpec, PipelineState, ServiceComponent

BASE_YAML = (
    "apiVersion: apps/v1\n"
    "kind: Deployment\n"
    "metadata:\n"
    "  name: checkout-api\n"
    "  namespace: default\n"
    "spec:\n"
    "  replicas: 3\n"
    "  template:\n"
    "    spec:\n"
    "      containers:\n"
    "        - name: checkout-api\n"
    "          image: checkout-api:1.0\n"
)


def _make_state(component_kwargs=None, manifest_yaml=BASE_YAML) -> PipelineState:
    component = ServiceComponent(
        component_name="checkout-api",
        workload_type="Deployment",
        image="checkout-api:1.0",
        energy_goals=["scaler automatiquement aux heures de pointe"],
        **(component_kwargs or {}),
    )
    spec = NormalizedSpec(
        components=[component],
        application_context="API de paiement critique",
        raw_user_request="Déploie checkout-api avec scaling automatique",
    )
    state = PipelineState(user_request="test", spec=spec, manifest_v2_yaml=manifest_yaml)
    return state


def _proposal_response(strategy: str, chunk: str) -> str:
    return json.dumps({
        "manifest_yaml": chunk + f"\n# marqueur-{strategy}",
        "rationale": f"rationale-{strategy}",
        "estimated_energy_savings_pct": 15,
        "performance_risk": "low",
        "actions": [f"action-{strategy}"],
        "warnings": [],
    })


def _critique_response(critiques, revised_manifest=None):
    payload = {"critiques": critiques}
    if revised_manifest is not None:
        payload["revised_proposal"] = {
            "manifest_yaml": revised_manifest,
            "rationale": "révisé suite critique",
            "estimated_energy_savings_pct": 12,
            "performance_risk": "low",
            "actions": [], "warnings": [],
        }
    else:
        payload["revised_proposal"] = None
    return json.dumps(payload)


def _judge_response(chunk: str, scores=None, reasoning="Fusion arbitrée par le Juge."):
    return json.dumps({
        "manifest_yaml": chunk + "\n# fusion-juge",
        "reasoning": reasoning,
        "strategy_scores": scores or {"consolidation": 7, "sizing": 8, "autoscaling": 6},
        "chosen_elements": {"resources": "sizing"},
        "fields_addressed": ["resources"],
        "fields_left_open": [],
        "warnings": [],
    })


# ---------------------------------------------------------------------
# 1. Fan-out réellement parallèle
# ---------------------------------------------------------------------

def test_strategy_proposals_run_on_three_distinct_threads(monkeypatch):
    """Les 3 propositions initiales doivent être exécutées sur des threads
    distincts du thread principal — pas une simple boucle for séquentielle
    qui appellerait call_llm 3 fois depuis le même thread."""
    seen_thread_ids = []
    lock = threading.Lock()

    def fake_call_llm(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        with lock:
            seen_thread_ids.append(threading.get_ident())
        time.sleep(0.05)  # force un chevauchement temporel mesurable
        if agent_name == "Agent4-Debate-Judge":
            return _judge_response(BASE_YAML)
        if agent_name.endswith("-Critique"):
            return _critique_response([])
        strategy = agent_name.rsplit("-", 1)[-1]
        return _proposal_response(strategy, BASE_YAML)

    monkeypatch.setattr(a4d, "call_llm", fake_call_llm)
    monkeypatch.setattr(settings, "DEBATE_MAX_TURNS", 1)

    state = _make_state()
    t0 = time.monotonic()
    result = run_agent4_debate(state)
    elapsed = time.monotonic() - t0

    assert result.error is None
    # 3 appels de proposition + 3 de critique = 6 appels à 0.05s ; en
    # séquentiel cela prendrait >= 0.30s, en parallèle (2 fan-out de 3)
    # cela prend environ 2*0.05s = 0.10s.
    assert elapsed < 0.25, f"Trop lent ({elapsed:.3f}s) : le fan-out ne semble pas parallèle"

    proposal_thread_ids = set(seen_thread_ids[:3])
    assert len(proposal_thread_ids) >= 2, "Les 3 stratégies n'ont pas tourné sur des threads distincts"
    assert threading.get_ident() not in proposal_thread_ids, (
        "Les appels-stratégies ont été exécutés sur le thread principal : pas de parallélisme réel."
    )


def test_fan_out_calls_all_three_strategies(monkeypatch):
    called_agent_names = []

    def fake_call_llm(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        called_agent_names.append(agent_name)
        if agent_name == "Agent4-Debate-Judge":
            return _judge_response(BASE_YAML)
        if agent_name.endswith("-Critique"):
            return _critique_response([])
        strategy = agent_name.rsplit("-", 1)[-1]
        return _proposal_response(strategy, BASE_YAML)

    monkeypatch.setattr(a4d, "call_llm", fake_call_llm)
    monkeypatch.setattr(settings, "DEBATE_MAX_TURNS", 1)

    run_agent4_debate(_make_state())

    proposal_calls = [
        n for n in called_agent_names
        if n.startswith("Agent4-Debate-Strategy-") and not n.endswith("-Critique")
    ]
    assert sorted(n.rsplit("-", 1)[-1] for n in proposal_calls) == ["autoscaling", "consolidation", "sizing"]
    assert called_agent_names.count("Agent4-Debate-Judge") == 1


# ---------------------------------------------------------------------
# 2. Borne du nombre de tours de débat
# ---------------------------------------------------------------------

def test_debate_turns_bounded_by_config(monkeypatch):
    critique_call_count = {"n": 0}

    def fake_call_llm(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if agent_name == "Agent4-Debate-Judge":
            return _judge_response(BASE_YAML)
        if agent_name.endswith("-Critique"):
            critique_call_count["n"] += 1
            return _critique_response([])
        strategy = agent_name.rsplit("-", 1)[-1]
        return _proposal_response(strategy, BASE_YAML)

    monkeypatch.setattr(a4d, "call_llm", fake_call_llm)
    monkeypatch.setattr(settings, "DEBATE_MAX_TURNS", 2)

    state = run_agent4_debate(_make_state())

    # 2 tours * 3 stratégies = 6 appels de critique.
    assert critique_call_count["n"] == 6
    assert len(state.debate_transcripts["checkout-api"]) == 2


def test_debate_turns_hard_capped_at_two_even_if_config_higher(monkeypatch):
    """Le cahier des charges impose '1 à 2 tours max' : même si
    DEBATE_MAX_TURNS est mal configuré au-delà, le code doit plafonner à 2."""
    critique_call_count = {"n": 0}

    def fake_call_llm(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if agent_name == "Agent4-Debate-Judge":
            return _judge_response(BASE_YAML)
        if agent_name.endswith("-Critique"):
            critique_call_count["n"] += 1
            return _critique_response([])
        strategy = agent_name.rsplit("-", 1)[-1]
        return _proposal_response(strategy, BASE_YAML)

    monkeypatch.setattr(a4d, "call_llm", fake_call_llm)
    monkeypatch.setattr(settings, "DEBATE_MAX_TURNS", 5)

    state = run_agent4_debate(_make_state())

    assert critique_call_count["n"] == 6  # 2 tours plafonnés, pas 5*3=15
    assert len(state.debate_transcripts["checkout-api"]) == 2


# ---------------------------------------------------------------------
# 3. Échange réel de critiques + verdict du Juge
# ---------------------------------------------------------------------

def test_conflict_between_strategies_is_captured_and_judged(monkeypatch):
    """La Stratégie A (consolidation) retire un PodDisruptionBudget pour
    faciliter la compaction ; la Stratégie C (autoscaling) le juge
    dangereux combiné à un scale-down agressif -> conflit réel, agrees=False,
    tranché explicitement par le Juge."""

    def fake_call_llm(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if agent_name == "Agent4-Debate-Judge":
            return _judge_response(
                BASE_YAML,
                scores={"consolidation": 5, "sizing": 7, "autoscaling": 8},
                reasoning="PDB minAvailable=1 conservé : compatible consolidation ET scale-down sûr.",
            )
        if agent_name.endswith("-Critique"):
            strategy = agent_name.replace("Agent4-Debate-Strategy-", "").replace("-Critique", "")
            if strategy == "autoscaling":
                return _critique_response([
                    {"target_strategy": "consolidation",
                     "comment": "Retirer le PDB est risqué avec un scale-down agressif.",
                     "agrees": False},
                    {"target_strategy": "sizing", "comment": "Pas de conflit.", "agrees": True},
                ])
            return _critique_response([
                {"target_strategy": "sizing", "comment": "Pas de conflit.", "agrees": True},
                {"target_strategy": "autoscaling", "comment": "Pas de conflit.", "agrees": True},
            ])
        strategy = agent_name.rsplit("-", 1)[-1]
        return _proposal_response(strategy, BASE_YAML)

    monkeypatch.setattr(a4d, "call_llm", fake_call_llm)
    monkeypatch.setattr(settings, "DEBATE_MAX_TURNS", 1)

    state = run_agent4_debate(_make_state())

    transcript = state.debate_transcripts["checkout-api"]
    all_critiques = [c for r in transcript for c in r.critiques]
    disagreements = [c for c in all_critiques if not c.agrees]
    assert len(disagreements) == 1
    assert disagreements[0].from_strategy == "autoscaling"
    assert disagreements[0].target_strategy == "consolidation"

    verdict = state.judge_verdicts[0]
    assert verdict.reasoning  # le Juge a bien produit un raisonnement
    assert "pdb" in verdict.reasoning.lower()
    assert verdict.manifest_yaml  # ... et un YAML consolidé
    assert "checkout-api" in state.manifest_v3_yaml


def test_judge_report_recorded_in_pipeline_state(monkeypatch):
    def fake_call_llm(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if agent_name == "Agent4-Debate-Judge":
            return _judge_response(BASE_YAML)
        if agent_name.endswith("-Critique"):
            return _critique_response([])
        strategy = agent_name.rsplit("-", 1)[-1]
        return _proposal_response(strategy, BASE_YAML)

    monkeypatch.setattr(a4d, "call_llm", fake_call_llm)
    monkeypatch.setattr(settings, "DEBATE_MAX_TURNS", 1)

    state = run_agent4_debate(_make_state())

    assert len(state.reports) == 1
    report = state.reports[0]
    assert report.agent_name == "Agent 4 - Débat multi-agents (Énergie)"
    assert any("Débat conclu" in a for a in report.actions)
    assert "fusion-juge" in state.manifest_v3_yaml


# ---------------------------------------------------------------------
# 4. Cas d'erreur
# ---------------------------------------------------------------------

def test_missing_manifest_input_sets_error():
    state = PipelineState(user_request="test")  # pas de manifest_v2_yaml ni spec
    result = run_agent4_debate(state)
    assert result.error is not None
    assert "Agent 4" in result.error
