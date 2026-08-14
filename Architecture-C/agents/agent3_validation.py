"""agents/agent3_validation.py — Agent 3 : validation/correction structurelle.

Architecture C, deuxième mécanisme (le premier étant le blackboard de
`global_constraints`) : Agent 3 ne se contente plus de corriger
silencieusement ce qu'il peut — pour les problèmes de SCHÉMA ou de
SÉCURITÉ qu'il détecte, il les signale sous forme de `ValidationError`
structurées plutôt que de les corriger lui-même, pour que le Générateur
(Agent 2) ait la responsabilité de les corriger avec ce retour explicite
(boucle Generator <-> Validator, voir graph.py::_route_after_agent3 et
agents/agent2_template.py::regenerate_with_feedback).

Ce qui reste inchangé : Agent 3 corrige toujours lui-même les problèmes
purement mécaniques (formatage de quantités, structure YAML cassée) --
seuls les problèmes de fond (sécurité manquante, violation de schéma
qu'il ne peut pas résoudre par une simple réécriture) remontent en
`validation_errors`.
"""

from __future__ import annotations

import re
from pathlib import Path

from llm_client import call_llm, extract_json
from schemas import AgentReport, PipelineState, ValidationError
from utils.logging_utils import log_step, log_warning
from utils.k8s_validate import full_validation, _pod_template as _get_pod_template
from utils.yaml_utils import load_all_documents, dump_all_documents
from utils.sidecar_injection import ANNOTATIONS
from config import settings

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SYSTEM = (PROMPTS_DIR / "agent3_system.txt").read_text(encoding="utf-8")

UNMAPPED_MARKER = "# ⚠️ GÉNÉRATION LIBRE"

# Filet de sécurité déterministe (zéro LLM) contre le conflit observé en
# production : Agent 3 a flagué `privileged`/`root` comme validation_error
# sur un composant dont la spec demandait EXPLICITEMENT cette posture
# (outil de diagnostic bas niveau) -- la boucle de correction a alors
# défait un choix sciemment voulu par l'utilisateur, avant que la
# réparation ciblée (Agent 5) ne le rétablisse. Deux agents qui se
# contredisent sur un simple manque de contexte partagé.
#
# Chaque entrée : mots-clés côté validation_error -> mots-clés côté
# security_requirements qui, si présents ensemble, signalent que
# l'"anomalie" détectée est en fait une demande explicite.
_SECURITY_POSTURE_OVERLAP = [
    (("privileg",), ("privileg", "capabilit", "noyau", "kernel")),
    (("root", "runasuser: 0", "runasuser=0"), ("root", "runasuser: 0", "runasuser=0")),
    (("writable", "inscriptible", "readonlyrootfilesystem: false", "readonlyrootfilesystem=false"),
     ("inscriptible", "writable", "readonlyrootfilesystem: false", "readonlyrootfilesystem=false", "écrire")),
]


def _explicitly_requested(error: ValidationError, security_requirements_by_component: dict[str, list[str]]) -> bool:
    """
    Heuristique de SURFACE (chevauchement de mots-clés), pas une
    compréhension sémantique fine -- même esprit que
    `_constraints_seem_to_cover` dans agent1_analyse.py : suffisant pour
    attraper le cas net (une posture de sécurité explicitement demandée,
    re-signalée comme anomalie), pas pour juger finement de tous les cas.
    """
    if not error.resource or "/" not in error.resource:
        return False
    _, name = error.resource.split("/", 1)
    requirements = security_requirements_by_component.get(name, [])
    if not requirements:
        return False
    combined = " ".join(requirements).lower()
    error_text = f"{error.rule} {error.message}".lower()
    for error_keywords, requirement_keywords in _SECURITY_POSTURE_OVERLAP:
        if any(k in error_text for k in error_keywords) and any(k in combined for k in requirement_keywords):
            return True
    return False


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


def _approximate_line(yaml_text: str, resource: str | None) -> int | None:
    """
    Cherche la ligne de 'name: <name>' la plus proche APRÈS un 'kind:
    <Kind>' pour une ressource "Kind/name" -- approximatif par nature
    (YAML n'a pas de position canonique unique pour une "ressource"), mais
    suffisant pour orienter un humain ou un agent vers le bon endroit,
    sans avoir besoin d'un vrai parseur YAML préservant les positions
    source (coût d'implémentation disproportionné pour ce que ça
    apporterait ici).
    """
    if not resource or "/" not in resource:
        return None
    kind, name = resource.split("/", 1)
    kind_pattern = re.compile(rf"^kind:\s*{re.escape(kind)}\s*$", re.MULTILINE)
    name_pattern = re.compile(rf"^\s*name:\s*{re.escape(name)}\s*$", re.MULTILINE)

    kind_match = kind_pattern.search(yaml_text)
    if not kind_match:
        return None
    name_match = name_pattern.search(yaml_text, kind_match.end())
    if not name_match:
        return None
    return yaml_text.count("\n", 0, name_match.start()) + 1


def _deterministic_validation_errors(manifest_core: str) -> list[ValidationError]:
    """
    Les checks structurels déterministes (utils/k8s_validate.py,
    zéro LLM) restent la première ligne de défense -- rapides, fiables,
    sans coût de token. Converties en ValidationError pour alimenter la
    même boucle que les erreurs détectées par le LLM.
    """
    try:
        docs = load_all_documents(manifest_core)
    except ValueError:
        return []  # YAML cassé : le LLM va s'en charger via son propre retour
    if not docs:
        return []

    errors = []
    for raw_error in full_validation(docs):
        # Format existant : "[Kind] message". On récupère au moins le Kind
        # pour l'attribution -- le nom précis n'est pas toujours dans le
        # message, donc `resource` reste partiel plutôt qu'inventé.
        m = re.match(r"^\[(?P<kind>[\w.]+)\]\s*(?P<message>.*)$", raw_error)
        kind = m.group("kind") if m else None
        message = m.group("message") if m else raw_error
        errors.append(ValidationError(
            rule="deterministic-cross-reference",
            message=message,
            resource=kind,
        ))
    return errors


def _strip_duplicate_auto_inject_containers(
    manifest_yaml: str, injection_mode: dict[str, dict[str, dict]]
) -> tuple[str, list[str]]:
    """
    Filet de sécurité DÉTERMINISTE (post-traitement Python, pas une
    instruction au LLM qu'il pourrait ignorer) : pour tout sidecar dont
    `sidecar_injection_mode` dit "annotations" (décision prise en amont
    par l'Agent 2, voir utils/sidecar_injection.py), retire tout conteneur
    du MÊME NOM qui serait quand même présent dans
    `spec.template.spec.containers` -- que ce soit parce que l'Agent 2 ne
    l'a pas suivi, ou parce que l'Agent 3 l'a réintroduit en pensant
    "corriger" un sidecar manquant. C'est précisément le bug observé en
    production (doublon annotations + conteneur manuel Dapr).

    Ne touche à rien d'autre. Renvoie (yaml_corrigé, notes_de_correction).
    """
    if not injection_mode:
        return manifest_yaml, []

    auto_inject_names: set[str] = {
        sc_name
        for sc_map in injection_mode.values()
        for sc_name, cfg in sc_map.items()
        if cfg.get("mode") == ANNOTATIONS
    }
    if not auto_inject_names:
        return manifest_yaml, []

    try:
        docs = load_all_documents(manifest_yaml)
    except ValueError:
        return manifest_yaml, []

    notes: list[str] = []
    for doc in docs:
        pod_spec = _get_pod_template(doc).get("spec", {})
        containers = pod_spec.get("containers")
        if not containers:
            continue
        kept = [c for c in containers if c.get("name") not in auto_inject_names]
        if len(kept) != len(containers):
            removed = [c.get("name") for c in containers if c.get("name") in auto_inject_names]
            pod_spec["containers"] = kept
            name = doc.get("metadata", {}).get("name", "?")
            kind = doc.get("kind", "?")
            notes.append(
                f"{kind}/{name} : conteneur(s) manuel(s) {removed} retiré(s) "
                f"(sidecar en mode 'annotations' — géré par injection "
                f"automatique, un conteneur manuel en plus créerait un "
                f"doublon)."
            )

    if not notes:
        return manifest_yaml, []
    return dump_all_documents(docs), notes


def run_agent3(state: PipelineState) -> PipelineState:
    if not state.manifest_v1_yaml or state.spec is None:
        state.error = "Agent 3 : manifeste ou spec manquant en entrée."
        return state

    log_step("Agent 3 - Validation", "Vérification structurelle du manifeste...")

    # `current_yaml` (blackboard de la boucle Generator<->Validator) :
    # au premier passage, initialisé depuis la sortie d'Agent 2. À un
    # passage ultérieur (après une correction du Générateur), il contient
    # déjà la version corrigée -- c'est CETTE valeur qu'on valide, pas
    # toujours state.manifest_v1_yaml qui resterait figé sur la toute
    # première génération.
    source_yaml = state.current_yaml or state.manifest_v1_yaml
    manifest_core, unmapped_block = _split_off_unmapped_block(source_yaml)

    spec = state.spec
    relevant_spec = {
        "namespace": spec.namespace,
        "architecture_type": spec.architecture_type,
        "components": [
            c.model_dump(include={
                "component_name", "workload_type", "image", "replicas",
                "labels", "ports", "env_vars", "volumes", "sidecars",
                "ingress", "rbac", "cron_schedule", "observability_style",
                "security_requirements",
            })
            for c in spec.components
        ],
        # Contraintes du blackboard (Architecture C) : Agent 3 voit déjà
        # TOUS les composants en une fois (contrairement à Agent 2/4, un
        # par un), donc c'est l'endroit naturel pour vérifier qu'une
        # contrainte globale est bien reflétée PARTOUT où elle s'applique
        # dans le YAML structuré connu. Limite assumée : ce contrôle ne
        # porte PAS sur le bloc best-effort (unmapped_requirements), volontairement
        # exclu de la vue d'Agent 3 (voir _split_off_unmapped_block) — c'est
        # le rôle d'Agent 5 (vue complète + boucle de réparation) d'attraper
        # les gaps sur cette partie-là.
        "global_constraints": [c.model_dump() for c in spec.global_constraints],
    }

    prompt = (
        f"Manifeste à valider :\n{manifest_core}\n\n"
        f"NormalizedSpec de référence (champs structurels) :\n{relevant_spec}\n\n"
    )
    if state.sidecar_injection_mode:
        prompt += (
            f"Mode d'injection de chaque sidecar, DÉCIDÉ EN AMONT par "
            f"l'Agent 2 de façon déterministe (PAS à re-déduire toi-même) : "
            f"{state.sidecar_injection_mode}\n"
            f"Pour un sidecar en mode 'manual_container', vérifie qu'il "
            f"apparaît bien comme conteneur dans "
            f"spec.template.spec.containers. Pour un sidecar en mode "
            f"'annotations', l'ABSENCE de conteneur pour lui n'est PAS une "
            f"anomalie -- vérifie plutôt que les annotations attendues sont "
            f"présentes sur spec.template.metadata.annotations, et NE "
            f"RAJOUTE JAMAIS de conteneur manuel pour lui.\n\n"
        )
    prompt += (
        f"En plus des vérifications structurelles habituelles, vérifie que "
        f"chaque `global_constraints` listée ci-dessus est bien reflétée "
        f"dans TOUTES les ressources concernées par son `scope` (pas "
        f"seulement celle où elle semblerait la plus évidente). Si une "
        f"contrainte globale n'est visiblement respectée nulle part dans "
        f"ce manifeste, ajoute-le à `warnings` avec le texte exact de la "
        f"contrainte manquante.\n\n"
        f"NOUVEAU (Architecture C) — distingue deux catégories de "
        f"problèmes : ceux que tu peux corriger toi-même par une simple "
        f"réécriture mécanique (formatage, cohérence YAML) — corrige-les "
        f"directement dans `manifest_yaml` comme avant. Et ceux qui "
        f"relèvent d'un manque de fond que TOI tu ne dois PAS corriger "
        f"silencieusement — une absence de `securityContext`, un "
        f"conteneur privilégié, un champ obligatoire structurellement "
        f"absent, une incohérence de schéma que tu ne peux pas résoudre "
        f"sans réinventer un choix qui appartient à l'Agent 2 — pour "
        f"CEUX-LÀ, ajoute une entrée dans `validation_errors` "
        f"(`rule` en kebab-case façon kube-linter, `message` précis, "
        f"`resource` au format 'Kind/name') PLUTÔT que de les corriger "
        f"toi-même ou de te contenter d'un `warnings`. Sois sélectif : "
        f"`validation_errors` déclenche un aller-retour coûteux vers le "
        f"Générateur, borné à {settings.MAX_ITERATIONS} tentatives -- réserve-le "
        f"aux problèmes réels de schéma/sécurité, pas à des préférences "
        f"cosmétiques.\n\n"
        f"⚠️ AVANT de flaguer une `validation_error` concernant une posture "
        f"de sécurité (privileged, root, filesystem inscriptible, "
        f"capability ajoutée...), VÉRIFIE D'ABORD le champ "
        f"`security_requirements` du composant concerné dans la "
        f"NormalizedSpec ci-dessus. Si cette posture y est EXPLICITEMENT "
        f"demandée (l'utilisateur l'a sciemment voulue, avec une raison "
        f"donnée), ce n'est PAS un gap de sécurité à corriger — c'est un "
        f"choix assumé de la spec. Ne le flague pas en `validation_error` "
        f"dans ce cas (tu peux à la rigueur le noter en `warnings` pour "
        f"que ce soit visible dans l'audit, sans déclencher de "
        f"correction). Un problème réel de sécurité NON PRÉCISÉMENT "
        f"demandé par `security_requirements` reste un `validation_error` "
        f"normal."
    )
    raw = call_llm(SYSTEM, prompt, agent_name="Agent 3 - Validation")
    result = extract_json(raw)

    corrected_core = result.get("manifest_yaml", manifest_core)

    # Filet de sécurité déterministe : retire tout conteneur manuel
    # dupliqué pour un sidecar en mode "annotations", que le LLM ait
    # respecté la consigne ou non (voir _strip_duplicate_auto_inject_containers).
    corrected_core, dedup_notes = _strip_duplicate_auto_inject_containers(
        corrected_core, state.sidecar_injection_mode
    )
    for note in dedup_notes:
        log_warning("Agent 3 - Validation", note)

    # Erreurs déterministes (zéro coût LLM) + erreurs signalées par le LLM,
    # avec attribution de ligne calculée par code (plus fiable que de
    # demander au LLM de compter des lignes lui-même).
    deterministic_errors = _deterministic_validation_errors(corrected_core)
    llm_errors = []
    for item in result.get("validation_errors", []):
        resource = item.get("resource")
        llm_errors.append(ValidationError(
            line=_approximate_line(corrected_core, resource),
            rule=item.get("rule", "unspecified"),
            message=item.get("message", ""),
            resource=resource,
        ))

    # Filet déterministe : même si le LLM a ignoré l'instruction, on
    # retire ici toute validation_error qui contredit une posture de
    # sécurité EXPLICITEMENT demandée par la spec pour ce composant.
    security_requirements_by_component = {
        c.component_name: c.security_requirements for c in spec.components
    }
    suppressed = [e for e in llm_errors if _explicitly_requested(e, security_requirements_by_component)]
    if suppressed:
        llm_errors = [e for e in llm_errors if e not in suppressed]
        log_warning(
            "Agent 3 - Validation",
            f"{len(suppressed)} validation_error(s) supprimée(s) car elles "
            f"contredisent une exigence de sécurité explicitement demandée "
            f"par la spec (pas un gap, un choix assumé) : "
            f"{[(e.rule, e.resource) for e in suppressed]}",
        )

    state.validation_errors = deterministic_errors + llm_errors
    state.current_yaml = corrected_core  # toujours à jour, que la boucle continue ou pas

    # `manifest_v2_yaml` reflète TOUJOURS le meilleur instantané courant
    # après ce passage d'Agent 3 -- que la boucle continue ou non. Séparé
    # de la décision de boucler (qui dépend uniquement de
    # `validation_errors`/`iteration_count`, évaluée par le routage du
    # graphe) : du code qui appelle `run_agent3` en dehors du graphe
    # complet (tests, scripts) continue de trouver un manifeste exploitable
    # après un seul appel, comme avant l'introduction de ce mécanisme.
    state.manifest_v2_yaml = (
        f"{corrected_core}\n---\n{unmapped_block}" if unmapped_block else corrected_core
    )
    # Si validation_errors est non vide, on NE finalise PAS manifest_v2_yaml
    # ici -- c'est le rôle du routage conditionnel (graph.py) de décider
    # s'il reste des tentatives (-> agent2_fix) ou si la borne est atteinte
    # (-> finalisation quand même, gérée dans _route_after_agent3 pour ne
    # jamais bloquer le pipeline sur une boucle épuisée).

    for w in result.get("warnings", []):
        log_warning("Agent 3 - Validation", w)
    if llm_errors:
        log_warning(
            "Agent 3 - Validation",
            f"{len(llm_errors)} problème(s) de schéma/sécurité signalé(s) "
            f"pour correction par le Générateur : "
            f"{[e.rule for e in llm_errors]}",
        )

    state.reports.append(AgentReport(
        agent_name=f"Agent 3 - Validation (itération {state.iteration_count})",
        fields_addressed=result.get("fields_addressed", []),
        fields_left_open=result.get("fields_left_open", []),
        actions=(
            result.get("checks_passed", [])
            + [f"Corrigé: {c}" for c in result.get("checks_failed_and_fixed", [])]
            + [f"Corrigé (déterministe): {n}" for n in dedup_notes]
        ),
        warnings=result.get("warnings", []) + [
            f"validation_errors: [{e.rule}] {e.message} ({e.resource})"
            for e in state.validation_errors
        ] + [
            f"validation_error supprimée (exigence explicite de la spec, pas un gap) : "
            f"[{e.rule}] {e.message} ({e.resource})"
            for e in suppressed
        ],
    ))
    return state
