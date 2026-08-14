"""
agents/agent5_verification.py — Agent 5 : vérification syntaxique finale +
audit de traçabilité (le "filet de sécurité" qui rend visible tout ce qui
aurait pu se perdre en cours de pipeline, sans jamais revenir en arrière).
"""

from __future__ import annotations

from pathlib import Path

from llm_client import call_llm, extract_json
from schemas import AgentReport, PipelineState, RepairRequest
from utils.logging_utils import log_step, log_warning, log_error
from utils.yaml_utils import load_all_documents
from utils.k8s_validate import full_validation
from agents.agent3_validation import _strip_duplicate_auto_inject_containers

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SYSTEM = (PROMPTS_DIR / "agent5_system.txt").read_text(encoding="utf-8")


def run_agent5(state: PipelineState) -> PipelineState:
    if not state.manifest_v3_yaml or state.spec is None:
        state.error = "Agent 5 : manifeste énergie manquant en entrée."
        return state

    log_step("Agent 5 - Vérification finale", "Contrôle syntaxique + audit de traçabilité...")

    spec = state.spec
    reports_summary = [r.model_dump() for r in state.reports]

    # Architecture C : sur une REVÉRIFICATION (après un passage par
    # "repair"), l'entrée doit être le manifeste RÉPARÉ, pas le manifeste
    # d'origine issu d'Agent 4. `state.manifest_final_yaml` n'est jamais
    # vide à ce stade si on est dans une boucle de réparation (il est posé
    # à la fin de CETTE fonction, et mis à jour par run_repair) -- donc le
    # préférer à `manifest_v3_yaml` dès qu'il existe couvre exactement ce
    # cas, sans rien changer au tout premier passage (où il est encore
    # None). Bug réel trouvé par le test d'intégration bout-en-bout avant
    # cette correction : sans ce fallback, la revérification relisait
    # toujours le manifeste NON réparé, rendant la boucle inutile.
    current_manifest = state.manifest_final_yaml or state.manifest_v3_yaml

    prompt = (
        f"Manifeste final (avant vérification) :\n{current_manifest}\n\n"
        f"NormalizedSpec complète :\n{spec.model_dump()}\n\n"
        f"Rapports des agents précédents :\n{reports_summary}\n\n"
    )
    if state.sidecar_injection_mode:
        prompt += (
            f"Mode d'injection de chaque sidecar, DÉCIDÉ EN AMONT par "
            f"l'Agent 2 de façon déterministe (PAS à re-déduire toi-même) : "
            f"{state.sidecar_injection_mode}\n"
            f"Pour un sidecar en mode 'manual_container', vérifie qu'il "
            f"apparaît bien dans le même Pod que son composant (jamais "
            f"comme Deployment séparé). Pour un sidecar en mode "
            f"'annotations', l'ABSENCE de conteneur pour lui n'est PAS une "
            f"anomalie -- vérifie seulement la présence des annotations, et "
            f"NE RAJOUTE JAMAIS de conteneur manuel pour lui.\n\n"
        )
    prompt += (
        f"NOUVEAU (Architecture C) — en plus de `unresolved_items` (texte "
        f"libre, pour tout ce qui n'est structurellement pas réparable par "
        f"un agent, ex: exigence organisationnelle hors scope K8s), "
        f"remplis aussi `repair_requests` pour CHAQUE gap CONCRÈTEMENT "
        f"réparable : une ressource identifiable qui n'a pas hérité d'une "
        f"`global_constraints` alors que son `scope` la couvre, ou un champ "
        f"structurel manquant qu'un agent peut ajouter. Chaque entrée : "
        f"`target_resource` (ex: 'PostgresCluster/postgres-cluster'), "
        f"`target_agent` ('agent2_template' pour un champ structurel/"
        f"sécurité manquant, 'agent4_energie' pour un problème de "
        f"dimensionnement/scaling), `missing_constraint` (précis, "
        f"actionnable), `reason`. Ne mets PAS dans `repair_requests` ce qui "
        f"n'est pas réparable par un simple ajout de champ (ex: une "
        f"contrainte de conformité organisationnelle) — ça reste dans "
        f"`unresolved_items`."
    )
    raw = call_llm(SYSTEM, prompt, agent_name="Agent 5 - Vérification finale")
    result = extract_json(raw)

    final_yaml = result.get("manifest_yaml", current_manifest)

    # Même filet de sécurité déterministe qu'après l'Agent 3 (voir
    # agents/agent3_validation.py::_strip_duplicate_auto_inject_containers) :
    # l'Agent 5 a aussi le droit de corriger le YAML, donc il peut en
    # théorie réintroduire le même doublon annotations+conteneur manuel
    # qu'Agent 3 -- on l'applique donc une deuxième fois ici, en dernière
    # ligne avant la remise du manifeste final.
    final_yaml, dedup_notes = _strip_duplicate_auto_inject_containers(
        final_yaml, state.sidecar_injection_mode
    )
    for note in dedup_notes:
        log_warning("Agent 5 - Vérification finale", note)

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

    # Parsing DÉFENSIF des repair_requests : contrairement aux champs de
    # NormalizedSpec (validés strictement par Pydantic dès l'Agent 1), ici
    # une entrée malformée ne doit PAS faire échouer tout Agent 5 — elle
    # est simplement dégradée en unresolved_item texte libre (comportement
    # d'avant, jamais pire que l'ancien pipeline) plutôt que de perdre le
    # run entier sur un problème de forme.
    repair_requests: list[RepairRequest] = []
    for item in result.get("repair_requests", []):
        try:
            repair_requests.append(RepairRequest(
                target_resource=item["target_resource"],
                target_agent=item["target_agent"],
                missing_constraint=item["missing_constraint"],
                reason=item.get("reason", ""),
                attempt=state.repair_attempt + 1,
            ))
        except (KeyError, TypeError, ValueError) as e:
            degraded = f"[repair_request malformée, dégradée] {item} ({e})"
            unresolved.append(degraded)
            log_warning("Agent 5 - Vérification finale", degraded)

    state.repair_requests = repair_requests

    state.manifest_final_yaml = final_yaml

    state.reports.append(AgentReport(
        agent_name="Agent 5 - Vérification finale",
        fields_addressed=result.get("fields_addressed", []),
        fields_left_open=unresolved,
        actions=(
            result.get("syntax_checks", [])
            + [f"Corrigé: {c}" for c in result.get("syntax_fixes", [])]
            + [f"Corrigé (déterministe): {n}" for n in dedup_notes]
            + (["Contrôle déterministe Python : OK"] if not deterministic_errors
               else [f"Contrôle déterministe Python : {len(deterministic_errors)} erreur(s)"])
        ),
        warnings=result.get("warnings", []),
    ))

    state.traceability_matrix = result.get("traceability_matrix", [])
    return state
