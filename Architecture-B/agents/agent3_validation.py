"""agents/agent3_validation.py — Agent 3 : validation/correction structurelle."""

from __future__ import annotations

from pathlib import Path

from llm_client import call_llm, extract_json
from schemas import AgentReport, PipelineState
from utils.k8s_validate import strip_duplicate_auto_injected_sidecars
from utils.logging_utils import log_step, log_warning
from utils.yaml_utils import dump_all_documents, load_all_documents

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SYSTEM = (PROMPTS_DIR / "agent3_system.txt").read_text(encoding="utf-8")

UNMAPPED_MARKER = "# ⚠️ GÉNÉRATION LIBRE"


def _split_off_unmapped_block(manifest_yaml: str) -> tuple[str, str]:
    """
    Le bloc best-effort (`unmapped_requirements`, généré par l'Agent 2)
    n'est PAS une vraie ressource Kubernetes structurée — Agent 3
    régénère tout le YAML via un appel LLM, et rien ne garantit qu'il
    préserve un bloc qu'il pourrait juger être du "bruit" en le
    réécrivant. On isole ce bloc AVANT de l'envoyer à l'Agent 3 (qui ne
    voit et ne valide donc que le YAML structuré connu), et on le
    réinjecte APRÈS, par code, quoi qu'ait fait le LLM entre-temps.
    """
    documents = manifest_yaml.split("\n---\n")
    core_docs, unmapped_docs = [], []
    for doc in documents:
        (unmapped_docs if UNMAPPED_MARKER in doc else core_docs).append(doc)
    return "\n---\n".join(core_docs), "\n---\n".join(unmapped_docs)


def run_agent3(state: PipelineState) -> PipelineState:
    if not state.manifest_v1_yaml or state.spec is None:
        state.error = "Agent 3 : manifeste ou spec manquant en entrée."
        return state

    log_step("Agent 3 - Validation", "Vérification structurelle du manifeste...")

    manifest_core, unmapped_block = _split_off_unmapped_block(state.manifest_v1_yaml)

    spec = state.spec
    relevant_spec = {
        "namespace": spec.namespace,
        "architecture_type": spec.architecture_type,
        "components": [
            c.model_dump(include={
                "component_name", "workload_type", "image", "replicas",
                "labels", "ports", "env_vars", "volumes", "sidecars",
                "ingress", "rbac", "cron_schedule", "observability_style",
            })
            for c in spec.components
        ],
    }

    prompt = (
        f"Manifeste à valider :\n{manifest_core}\n\n"
        f"NormalizedSpec de référence (champs structurels) :\n{relevant_spec}"
    )
    raw = call_llm(SYSTEM, prompt, agent_name="Agent 3 - Validation")
    result = extract_json(raw)

    corrected_core = result.get("manifest_yaml", manifest_core)

    # Filet de sécurité déterministe : indépendant de ce que le LLM a
    # réellement fait, on retire tout conteneur sidecar "nu" en doublon
    # d'une annotation d'injection automatique déjà présente. Si le
    # manifeste ne parse pas (LLM ayant produit du YAML invalide malgré
    # le prompt), on n'applique pas cette passe et on laisse Agent 5
    # remonter l'erreur de parsing comme avant — ce garde-fou ne doit
    # jamais être la cause d'un crash de l'Agent 3.
    dedup_actions: list[str] = []
    try:
        core_docs = load_all_documents(corrected_core)
        dedup_actions = strip_duplicate_auto_injected_sidecars(core_docs)
        if dedup_actions:
            corrected_core = dump_all_documents(core_docs)
    except ValueError:
        pass

    state.manifest_v2_yaml = (
        f"{corrected_core}\n---\n{unmapped_block}" if unmapped_block else corrected_core
    )

    for w in result.get("warnings", []):
        log_warning("Agent 3 - Validation", w)
    for a in dedup_actions:
        log_warning("Agent 3 - Validation", a)

    state.reports.append(AgentReport(
        agent_name="Agent 3 - Validation",
        fields_addressed=result.get("fields_addressed", []),
        fields_left_open=result.get("fields_left_open", []),
        actions=(
            result.get("checks_passed", [])
            + [f"Corrigé: {c}" for c in result.get("checks_failed_and_fixed", [])]
            + [f"Corrigé (déterministe): {a}" for a in dedup_actions]
        ),
        warnings=result.get("warnings", []),
    ))
    return state
