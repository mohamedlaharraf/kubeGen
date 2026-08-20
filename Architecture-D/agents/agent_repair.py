"""
agents/agent_repair.py — le noeud de réparation ciblée de l'Architecture C.

Ce n'est PAS un sixième "agent spécialisé" comme 1-5 (qui ont chacun un
domaine fixe) : c'est un noeud d'ORCHESTRATION qui reçoit une liste de
`RepairRequest` (produite par Agent 5) et route chacune vers un correctif
CIBLÉ sur le document concerné, sans régénérer quoi que ce soit d'autre.

Pourquoi une régénération complète du composant serait une mauvaise idée
ici : au moment où Agent 5 détecte un gap, le document a déjà traversé
Agent 2 (structure/sécurité), potentiellement Agent 3 (corrections) et
Agent 4 (optimisation énergie). Régénérer le composant entier depuis les
specs perdrait ces trois passes pour gagner une seule correction — le
patch ciblé (ce module) préserve tout sauf ce qui doit changer.
"""

from __future__ import annotations

from pathlib import Path

from llm_client import call_llm, extract_json
from schemas import AgentReport, PipelineState
from utils.logging_utils import log_step, log_warning
from utils.yaml_utils import load_all_documents, dump_all_documents
from config import settings

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SYSTEM = (PROMPTS_DIR / "repair_system.txt").read_text(encoding="utf-8")

MAX_REPAIR_ATTEMPTS = settings.MAX_REPAIR_ATTEMPTS


def _find_doc(docs: list[dict], kind: str, name: str) -> int | None:
    """Retourne l'index du document (kind, name) dans `docs`, ou None."""
    for i, d in enumerate(docs):
        if d.get("kind") == kind and d.get("metadata", {}).get("name") == name:
            return i
    return None


def _pair_list_items_by_name(original_list: list, corrected_list: list) -> list | None:
    """
    Associe les éléments de deux listes par leur champ `name` -- le cas
    dominant dans un manifeste K8s (containers, volumes, env, ports...).
    Retourne None si le pairing n'est pas fiable (élément sans `name`,
    liste vide, etc.), auquel cas l'appelant garde `corrected` tel quel
    plutôt que de risquer un mauvais appariement.
    """
    if not original_list or not corrected_list:
        return None
    if not all(isinstance(i, dict) and "name" in i for i in original_list):
        return None
    if not all(isinstance(i, dict) and "name" in i for i in corrected_list):
        return None
    by_name = {i["name"]: i for i in original_list}
    return [(by_name.get(i["name"]), i) for i in corrected_list]


def _restored_paths(original: dict, corrected: dict, prefix: str = "") -> list[str]:
    """
    Liste (dot-notation) les clés présentes dans `original` mais absentes
    de `corrected` -- c'est-à-dire tout ce que le correcteur a fait
    disparaître, alors que le prompt lui demande explicitement de
    "préserver tout le reste EXACTEMENT tel quel". Récursif sur les dicts
    imbriqués ET sur les listes d'objets nommés (containers, volumes...),
    appariés par `name` -- c'est le cas dominant dans un manifeste K8s,
    contrairement à une liste de scalaires où le pairing n'a pas de sens.
    """
    paths: list[str] = []
    if not isinstance(original, dict) or not isinstance(corrected, dict):
        return paths
    for key, orig_value in original.items():
        path = f"{prefix}.{key}" if prefix else key
        if key not in corrected:
            paths.append(path)
        elif isinstance(orig_value, dict) and isinstance(corrected.get(key), dict):
            paths.extend(_restored_paths(orig_value, corrected[key], path))
        elif isinstance(orig_value, list) and isinstance(corrected.get(key), list):
            pairs = _pair_list_items_by_name(orig_value, corrected[key])
            if pairs:
                for orig_item, corr_item in pairs:
                    if orig_item is None:
                        continue  # élément ajouté par le correcteur, rien à comparer
                    item_prefix = f"{path}[{corr_item.get('name')}]"
                    if isinstance(orig_item, dict) and isinstance(corr_item, dict):
                        paths.extend(_restored_paths(orig_item, corr_item, item_prefix))
    return paths


def _merge_preserving_missing_fields(original: dict, corrected: dict) -> dict:
    """
    Filet de sécurité DÉTERMINISTE contre la perte silencieuse de champs
    par le correcteur -- même principe que le filet de cohérence sidecar
    (utils/sidecar_injection.py) : on ne fait pas confiance à l'instruction
    "préserve tout le reste" du prompt seule, on la fait respecter par
    code après coup.

    Bug réel observé en production qui motive ce filet : une réparation
    qui rétablissait `privileged`/`runAsUser` sur le securityContext d'UN
    conteneur (dans `spec.template.spec.containers`, une LISTE) a fait
    disparaître `readOnlyRootFilesystem` au passage, sans que rien ne le
    signale. Une fusion naïve qui ne descend pas dans les listes ne
    l'aurait pas attrapé -- d'où le pairing par `name` ci-dessous, pas
    juste une fusion de dicts au premier niveau.

    Toute clé présente dans `original` mais absente de `corrected` est
    restaurée depuis `original` (dicts ET listes d'objets nommés,
    récursivement). Les valeurs explicitement modifiées par `corrected`
    sont conservées telles quelles -- ce mécanisme ne peut QUE restaurer
    un oubli, jamais annuler une correction volontaire.
    """
    if not isinstance(original, dict) or not isinstance(corrected, dict):
        return corrected
    merged = dict(corrected)
    for key, orig_value in original.items():
        if key not in corrected:
            merged[key] = orig_value
        elif isinstance(orig_value, dict) and isinstance(corrected[key], dict):
            merged[key] = _merge_preserving_missing_fields(orig_value, corrected[key])
        elif isinstance(orig_value, list) and isinstance(corrected[key], list):
            pairs = _pair_list_items_by_name(orig_value, corrected[key])
            if pairs is not None:
                merged[key] = [
                    _merge_preserving_missing_fields(o, c) if isinstance(o, dict) and isinstance(c, dict) else c
                    for o, c in pairs
                ]
            # sinon : pas de pairing fiable, `corrected[key]` reste tel
            # quel (déjà dans `merged` via dict(corrected))
    return merged


def _repair_document(doc: dict, missing_constraint: str, reason: str, target_agent: str) -> tuple[dict, bool, str]:
    prompt = (
        f"Document YAML actuel (représenté en JSON, structure identique) :\n{doc}\n\n"
        f"Agent d'origine de ce document : {target_agent}\n"
        f"Gap à corriger : {missing_constraint}\n"
        f"Raison (pourquoi c'est un gap) : {reason}\n\n"
        f"Corrige UNIQUEMENT ce gap précis, ne change rien d'autre."
    )
    raw = call_llm(SYSTEM, prompt, agent_name="Réparation ciblée")
    result = extract_json(raw)
    corrected = result.get("corrected_document", doc)
    applied = bool(result.get("applied", False))
    note = result.get("note", "")
    return corrected, applied, note


def run_repair(state: PipelineState) -> PipelineState:
    """
    Traite TOUTES les `repair_requests` en attente en une passe, puis
    vide la liste — la revérification suivante d'Agent 5 la repeuplera
    si un gap persiste malgré la tentative de correction (ex: le LLM de
    réparation a lui-même jugé ne pas pouvoir corriger raisonnablement).
    """
    if not state.repair_requests or not state.manifest_final_yaml:
        return state

    log_step(
        "Réparation ciblée",
        f"{len(state.repair_requests)} gap(s) à traiter (tentative "
        f"{state.repair_attempt + 1}/{MAX_REPAIR_ATTEMPTS})...",
    )

    try:
        docs = load_all_documents(state.manifest_final_yaml)
    except ValueError as e:
        state.error = f"Réparation ciblée : impossible de re-parser le manifeste : {e}"
        return state

    actions: list[str] = []
    warnings: list[str] = []
    fields_addressed: list[str] = []
    fields_left_open: list[str] = []

    for req in state.repair_requests:
        if req.attempt > MAX_REPAIR_ATTEMPTS:
            msg = (
                f"[abandon après {MAX_REPAIR_ATTEMPTS} tentative(s)] "
                f"{req.target_resource} : {req.missing_constraint}"
            )
            fields_left_open.append(msg)
            log_warning("Réparation ciblée", msg)
            continue

        try:
            kind, name = req.target_resource.split("/", 1)
        except ValueError:
            msg = f"target_resource mal formé, réparation ignorée : {req.target_resource!r}"
            warnings.append(msg)
            log_warning("Réparation ciblée", msg)
            continue

        idx = _find_doc(docs, kind, name)
        if idx is None:
            msg = (
                f"{req.target_resource} introuvable dans le manifeste actuel "
                f"(déjà corrigé par une tentative précédente, ou nom/kind "
                f"incorrect) — réparation ignorée."
            )
            warnings.append(msg)
            log_warning("Réparation ciblée", msg)
            continue

        corrected, applied, note = _repair_document(
            docs[idx], req.missing_constraint, req.reason, req.target_agent
        )

        if applied:
            restored = _restored_paths(docs[idx], corrected)
            docs[idx] = _merge_preserving_missing_fields(docs[idx], corrected)
            action_msg = (
                f"[réparation #{req.attempt}] {req.target_resource} corrigé "
                f"via {req.target_agent} : {req.missing_constraint}"
                + (f" — {note}" if note else "")
            )
            if restored:
                action_msg += (
                    f" (⚠️ {len(restored)} champ(s) restauré(s) automatiquement, "
                    f"absents par erreur de la réponse du correcteur malgré la "
                    f"consigne de préservation : {restored})"
                )
                log_warning(
                    "Réparation ciblée",
                    f"{req.target_resource} : le correcteur a fait disparaître "
                    f"{restored} en corrigeant '{req.missing_constraint}' -- "
                    f"restauré automatiquement, à revérifier.",
                )
            actions.append(action_msg)
            fields_addressed.append(f"repair: {req.target_resource} -> {req.missing_constraint}")
        else:
            msg = (
                f"{req.target_resource} : correction jugée impossible par "
                f"l'agent de réparation" + (f" ({note})" if note else "") +
                f" — reste dans les points ouverts."
            )
            fields_left_open.append(msg)
            log_warning("Réparation ciblée", msg)

    state.manifest_final_yaml = dump_all_documents(docs)
    state.repair_attempt += 1
    state.repair_requests = []  # revérification suivante repeuplera si besoin

    state.reports.append(AgentReport(
        agent_name=f"Réparation ciblée (tentative {state.repair_attempt}/{MAX_REPAIR_ATTEMPTS})",
        fields_addressed=fields_addressed,
        fields_left_open=fields_left_open,
        actions=actions,
        warnings=warnings,
    ))
    return state
