"""
tests/_debate_fakes.py — mocks partagés pour `agents.agent4_debate.call_llm`.

Architecture D remplace l'Agent 4 unique par 3 appels-stratégies +
1 à 2 tours de critique + 1 appel Juge, chacun avec son propre
`agent_name` distinctif (voir agents/agent4_debate.py) :

    Agent4-Debate-Strategy-consolidation
    Agent4-Debate-Strategy-sizing
    Agent4-Debate-Strategy-autoscaling
    Agent4-Debate-Strategy-consolidation-Critique
    Agent4-Debate-Strategy-sizing-Critique
    Agent4-Debate-Strategy-autoscaling-Critique
    Agent4-Debate-Judge

Deux dispatchers sont fournis :
  - `dispatch_agent4_debate_passthrough` : le manifeste traverse le débat
    inchangé (aucun conflit, aucune révision) — pour les tests qui portent
    sur un AUTRE mécanisme (boucle Generator<->Validator, boucle de
    réparation, CLI) et n'ont besoin que d'un passage propre par Agent 4.
  - `dispatch_agent4_debate_with_hpa` : la stratégie 'autoscaling' ajoute
    un bloc HorizontalPodAutoscaler (`<name>-hpa`) que le Juge retient tel
    quel — pour les tests qui, comme l'ancien mock `fake_call_llm_agent4`,
    vérifient la présence d'un HPA dans le manifeste final.
"""

from __future__ import annotations

import json
import re

CHUNK_RE = re.compile(
    r"Manifeste validé de ce composant :\n(.*?)\n\nContexte énergie", re.DOTALL
)
JUDGE_CHUNK_RE = re.compile(
    r"YAML validé d'origine de ce composant \(avant optimisation\) :\n(.*?)\n\n",
    re.DOTALL,
)
COMPONENT_NAME_RE = re.compile(r"'component_name':\s*'([^']+)'")


def _extract_component_name(user_prompt: str) -> str:
    m = COMPONENT_NAME_RE.search(user_prompt)
    return m.group(1) if m else "unknown-component"


def _is_debate_agent(agent_name: str) -> bool:
    return agent_name.startswith("Agent4-Debate-")


def dispatch_agent4_debate_passthrough(agent_name: str, user_prompt: str) -> str:
    """Manifeste inchangé à chaque étape : pas de conflit, aucune révision.
    Convient à tout test qui n'a besoin que d'un Agent 4 fonctionnel, sans
    porter sur son contenu."""
    if agent_name == "Agent4-Debate-Judge":
        chunk_match = JUDGE_CHUNK_RE.search(user_prompt)
        chunk = chunk_match.group(1) if chunk_match else ""
        return json.dumps({
            "manifest_yaml": chunk,
            "reasoning": "Aucun conflit relevé, propositions complémentaires fusionnées telles quelles.",
            "strategy_scores": {"consolidation": 7, "sizing": 7, "autoscaling": 7},
            "chosen_elements": {},
            "fields_addressed": [], "fields_left_open": [], "warnings": [],
        })
    if agent_name.endswith("-Critique"):
        return json.dumps({"critiques": [], "revised_proposal": None})
    # Proposition initiale d'une stratégie
    chunk_match = CHUNK_RE.search(user_prompt)
    chunk = chunk_match.group(1) if chunk_match else ""
    return json.dumps({
        "manifest_yaml": chunk,
        "rationale": "passthrough de test", "estimated_energy_savings_pct": None,
        "performance_risk": "low", "actions": [], "warnings": [],
    })


def dispatch_agent4_debate_with_hpa(agent_name: str, user_prompt: str) -> str:
    """Comme le passthrough, sauf que la stratégie 'autoscaling' ajoute un
    bloc HPA `<name>-hpa` que le Juge retient dans le manifeste final —
    reproduit le comportement de l'ancien mock `fake_call_llm_agent4`
    d'Architecture C pour les tests qui vérifient sa présence."""
    if agent_name == "Agent4-Debate-Judge":
        chunk_match = JUDGE_CHUNK_RE.search(user_prompt)
        chunk = chunk_match.group(1) if chunk_match else ""
        name = _extract_component_name(user_prompt)
        enriched = chunk + (
            f"---\n"
            f"apiVersion: autoscaling/v2\n"
            f"kind: HorizontalPodAutoscaler\n"
            f"metadata:\n"
            f"  name: {name}-hpa\n"
            f"spec:\n"
            f"  scaleTargetRef:\n"
            f"    apiVersion: apps/v1\n"
            f"    kind: Deployment\n"
            f"    name: {name}\n"
            f"  minReplicas: 2\n"
            f"  maxReplicas: 8\n"
        )
        return json.dumps({
            "manifest_yaml": enriched,
            "reasoning": "Stratégie autoscaling retenue : trafic variable justifie un HPA.",
            "strategy_scores": {"consolidation": 6, "sizing": 6, "autoscaling": 9},
            "chosen_elements": {"hpa": "autoscaling"},
            "fields_addressed": ["resources", "hpa"], "fields_left_open": [], "warnings": [],
        })
    if agent_name.endswith("-Critique"):
        return json.dumps({"critiques": [], "revised_proposal": None})
    chunk_match = CHUNK_RE.search(user_prompt)
    chunk = chunk_match.group(1) if chunk_match else ""
    return json.dumps({
        "manifest_yaml": chunk,
        "rationale": "passthrough de test", "estimated_energy_savings_pct": 10,
        "performance_risk": "low", "actions": [], "warnings": [],
    })
