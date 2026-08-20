"""
orchestrator.py — l'Orchestrateur explicite de l'Architecture D.

Différence structurelle UNIQUE avec Architecture C : le noeud
"agent4_energie" (un seul agent LLM) est remplacé par "agent4_debate"
(sous-système de débat multi-agents Consolidation/Sizing/Autoscaling +
Juge, voir agents/agent4_debate.py). Le CÂBLAGE du graphe (quels noeuds,
dans quel ordre, quels cycles bornés) est VOLONTAIREMENT identique à
Architecture C : le débat multi-agents est entièrement interne à ce seul
noeud (comme la boucle d'auto-vérification de l'Agent 1), il n'introduit
AUCUNE arête supplémentaire dans le StateGraph. C'est ce qui permet une
comparaison de benchmark isolant strictement la contribution du patron
Debate, sans changer quoi que ce soit d'autre par rapport à C (E1-E6
inchangées, seul E7 — exécution parallèle — passe de Non à Oui).

Avant ce fichier, "l'orchestrateur" n'existait qu'IMPLICITEMENT : le
`StateGraph` de LangGraph et ses fonctions de routage vivaient directement
dans `graph.py`, sans composant nommable auquel se référer. Ce module rend
la chose explicite : une classe `Orchestrator`, seule responsable des
décisions de routage (quand boucler, quand avancer) et de leur
traçabilité — ce qui correspond au rôle dessiné dans le schéma du cahier
des charges :

                 ┌────────────── Orchestrator ──────────────┐
                 ▼                                          ▼
    [Analyst] ──> [Generator] <───(Blackboard Memory)───> [Validator] ──> [Energy Optimizer]

`graph.py` reste responsable du CÂBLAGE (quels noeuds, dans quel ordre) ;
`Orchestrator` est responsable des DÉCISIONS (routage conditionnel) et de
leur JOURNALISATION explicite -- avant, une décision de boucler ou
d'avancer ne laissait aucune trace autre que l'appel suivant observé dans
les logs d'agents. Maintenant, chaque décision de routage s'imprime
elle-même avec sa justification.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from schemas import PipelineState
from config import settings
from utils.logging_utils import log_step, log_error


class Orchestrator:
    """
    État manager central de l'Architecture D (câblage hérité tel quel
    d'Architecture C, seul le noeud "agent4_debate" change de nature).

    Responsabilités :
      1. Construire le graphe (noeuds + arêtes, y compris les deux cycles
         bornés) -- `build()`.
      2. Décider, à deux points précis du pipeline, s'il faut boucler ou
         avancer -- `route_after_generation_validation()` et
         `route_after_final_verification()`. Ce sont EXACTEMENT les
         fonctions utilisées comme fonctions de routage LangGraph
         (`add_conditional_edges`), pas une couche supplémentaire au-dessus.
      3. Journaliser explicitement chaque décision non triviale, pour que
         "pourquoi ça a rebouclé" soit visible sans avoir à lire le code.

    Ne fait PAS le travail des agents eux-mêmes (aucune logique métier
    ici) -- uniquement le contrôle de flux entre eux.
    """

    def __init__(self):
        self._graph = None  # construit paresseusement, voir build()

    # -- Décisions de routage ------------------------------------------

    def route_after_generation_validation(self, state: PipelineState) -> str:
        """
        Premier cycle borné : Generator <-> Validator (blackboard =
        `current_yaml` / `validation_errors` / `iteration_count`).

        Boucle vers "fix" si ET SEULEMENT SI :
          - pas d'erreur bloquante en amont
          - Agent 3 a détecté des `validation_errors` (schéma/sécurité)
          - `iteration_count` n'a pas atteint `MAX_ITERATIONS`
        """
        if state.error:
            return "forward"

        if state.validation_errors and state.iteration_count < settings.MAX_ITERATIONS:
            log_step(
                "Orchestrateur",
                f"↻ Renvoi vers le Générateur : {len(state.validation_errors)} "
                f"erreur(s) de validation détectée(s) "
                f"({[e.rule for e in state.validation_errors]}), "
                f"itération {state.iteration_count + 1}/{settings.MAX_ITERATIONS}.",
            )
            return "fix"

        if state.validation_errors:
            log_step(
                "Orchestrateur",
                f"⏭ Borne MAX_ITERATIONS ({settings.MAX_ITERATIONS}) atteinte avec "
                f"{len(state.validation_errors)} erreur(s) résiduelle(s) — passage "
                f"forcé à l'étape suivante, erreurs conservées pour l'audit.",
            )
        return "forward"

    def route_after_final_verification(self, state: PipelineState) -> str:
        """
        Deuxième cycle borné : Agent 5 <-> repair (blackboard =
        `global_constraints` du NormalizedSpec, `repair_requests` /
        `repair_attempt` du PipelineState).

        Boucle vers "repair" si ET SEULEMENT SI :
          - pas d'erreur bloquante en amont
          - Agent 5 a produit au moins une `repair_requests` concrète
          - `repair_attempt` n'a pas atteint `MAX_REPAIR_ATTEMPTS`
        """
        if state.error:
            return "end"

        if state.repair_requests and state.repair_attempt < settings.MAX_REPAIR_ATTEMPTS:
            log_step(
                "Orchestrateur",
                f"↻ Renvoi vers la réparation ciblée : {len(state.repair_requests)} "
                f"gap(s) détecté(s) par Agent 5, tentative "
                f"{state.repair_attempt + 1}/{settings.MAX_REPAIR_ATTEMPTS}.",
            )
            return "repair"

        if state.repair_requests:
            log_step(
                "Orchestrateur",
                f"⏭ Borne MAX_REPAIR_ATTEMPTS ({settings.MAX_REPAIR_ATTEMPTS}) atteinte "
                f"avec {len(state.repair_requests)} gap(s) résiduel(s) — fin du "
                f"pipeline, gaps conservés pour l'audit.",
            )
        return "end"

    # -- Construction du graphe ------------------------------------------

    def build(self):
        """Construit (une seule fois, mise en cache) et retourne le graphe
        LangGraph compilé, avec les deux cycles bornés câblés sur les
        décisions ci-dessus."""
        if self._graph is not None:
            return self._graph

        # Imports différés : évite un import circulaire (les modules
        # agents/* importent PipelineState de schemas.py, pas
        # l'orchestrateur -- mais orchestrator.py doit pouvoir être importé
        # AVANT que tous les agents existent, au chargement du module).
        from agents.agent1_analyse import run_agent1
        from agents.agent2_template import run_agent2, run_generator_fix
        from agents.agent3_validation import run_agent3
        from agents.agent4_debate import run_agent4_debate
        from agents.agent5_verification import run_agent5
        from agents.agent_repair import run_repair

        def guard(node_fn, node_name: str):
            def wrapped(state: PipelineState) -> PipelineState:
                if state.error:
                    return state
                try:
                    return node_fn(state)
                except Exception as e:  # noqa: BLE001
                    state.error = f"{node_name} : exception non gérée : {e}"
                    log_error(node_name, str(e))
                    return state
            return wrapped

        graph = StateGraph(PipelineState)

        graph.add_node("agent1_analyse", guard(run_agent1, "Agent 1 - Analyse"))
        graph.add_node("agent2_template", guard(run_agent2, "Agent 2 - Template"))
        graph.add_node("agent3_validation", guard(run_agent3, "Agent 3 - Validation"))
        graph.add_node("agent2_generator_fix", guard(run_generator_fix, "Agent 2 - Correction sur retour"))
        graph.add_node("agent4_debate", guard(run_agent4_debate, "Agent 4 - Débat multi-agents (Énergie)"))
        graph.add_node("agent5_verification", guard(run_agent5, "Agent 5 - Vérification finale"))
        graph.add_node("repair", guard(run_repair, "Réparation ciblée"))

        graph.set_entry_point("agent1_analyse")

        graph.add_edge("agent1_analyse", "agent2_template")
        graph.add_edge("agent2_template", "agent3_validation")

        graph.add_conditional_edges(
            "agent3_validation",
            self.route_after_generation_validation,
            {"fix": "agent2_generator_fix", "forward": "agent4_debate"},
        )
        graph.add_edge("agent2_generator_fix", "agent3_validation")

        graph.add_edge("agent4_debate", "agent5_verification")

        graph.add_conditional_edges(
            "agent5_verification",
            self.route_after_final_verification,
            {"repair": "repair", "end": END},
        )
        graph.add_edge("repair", "agent5_verification")

        self._graph = graph.compile()
        return self._graph

    # -- Exécution --------------------------------------------------------

    def run(self, user_request: str) -> dict:
        """Point d'entrée pratique : construit le graphe si besoin et
        exécute un run complet pour une demande donnée."""
        pipeline = self.build()
        return pipeline.invoke(PipelineState(user_request=user_request))
