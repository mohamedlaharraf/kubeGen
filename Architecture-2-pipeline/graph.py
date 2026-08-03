"""
graph.py — assemblage du pipeline avec LangGraph.

Architecture strictement séquentielle, sans arête de retour :

    START -> agent1 -> agent2 -> agent3 -> agent4 -> agent5 -> END

Chaque noeud reçoit le PipelineState complet (pour la traçabilité) mais,
comme détaillé dans chaque agents/agentN_*.py, ne PUISE dans son prompt
LLM que les champs pertinents à son rôle ("contexte isolé par étape").

Si un agent pose `state.error`, le graphe s'arrête immédiatement (on ne
continue jamais avec un état invalide) : c'est la seule "sortie
anticipée" tolérée, elle ne revient jamais en arrière, elle stoppe.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END
from tenacity import RetryError

from schemas import PipelineState
from agents.agent1_analyse import run_agent1
from agents.agent2_template import run_agent2
from agents.agent3_validation import run_agent3
from agents.agent4_energie import run_agent4
from agents.agent5_verification import run_agent5
from utils.logging_utils import log_error


def _root_cause(e: Exception) -> Exception:
    """
    `call_llm` est décoré `@retry(...)` (tenacity) : après 3 tentatives
    infructueuses, tenacity lève un `RetryError` dont le message
    (`str(e)`) ne contient QUE le nom de la classe de l'exception
    d'origine (ex: "RetryError[<Future ... raised ClientError>]"),
    jamais son message réel (code HTTP, raison exacte renvoyée par
    l'API Google...). Ça rend le diagnostic impossible pour
    l'utilisateur. On déballe donc ici l'exception réelle de la
    dernière tentative pour l'afficher à la place.
    """
    if isinstance(e, RetryError):
        try:
            inner = e.last_attempt.exception()
            if inner is not None:
                return inner
        except Exception:
            pass
    return e


def _guard(node_fn, node_name: str):
    """Enveloppe un agent pour interrompre proprement le pipeline strict
    en cas d'erreur bloquante, sans jamais revenir en arrière."""

    def wrapped(state: PipelineState) -> PipelineState:
        if state.error:
            return state  # déjà en erreur : on ne fait plus rien
        try:
            return node_fn(state)
        except Exception as e:  # noqa: BLE001
            root = _root_cause(e)
            detail = f"{type(root).__name__}: {root}"
            state.error = f"{node_name} : exception non gérée : {detail}"
            log_error(node_name, detail)
            return state

    return wrapped


def build_pipeline():
    graph = StateGraph(PipelineState)

    graph.add_node("agent1_analyse", _guard(run_agent1, "Agent 1 - Analyse"))
    graph.add_node("agent2_template", _guard(run_agent2, "Agent 2 - Template"))
    graph.add_node("agent3_validation", _guard(run_agent3, "Agent 3 - Validation"))
    graph.add_node("agent4_energie", _guard(run_agent4, "Agent 4 - Énergie"))
    graph.add_node("agent5_verification", _guard(run_agent5, "Agent 5 - Vérification finale"))

    graph.set_entry_point("agent1_analyse")

    # Chaîne stricte : chaque arête est unique et va vers l'avant uniquement.
    graph.add_edge("agent1_analyse", "agent2_template")
    graph.add_edge("agent2_template", "agent3_validation")
    graph.add_edge("agent3_validation", "agent4_energie")
    graph.add_edge("agent4_energie", "agent5_verification")
    graph.add_edge("agent5_verification", END)

    return graph.compile()
