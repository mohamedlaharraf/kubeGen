"""
agents/agent4_energie.py — Agent 4 : optimisation énergétique, COMPOSANT PAR
COMPOSANT.

Chaque `ServiceComponent` peut avoir son propre profil de charge
(`energy_goals`/`traffic_windows` différents — ex: l'API scale sur horaires,
le worker asynchrone scale sur autre chose). On isole donc, pour chaque
composant, les documents YAML qui lui appartiennent et on applique
l'optimisation énergie dessus séparément, avec seulement les champs énergie
DE CE composant dans le prompt.

Matching des documents à un composant :
1. `metadata.name == component_name` (workload principal, Service,
   NetworkPolicy — convention posée par l'Agent 2).
2. `metadata.name` commence par `"<component_name>-"` (ServiceAccount,
   Ingress, Role/RoleBinding, PVC, ScaledObject/HPA... convention de
   nommage standard). En cas d'ambiguïté (plusieurs component_name
   préfixes possibles), le préfixe le plus long gagne.
3. Les documents de kinds "transverses" (Namespace, ServiceMonitor,
   VirtualService, DestinationRule) qui ne matchent AUCUN composant sont
   attendus — ce n'est PAS une anomalie, ils sont conservés tels quels
   SANS déclencher d'avertissement.
4. Tout le reste qui ne matche rien ET n'est pas un kind transverse connu
   déclenche un avertissement (cas réellement inattendu, à signaler).
"""

from __future__ import annotations

from pathlib import Path

from llm_client import call_llm, extract_json
from schemas import AgentReport, PipelineState
from utils.logging_utils import log_step, log_warning
from utils.yaml_utils import load_all_documents, dump_all_documents
from utils.cost_estimate import HistoricalMetrics, size_from_metrics
from utils.k8s_validate import _pod_template as _get_pod_template

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SYSTEM = (PROMPTS_DIR / "agent4_system.txt").read_text(encoding="utf-8")

# Kinds qui ne sont légitimement rattachés à AUCUN composant précis (soit
# partagés entre composants, soit rattachés indirectement) : ne pas les
# signaler comme "orphelins" quand ils atterrissent dans le reste (leftover).
CROSS_CUTTING_KINDS = {"Namespace", "ServiceMonitor", "VirtualService", "DestinationRule"}


def _split_by_component(manifest_yaml: str, component_names: list[str]):
    """Retourne (dict component_name -> yaml_chunk, yaml_chunk_restant,
    liste des noms de documents réellement non reconnus)."""
    docs = load_all_documents(manifest_yaml)
    by_component: dict[str, list[dict]] = {name: [] for name in component_names}
    leftover: list[dict] = []
    truly_unmatched: list[str] = []

    # Préfixes triés du plus long au plus court pour éviter qu'un nom court
    # (ex: "api") ne capture par erreur un document d'un autre composant
    # dont le nom le contient (ex: "api-gateway-sa").
    sorted_names = sorted(component_names, key=len, reverse=True)

    for doc in docs:
        name = doc.get("metadata", {}).get("name", "") or ""
        kind = doc.get("kind", "")

        if name in by_component:
            by_component[name].append(doc)
            continue

        matched = next((cn for cn in sorted_names if name.startswith(f"{cn}-")), None)
        if matched:
            by_component[matched].append(doc)
            continue

        leftover.append(doc)
        if kind not in CROSS_CUTTING_KINDS:
            truly_unmatched.append(f"{kind}/{name}")

    chunks = {
        name: dump_all_documents(docs) if docs else ""
        for name, docs in by_component.items()
    }
    leftover_yaml = dump_all_documents(leftover) if leftover else ""
    return chunks, leftover_yaml, truly_unmatched


def _optimize_component(component, yaml_chunk: str) -> dict:
    relevant_spec = component.model_dump(
        include={
            "component_name", "workload_type", "replicas",
            "energy_goals", "resource_hints", "traffic_windows", "constraints",
        }
    )
    prompt = (
        f"Manifeste validé de ce composant :\n{yaml_chunk}\n\n"
        f"Contexte énergie (ServiceComponent, champs pertinents) :\n{relevant_spec}"
    )
    raw = call_llm(SYSTEM, prompt, agent_name="Agent 4 - Énergie")
    return extract_json(raw)


def _apply_metrics_override(yaml_text: str, component_name: str, metrics_dict: dict) -> tuple[str, bool]:
    """
    Remplace, de façon DÉTERMINISTE (post-traitement Python, pas une
    instruction au LLM qu'il pourrait ignorer), les `resources.requests/
    limits` du conteneur principal par un dimensionnement calculé à partir
    de métriques historiques réelles (voir utils/cost_estimate.py). Ne
    touche à rien d'autre dans le manifeste.
    """
    try:
        docs = load_all_documents(yaml_text)
    except ValueError:
        return yaml_text, False

    try:
        metrics = HistoricalMetrics(**metrics_dict)
        sizing = size_from_metrics(metrics)
    except (TypeError, ValueError):
        return yaml_text, False

    applied = False
    for doc in docs:
        if doc.get("metadata", {}).get("name") != component_name:
            continue
        pod_spec = _get_pod_template(doc).get("spec", {})
        for container in pod_spec.get("containers", []):
            if container.get("name") == component_name:
                container["resources"] = {
                    "requests": sizing["requests"], "limits": sizing["limits"],
                }
                applied = True

    if not applied:
        return yaml_text, False
    return dump_all_documents(docs), True


def run_agent4(state: PipelineState) -> PipelineState:
    if not state.manifest_v2_yaml or state.spec is None or not state.spec.components:
        state.error = "Agent 4 : manifeste validé ou composants manquants en entrée."
        return state

    spec = state.spec
    component_names = [c.component_name for c in spec.components]
    log_step(
        "Agent 4 - Énergie",
        f"Optimisation énergétique pour {len(component_names)} composant(s)...",
    )

    try:
        chunks, leftover_yaml, truly_unmatched = _split_by_component(
            state.manifest_v2_yaml, component_names
        )
    except ValueError as e:
        state.error = f"Agent 4 : impossible de parser le manifeste validé : {e}"
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
                f"optimisation énergie ignorée pour ce composant."
            )
            log_warning("Agent 4 - Énergie", warnings[-1])
            continue

        if component.workload_type in ("Job", "CronJob"):
            # Un Job/CronJob n'a pas de notion de réplicas persistants à
            # scaler : pas d'HPA/ScaledObject pertinent, seulement un
            # dimensionnement resources.requests/limits raisonnable.
            actions.append(
                f"{prefix}workload_type='{component.workload_type}' : pas de "
                f"HPA/ScaledObject généré (non applicable), uniquement "
                f"dimensionnement resources.requests/limits."
            )

        result = _optimize_component(component, chunk)
        enriched_yaml = result.get("manifest_yaml", chunk)

        if component.component_name in state.historical_metrics:
            enriched_yaml, applied = _apply_metrics_override(
                enriched_yaml, component.component_name,
                state.historical_metrics[component.component_name],
            )
            if applied:
                actions.append(
                    f"{prefix}resources.requests/limits REMPLACÉS par un "
                    f"dimensionnement calculé à partir de métriques historiques "
                    f"réelles (p50/p95 mesurés), pas une estimation LLM."
                )
            else:
                warnings.append(
                    f"{prefix}Métriques historiques fournies mais non applicables "
                    f"(format invalide ou conteneur principal introuvable) — "
                    f"dimensionnement LLM conservé."
                )

        manifest_parts.append(enriched_yaml)

        for w in result.get("warnings", []):
            log_warning("Agent 4 - Énergie", prefix + w)
            warnings.append(prefix + w)

        energy_open = result.get("energy_goals_left_open", [])
        if energy_open:
            log_warning("Agent 4 - Énergie", f"{prefix}Objectifs énergie non traités: {energy_open}")

        fields_addressed += [prefix + f for f in result.get("fields_addressed", [])]
        fields_addressed += [
            f"{prefix}energy_goals: {g}" for g in result.get("energy_goals_addressed", [])
        ]
        fields_left_open += [prefix + f for f in result.get("fields_left_open", [])]
        fields_left_open += [prefix + f for f in energy_open]
        actions += [prefix + a for a in result.get("actions", [])]

    if leftover_yaml:
        manifest_parts.append(leftover_yaml)
        if truly_unmatched:
            warnings.append(
                f"Documents non associés à un composant connu, conservés tels "
                f"quels (non optimisés énergétiquement) : {truly_unmatched}."
            )

    state.manifest_v3_yaml = "\n---\n".join(p for p in manifest_parts if p)

    state.reports.append(AgentReport(
        agent_name="Agent 4 - Énergie",
        fields_addressed=fields_addressed,
        fields_left_open=fields_left_open,
        actions=actions,
        warnings=warnings,
    ))
    return state
