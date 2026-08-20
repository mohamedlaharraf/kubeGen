"""
agents/agent4_debate.py — Architecture D : remplace l'Agent 4 unique
(agents/agent4_energie.py, Architecture C) par un sous-système de DÉBAT
MULTI-AGENTS pour l'étape d'optimisation énergétique.

    [Validated YAML] --> [Orchestrator] --+--> [Strategy A: Consolidation] --+
                                           +--> [Strategy B: Sizing]         +--> [Judge] --> [Final YAML]
                                           +--> [Strategy C: Autoscaling]  --+

Justification (cf. rapport d'avancement n°1, §2.6 et §5.4) : la
littérature sur l'ordonnancement énergétique documente des stratégies
concurrentes et parfois contradictoires (consolider vs. étaler la
charge) plutôt qu'une méthode consensuelle unique. Un agent unique
appliquant SA heuristique ne peut pas, par construction, explorer ce
désaccord ; le patron Debate le modélise explicitement.

DÉCOUPAGE PAR COMPOSANT (hérité tel quel de l'Architecture C — voir
`agents/agent4_energie.py::_split_by_component`, réutilisé ici sans
duplication) : chaque `ServiceComponent` a son propre débat, totalement
indépendant des autres — un désaccord entre stratégies sur le composant
"api" n'a aucune incidence sur le débat du composant "worker".

DÉROULEMENT DU DÉBAT, PAR COMPOSANT (toujours interne à CE noeud du
graphe — comme la boucle d'auto-vérification de l'Agent 1, ceci ne crée
AUCUNE arête supplémentaire dans le StateGraph, voir orchestrator.py) :

  1. FAN-OUT (parallèle, 3 threads) : chaque agent-stratégie produit une
     `StrategyProposal` indépendante, à partir du même YAML validé et des
     mêmes champs énergie que l'ancien Agent 4 — seul l'angle d'attaque
     change (voir prompts/strategy_*_system.txt).
  2. DÉBAT (1 à `DEBATE_MAX_TURNS` tours, plafonné à 2, toujours en
     fan-out parallèle) : chaque stratégie reçoit les deux autres
     propositions, produit une critique par pair (`agrees: False` sur un
     conflit réel, `True` sinon) et peut réviser SA proposition sur le
     point contesté.
  3. JUGE (1 appel séquentiel, après le débat) : fusionne les trois
     propositions finales en un manifeste unique, tranche explicitement
     chaque conflit relevé, note chaque stratégie.

Le transcript complet (tous les tours, toutes les critiques) est conservé
dans `PipelineState.debate_transcripts` pour l'audit — voir Agent 5.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from llm_client import call_llm, extract_json
from schemas import (
    AgentReport,
    DebateRound,
    JudgeVerdict,
    PipelineState,
    StrategyCritique,
    StrategyProposal,
)
from config import settings
from utils.logging_utils import log_step, log_warning
from utils.global_constraints import filter_constraints, constraints_block

# Réutilisation SANS DUPLICATION du découpage par composant introduit par
# l'Architecture C : le comportement (matching par nom/préfixe, kinds
# transverses conservés tels quels) doit rester identique entre C et D
# pour que la comparaison de benchmark porte uniquement sur l'étape
# d'optimisation elle-même, pas sur un détail de segmentation qui aurait
# divergé entre les deux implémentations.
from agents.agent4_energie import _split_by_component

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

STRATEGIES = ("consolidation", "sizing", "autoscaling")

_STRATEGY_SYSTEM = {
    name: (PROMPTS_DIR / f"strategy_{name}_system.txt").read_text(encoding="utf-8")
    for name in STRATEGIES
}
_CRITIQUE_INSTRUCTIONS = (PROMPTS_DIR / "strategy_critique_instructions.txt").read_text(encoding="utf-8")
_JUDGE_SYSTEM = (PROMPTS_DIR / "debate_judge_system.txt").read_text(encoding="utf-8")

# Plafond dur, indépendant de la valeur configurée (voir config.py) : au
# delà de 2 tours, le patron Debate documenté dans la littérature (cf.
# Group Chat) montre un risque de non-convergence sans gain observé, pour
# un coût en appels LLM qui continue de croître linéairement.
_HARD_MAX_TURNS = 2


def _component_energy_context(component) -> dict:
    return component.model_dump(
        include={
            "component_name", "workload_type", "replicas",
            "energy_goals", "resource_hints", "traffic_windows", "constraints",
        }
    )


def _base_prompt(component, yaml_chunk: str, global_constraints: list, application_context: str) -> str:
    prompt = (
        f"Manifeste validé de ce composant :\n{yaml_chunk}\n\n"
        f"Contexte énergie (ServiceComponent, champs pertinents) :\n"
        f"{_component_energy_context(component)}"
    )
    if application_context:
        prompt += (
            f"\n\nContexte global de l'application (résumé, PAS le texte "
            f"brut) : {application_context}\n"
            f"Utilise ce contexte pour calibrer tes décisions — ce n'est "
            f"pas un champ à recopier dans le YAML."
        )
    prompt += constraints_block(filter_constraints(component.component_name, global_constraints))
    return prompt


def _run_strategy_proposal(strategy: str, component, yaml_chunk: str,
                            global_constraints: list, application_context: str) -> StrategyProposal:
    prompt = _base_prompt(component, yaml_chunk, global_constraints, application_context)
    raw = call_llm(
        _STRATEGY_SYSTEM[strategy], prompt,
        agent_name=f"Agent4-Debate-Strategy-{strategy}",
    )
    result = extract_json(raw)
    return StrategyProposal(
        strategy=strategy,
        component_name=component.component_name,
        manifest_yaml=result.get("manifest_yaml", yaml_chunk),
        rationale=result.get("rationale", ""),
        estimated_energy_savings_pct=result.get("estimated_energy_savings_pct"),
        performance_risk=result.get("performance_risk", "medium"),
        actions=result.get("actions", []),
        warnings=result.get("warnings", []),
    )


def _run_fan_out_proposals(component, yaml_chunk: str, global_constraints: list,
                            application_context: str) -> dict[str, StrategyProposal]:
    """FAN-OUT : les 3 agents-stratégies proposent en parallèle (threads
    réels, pas une simple boucle séquentielle déguisée) — c'est le
    critère d'acceptation explicite du cahier des charges."""
    with ThreadPoolExecutor(max_workers=len(STRATEGIES)) as pool:
        futures = {
            strategy: pool.submit(
                _run_strategy_proposal, strategy, component, yaml_chunk,
                global_constraints, application_context,
            )
            for strategy in STRATEGIES
        }
        return {strategy: fut.result() for strategy, fut in futures.items()}


def _run_strategy_critique(strategy: str, component, chunk_for_context: str,
                            own_proposal: StrategyProposal,
                            peer_proposals: dict[str, StrategyProposal],
                            critiques_received: list[StrategyCritique],
                            global_constraints: list, application_context: str,
                            ) -> tuple[list[StrategyCritique], StrategyProposal]:
    peers_block = "\n\n".join(
        f"Proposition de la stratégie '{peer_name}' :\n"
        f"- rationale: {peer.rationale}\n"
        f"- performance_risk: {peer.performance_risk}\n"
        f"- manifest_yaml:\n{peer.manifest_yaml}"
        for peer_name, peer in peer_proposals.items()
        if peer_name != strategy
    )
    prompt = (
        f"TA proposition actuelle (stratégie '{strategy}') pour le "
        f"composant '{component.component_name}' :\n"
        f"- rationale: {own_proposal.rationale}\n"
        f"- manifest_yaml:\n{own_proposal.manifest_yaml}\n\n"
        f"Propositions des deux autres stratégies :\n{peers_block}\n\n"
        f"Contexte énergie de ce composant :\n{_component_energy_context(component)}"
    )
    if application_context:
        prompt += f"\n\nContexte global de l'application (résumé) : {application_context}"
    prompt += constraints_block(filter_constraints(component.component_name, global_constraints))

    if critiques_received:
        prompt += (
            "\n\nCritiques reçues sur TA proposition au tour précédent "
            "(à prendre en compte si tu révises) :\n" + "\n".join(
                f"- [{c.from_strategy} -> toi] agrees={c.agrees} : {c.comment}"
                for c in critiques_received
            )
        )

    system = _STRATEGY_SYSTEM[strategy] + "\n\n" + _CRITIQUE_INSTRUCTIONS
    raw = call_llm(system, prompt, agent_name=f"Agent4-Debate-Strategy-{strategy}-Critique")
    result = extract_json(raw)

    critiques = [
        StrategyCritique(
            from_strategy=strategy,
            target_strategy=c.get("target_strategy"),
            component_name=component.component_name,
            comment=c.get("comment", ""),
            agrees=c.get("agrees", True),
        )
        for c in result.get("critiques", [])
        if c.get("target_strategy") in STRATEGIES and c.get("target_strategy") != strategy
    ]

    revised = result.get("revised_proposal") or {}
    revised_proposal = StrategyProposal(
        strategy=strategy,
        component_name=component.component_name,
        manifest_yaml=revised.get("manifest_yaml", own_proposal.manifest_yaml),
        rationale=revised.get("rationale", own_proposal.rationale),
        estimated_energy_savings_pct=revised.get(
            "estimated_energy_savings_pct", own_proposal.estimated_energy_savings_pct
        ),
        performance_risk=revised.get("performance_risk", own_proposal.performance_risk),
        actions=revised.get("actions", own_proposal.actions),
        warnings=revised.get("warnings", own_proposal.warnings),
    )
    return critiques, revised_proposal


def _run_fan_out_critiques(component, chunk_for_context: str,
                            current_proposals: dict[str, StrategyProposal],
                            critiques_by_target: dict[str, list[StrategyCritique]],
                            global_constraints: list, application_context: str,
                            ) -> tuple[list[StrategyCritique], dict[str, StrategyProposal]]:
    """FAN-OUT du tour de critique : les 3 stratégies critiquent leurs
    pairs en parallèle (mêmes threads réels que pour les propositions)."""
    with ThreadPoolExecutor(max_workers=len(STRATEGIES)) as pool:
        futures = {
            strategy: pool.submit(
                _run_strategy_critique, strategy, component, chunk_for_context,
                current_proposals[strategy],
                {p: prop for p, prop in current_proposals.items() if p != strategy},
                critiques_by_target.get(strategy, []),
                global_constraints, application_context,
            )
            for strategy in STRATEGIES
        }
        results = {strategy: fut.result() for strategy, fut in futures.items()}

    all_critiques: list[StrategyCritique] = []
    revised_proposals: dict[str, StrategyProposal] = {}
    for strategy, (critiques, revised) in results.items():
        all_critiques.extend(critiques)
        revised_proposals[strategy] = revised
    return all_critiques, revised_proposals


def _run_judge(component, yaml_chunk: str, final_proposals: dict[str, StrategyProposal],
               transcript: list[DebateRound], global_constraints: list,
               application_context: str) -> JudgeVerdict:
    proposals_block = "\n\n".join(
        f"Proposition finale (post-débat) de la stratégie '{name}' :\n"
        f"- rationale: {p.rationale}\n"
        f"- estimated_energy_savings_pct: {p.estimated_energy_savings_pct}\n"
        f"- performance_risk: {p.performance_risk}\n"
        f"- manifest_yaml:\n{p.manifest_yaml}"
        for name, p in final_proposals.items()
    )
    critiques_block = "\n".join(
        f"[Tour {r.round_number}] {c.from_strategy} -> {c.target_strategy} "
        f"(agrees={c.agrees}) : {c.comment}"
        for r in transcript
        for c in r.critiques
    ) or "(aucun désaccord relevé lors du débat)"

    prompt = (
        f"YAML validé d'origine de ce composant (avant optimisation) :\n{yaml_chunk}\n\n"
        f"{proposals_block}\n\n"
        f"Transcript des critiques échangées pendant le débat :\n{critiques_block}\n\n"
        f"Contexte énergie de ce composant :\n{_component_energy_context(component)}"
    )
    if application_context:
        prompt += f"\n\nContexte global de l'application (résumé) : {application_context}"
    prompt += constraints_block(filter_constraints(component.component_name, global_constraints))

    raw = call_llm(_JUDGE_SYSTEM, prompt, agent_name="Agent4-Debate-Judge")
    result = extract_json(raw)
    return JudgeVerdict(
        component_name=component.component_name,
        manifest_yaml=result.get("manifest_yaml", yaml_chunk),
        reasoning=result.get("reasoning", ""),
        strategy_scores=result.get("strategy_scores", {}),
        chosen_elements=result.get("chosen_elements", {}),
        fields_addressed=result.get("fields_addressed", []),
        fields_left_open=result.get("fields_left_open", []),
        warnings=result.get("warnings", []),
    )


def _debate_for_component(component, yaml_chunk: str, global_constraints: list,
                           application_context: str) -> tuple[JudgeVerdict, list[DebateRound]]:
    max_turns = min(max(settings.DEBATE_MAX_TURNS, 1), _HARD_MAX_TURNS)

    # --- Étape 1 : fan-out des propositions initiales -------------------
    current_proposals = _run_fan_out_proposals(
        component, yaml_chunk, global_constraints, application_context
    )

    # --- Étape 2 : tour(s) de débat borné(s), toujours en fan-out -------
    transcript: list[DebateRound] = []
    critiques_by_target: dict[str, list[StrategyCritique]] = {s: [] for s in STRATEGIES}
    for turn in range(1, max_turns + 1):
        round_critiques, revised = _run_fan_out_critiques(
            component, yaml_chunk, current_proposals, critiques_by_target,
            global_constraints, application_context,
        )
        current_proposals = revised
        transcript.append(DebateRound(
            round_number=turn,
            proposals=list(current_proposals.values()),
            critiques=round_critiques,
        ))
        # Prépare les critiques reçues pour le tour suivant (une seule
        # fois par cible, pour ne pas répéter les mêmes remarques si
        # DEBATE_MAX_TURNS=2).
        critiques_by_target = {s: [] for s in STRATEGIES}
        for c in round_critiques:
            critiques_by_target.setdefault(c.target_strategy, []).append(c)

    # --- Étape 3 : verdict du Juge (séquentiel, un seul appel) ----------
    verdict = _run_judge(
        component, yaml_chunk, current_proposals, transcript,
        global_constraints, application_context,
    )
    return verdict, transcript


def run_agent4_debate(state: PipelineState) -> PipelineState:
    if not state.manifest_v2_yaml or state.spec is None or not state.spec.components:
        state.error = "Agent 4 (débat) : manifeste validé ou composants manquants en entrée."
        return state

    spec = state.spec
    component_names = [c.component_name for c in spec.components]
    log_step(
        "Agent 4 - Débat multi-agents (Énergie)",
        f"Débat Consolidation/Sizing/Autoscaling pour {len(component_names)} "
        f"composant(s), {min(max(settings.DEBATE_MAX_TURNS, 1), _HARD_MAX_TURNS)} "
        f"tour(s) de critique...",
    )

    try:
        chunks, leftover_yaml, truly_unmatched = _split_by_component(
            state.manifest_v2_yaml, component_names
        )
    except ValueError as e:
        state.error = f"Agent 4 (débat) : impossible de parser le manifeste validé : {e}"
        return state

    manifest_parts: list[str] = []
    fields_addressed: list[str] = []
    fields_left_open: list[str] = []
    actions: list[str] = []
    warnings: list[str] = []

    for component in spec.components:
        prefix = f"[{component.component_name}] "
        chunk = chunks.get(component.component_name, "")
        if not chunk:
            warnings.append(
                f"{prefix}Aucun document YAML retrouvé pour ce composant dans le "
                f"manifeste validé (nom attendu: '{component.component_name}') — "
                f"débat énergie ignoré pour ce composant."
            )
            log_warning("Agent 4 - Débat multi-agents (Énergie)", warnings[-1])
            continue

        if component.workload_type in ("Job", "CronJob"):
            actions.append(
                f"{prefix}workload_type='{component.workload_type}' : pas de "
                f"HPA/ScaledObject attendu des stratégies (non applicable), "
                f"seulement dimensionnement/placement."
            )

        verdict, transcript = _debate_for_component(
            component, chunk, spec.global_constraints, spec.application_context
        )
        state.debate_transcripts[component.component_name] = transcript
        state.judge_verdicts.append(verdict)

        manifest_parts.append(verdict.manifest_yaml)

        conflicts = [c for r in transcript for c in r.critiques if not c.agrees]
        actions.append(
            f"{prefix}Débat conclu : {len(transcript)} tour(s) de critique, "
            f"{len(conflicts)} conflit(s) réel(s) relevé(s), scores "
            f"{verdict.strategy_scores}."
        )
        if verdict.chosen_elements:
            actions.append(f"{prefix}Éléments retenus par stratégie : {verdict.chosen_elements}")
        actions.append(f"{prefix}{verdict.reasoning}")

        for w in verdict.warnings:
            log_warning("Agent 4 - Débat multi-agents (Énergie)", prefix + w)
            warnings.append(prefix + w)

        fields_addressed += [prefix + f for f in verdict.fields_addressed]
        fields_left_open += [prefix + f for f in verdict.fields_left_open]

    if leftover_yaml:
        manifest_parts.append(leftover_yaml)
        if truly_unmatched:
            warnings.append(
                f"Documents non associés à un composant connu, conservés tels "
                f"quels (non optimisés énergétiquement) : {truly_unmatched}."
            )

    state.manifest_v3_yaml = "\n---\n".join(p for p in manifest_parts if p)

    state.reports.append(AgentReport(
        agent_name="Agent 4 - Débat multi-agents (Énergie)",
        fields_addressed=fields_addressed,
        fields_left_open=fields_left_open,
        actions=actions,
        warnings=warnings,
    ))
    return state
