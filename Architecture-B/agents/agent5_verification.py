"""
agents/agent5_verification.py — Agent 5 : vérification syntaxique finale +
audit de traçabilité (le "filet de sécurité" qui rend visible tout ce qui
aurait pu se perdre en cours de pipeline, sans jamais revenir en arrière).
"""

from __future__ import annotations

from pathlib import Path

from llm_client import call_llm, extract_json
from schemas import AgentReport, PipelineState
from utils.logging_utils import log_step, log_warning, log_error
from utils.yaml_utils import load_all_documents
from utils.k8s_validate import full_validation

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SYSTEM = (PROMPTS_DIR / "agent5_system.txt").read_text(encoding="utf-8")


def run_agent5(state: PipelineState) -> PipelineState:
    if not state.manifest_v3_yaml or state.spec is None:
        state.error = "Agent 5 : manifeste énergie manquant en entrée."
        return state

    log_step("Agent 5 - Vérification finale", "Contrôle syntaxique + audit de traçabilité...")

    spec = state.spec
    reports_summary = [r.model_dump() for r in state.reports]

    prompt = (
        f"Manifeste final (avant vérification) :\n{state.manifest_v3_yaml}\n\n"
        f"NormalizedSpec complète :\n{spec.model_dump()}\n\n"
        f"Rapports des agents précédents :\n{reports_summary}"
    )
    raw = call_llm(SYSTEM, prompt, agent_name="Agent 5 - Vérification finale")
    result = extract_json(raw)

    final_yaml = result.get("manifest_yaml", state.manifest_v3_yaml)

    # Double vérification déterministe (code Python), en complément du LLM :
    # un LLM peut se tromper sur une vérification syntaxique, du code non.
    deterministic_errors: list[str] = []
    try:
        docs = load_all_documents(final_yaml)
        all_traffic_windows = [
            tw.model_dump()
            for component in spec.components
            for tw in component.traffic_windows
        ]
        deterministic_errors = full_validation(docs, traffic_windows=all_traffic_windows)
    except ValueError as e:
        deterministic_errors = [str(e)]

    if deterministic_errors:
        for e in deterministic_errors:
            log_error("Agent 5 - Vérification finale", e)
    else:
        log_step("Agent 5 - Vérification finale", "Contrôle déterministe : OK, aucun problème structurel détecté.")

    # Vérification déterministe (pas de LLM) : toute exigence hors du
    # schéma structuré DOIT rester visible dans l'audit, quoi qu'il arrive
    # côté LLM. C'est ce qui empêche le piège "Aucun point ouvert détecté
    # ✅" alors qu'une exigence a été générée en best-effort, non vérifiée.
    unmapped_warning = None
    if spec.unmapped_requirements:
        unmapped_warning = (
            f"{len(spec.unmapped_requirements)} exigence(s) générée(s) en mode "
            f"BEST-EFFORT, hors du schéma structuré habituel — non couvertes par "
            f"les cross-vérifications spécifiques (contrairement au reste du "
            f"manifeste), à valider manuellement avant tout déploiement réel : "
            + "; ".join(
                f"'{r.text}'" + (f" (kind supposé: {r.suggested_kind})" if r.suggested_kind else "")
                for r in spec.unmapped_requirements
            )
        )
        log_warning("Agent 5 - Vérification finale", unmapped_warning)

    unresolved = result.get("unresolved_items", []) + deterministic_errors
    if unmapped_warning:
        unresolved.append(unmapped_warning)
    if unresolved:
        log_warning(
            "Agent 5 - Vérification finale",
            f"Éléments à examiner par l'utilisateur : {unresolved}",
        )

    state.manifest_final_yaml = final_yaml

    state.reports.append(AgentReport(
        agent_name="Agent 5 - Vérification finale",
        fields_addressed=result.get("fields_addressed", []),
        fields_left_open=unresolved,
        actions=(
            result.get("syntax_checks", [])
            + [f"Corrigé: {c}" for c in result.get("syntax_fixes", [])]
            + (["Contrôle déterministe Python : OK"] if not deterministic_errors
               else [f"Contrôle déterministe Python : {len(deterministic_errors)} erreur(s)"])
        ),
        warnings=result.get("warnings", []),
    ))

    state.traceability_matrix = result.get("traceability_matrix", [])
    return state
