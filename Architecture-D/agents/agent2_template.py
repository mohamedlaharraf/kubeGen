"""
agents/agent2_template.py — Agent 2 : génération du manifeste structurel de
base, UN COMPOSANT À LA FOIS.

Pour une architecture "microservices" à N composants, on appelle le LLM N
fois séparément (une fois par `ServiceComponent`), chacune isolée aux
champs de CE composant uniquement — cohérent avec le principe de "contexte
isolé par étape" : le fait qu'il y ait plusieurs composants ne change rien
au rôle de l'Agent 2, il génère toujours "le template d'un composant",
juste plusieurs fois. Les YAML de chaque composant sont concaténés en un
seul manifeste multi-documents.

Le `Namespace` lui-même est généré de façon DÉTERMINISTE en Python (pas via
le LLM) : c'est un document trivial et partagé entre tous les composants,
donc autant éviter tout risque d'incohérence ou de duplication en le
générant une seule fois ici plutôt que N fois par le LLM.
"""

from __future__ import annotations

from pathlib import Path

from llm_client import call_llm, extract_json
from schemas import AgentReport, PipelineState
from utils.logging_utils import log_step, log_warning
from utils.admission_policies import generate_admission_policy_skeletons
from utils.multi_cluster import generate_applicationset_skeleton
from utils.yaml_utils import load_all_documents
from utils.global_constraints import filter_constraints, constraints_block
from utils.sidecar_injection import build_injection_mode_map, ANNOTATIONS
from config import settings

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SYSTEM = (PROMPTS_DIR / "agent2_system.txt").read_text(encoding="utf-8")
FIX_SYSTEM = (PROMPTS_DIR / "agent2_fix_system.txt").read_text(encoding="utf-8")


def run_generator_fix(state: PipelineState) -> PipelineState:
    """
    Noeud dédié à la boucle Generator <-> Validator (Architecture C,
    mécanisme #2 -- distinct de la boucle de réparation post-Agent 5).

    Appelé quand Agent 3 a détecté des `validation_errors` non vides et
    que la borne `MAX_ITERATIONS` n'est pas encore atteinte (routage
    décidé dans graph.py::_route_after_agent3). Corrige le manifeste
    COMPLET en une passe (pas un patch par ressource comme
    `agents/agent_repair.py` -- ici les erreurs peuvent toucher
    simultanément plusieurs documents liés, ex: Deployment + sa
    NetworkPolicy, donc une correction cohérente doit voir l'ensemble),
    puis incrémente `state.iteration_count` et renvoie vers Agent 3 pour
    revalidation (arête de graphe, pas géré dans cette fonction).
    """
    if not state.validation_errors or not state.current_yaml:
        return state

    log_step(
        "Agent 2 - Correction sur retour",
        f"{len(state.validation_errors)} erreur(s) à corriger "
        f"(itération {state.iteration_count + 1}/{settings.MAX_ITERATIONS})...",
    )

    errors_payload = [e.model_dump() for e in state.validation_errors]
    prompt = (
        f"Manifeste actuel :\n{state.current_yaml}\n\n"
        f"Erreurs signalées par le Validateur :\n{errors_payload}"
    )
    raw = call_llm(FIX_SYSTEM, prompt, agent_name="Agent 2 - Correction sur retour")
    result = extract_json(raw)

    state.current_yaml = result.get("manifest_yaml", state.current_yaml)
    state.iteration_count += 1

    state.reports.append(AgentReport(
        agent_name=f"Agent 2 - Correction sur retour (itération {state.iteration_count})",
        actions=result.get("fixes_applied", []),
        warnings=result.get("notes", []),
    ))
    return state


def _namespace_yaml(namespace: str) -> str:
    return (
        f"apiVersion: v1\n"
        f"kind: Namespace\n"
        f"metadata:\n"
        f"  name: {namespace}\n"
    )


def _quarantine_if_invalid(unmapped_yaml: str) -> tuple[str, bool]:
    """
    Le fragment best-effort n'a par nature AUCUNE garantie de bien former
    du YAML valide (contrairement au reste du pipeline, dont la structure
    est contrainte). Si un fragment invalide était concaténé tel quel au
    manifeste, `load_all_documents` planterait en aval (Agent 4, Agent 5)
    et ferait échouer TOUT le pipeline — y compris la partie connue et
    parfaitement correcte. Inacceptable : une génération "best-effort" ne
    doit jamais pouvoir couler le reste.

    Donc : on valide le fragment ICI. S'il est invalide, on le transforme
    en un simple commentaire YAML (syntaxiquement inerte, donc ignoré par
    tout parseur en aval) — le contenu original reste lisible pour revue
    humaine, mais ne peut plus rien casser.

    Renvoie (contenu_final, était_valide).
    """
    if not unmapped_yaml.strip():
        return "", True

    try:
        load_all_documents(unmapped_yaml)
        return unmapped_yaml, True
    except ValueError:
        commented = "\n".join(f"# {line}" for line in unmapped_yaml.splitlines())
        wrapped = (
            "# ⚠️ GÉNÉRATION LIBRE INVALIDE — le YAML produit par le modèle "
            "n'a pas pu être parsé et a été mis en quarantaine (commenté) pour "
            "ne pas faire échouer le reste du pipeline. Contenu original "
            "ci-dessous, à corriger manuellement si utile :\n"
            f"{commented}\n"
        )
        return wrapped, False


def _generate_unmapped_fragments(unmapped: list, global_constraints: list) -> str:
    """
    Chemin de génération BEST-EFFORT, séparé du chemin structuré
    `_generate_component` (qui ne change jamais, ne serait-ce que d'une
    ligne, à cause de cette fonction). Appelée UNE SEULE FOIS pour toute
    la liste `unmapped_requirements` de la spec entière — pas par
    composant, puisque ces exigences n'ont par définition pas été
    rattachées à un composant précis par l'Agent 1.

    Pas de `extract_json` ici : contrairement au reste du pipeline, la
    structure de la réponse n'est PAS prévisible (un `PostgresCluster`,
    un CRD maison... n'ont aucun schéma commun à imposer). On récupère
    du YAML brut, clairement étiqueté comme non vérifié à chaque fragment.

    `global_constraints` : c'est PRÉCISÉMENT ce paramètre qui corrige le
    bug PCI-DSS/PostgresCluster observé en production (Architecture B) —
    avant, ce chemin de génération n'avait aucun moyen de savoir qu'une
    contrainte "chiffrement au repos pour tous les volumes" existait,
    parce qu'elle était rattachée aux security_requirements d'un AUTRE
    composant. Ici, `global_constraints` vit au niveau de la spec entière,
    donc accessible même à une ressource qui n'a pas de composant nommé.
    """
    if not unmapped:
        return ""

    texts = "\n".join(
        f"- {r.text}" + (f" (kind supposé : {r.suggested_kind})" if r.suggested_kind else "")
        for r in unmapped
    )
    prompt = (
        "Exigences non standard, hors du schéma structuré habituel de ce "
        "pipeline :\n"
        f"{texts}\n\n"
        "Génère un fragment YAML Kubernetes best-effort pour CHACUNE, en te "
        "basant sur ta connaissance générale de Kubernetes et de ses CRD "
        "courantes (opérateurs communautaires, etc.). Précède CHAQUE "
        "fragment d'un commentaire exact :\n"
        "# ⚠️ GÉNÉRATION LIBRE — non vérifiée par les contrôles habituels du "
        "pipeline, à valider manuellement avant tout déploiement.\n\n"
        "Sépare chaque document par '---'. Si tu n'as vraiment aucune base "
        "pour générer un fragment plausible pour une exigence donnée, "
        "n'invente rien : ajoute simplement un commentaire "
        "'# Impossible de générer un fragment plausible pour : <exigence>' "
        "à la place. Réponds UNIQUEMENT avec le YAML (+ commentaires), rien "
        "d'autre autour."
    )
    prompt += constraints_block(filter_constraints(None, global_constraints))
    return call_llm(SYSTEM, prompt, agent_name="Agent 2 - Template (best-effort)")


def _generate_component(namespace: str, component, global_constraints: list,
                         injection_map: dict[str, dict]) -> dict:
    relevant = component.model_dump(
        include={
            "component_name", "workload_type", "image", "replicas", "labels",
            "ports", "env_vars", "volumes", "sidecars",
            "security_requirements", "observability_requirements",
            "ingress", "rbac", "service_mesh_routing",
            "observability_style", "cron_schedule",
            "config_maps", "network_policy", "deployment_strategy",
            "depends_on",
        }
    )
    relevant["namespace"] = namespace  # partagé au niveau de la spec, pas du composant
    if injection_map:
        # Décision DÉJÀ PRISE en Python déterministe (voir
        # utils/sidecar_injection.py) : l'Agent 2 ne doit plus décider
        # lui-même quels sidecars sont à injection automatique, il
        # applique ce mapping tel quel. C'est la même source de vérité
        # que celle relue par l'Agent 3 et l'Agent 5 en aval, ce qui
        # évite qu'un agent en aval "corrige" un choix qu'il n'a pas vu.
        # Placé DANS `relevant` (pas en texte libre après) pour rester un
        # seul bloc structuré, cohérent avec le reste du prompt.
        relevant["sidecar_injection_mode"] = injection_map

    # Le rappel des règles à appliquer selon `sidecar_injection_mode` vit
    # dans le prompt SYSTÈME (agent2_system.txt), pas ici : on garde le
    # prompt utilisateur limité au dict `relevant` (+ le bloc de
    # contraintes déjà existant) pour rester un seul bloc structuré facile
    # à extraire/parser en aval (traçabilité, tests).
    prompt = f"ServiceComponent (un seul composant, champs pertinents) :\n{relevant}"
    prompt += constraints_block(filter_constraints(component.component_name, global_constraints))
    raw = call_llm(SYSTEM, prompt, agent_name="Agent 2 - Template")
    return extract_json(raw)


def run_agent2(state: PipelineState) -> PipelineState:
    if state.spec is None or not state.spec.components:
        state.error = "Agent 2 : aucun composant disponible dans la NormalizedSpec (Agent 1 a échoué)."
        return state

    spec = state.spec
    log_step(
        "Agent 2 - Template",
        f"Génération du manifeste K8s pour {len(spec.components)} composant(s) "
        f"({spec.architecture_type})...",
    )

    manifest_parts: list[str] = []
    fields_addressed: list[str] = []
    fields_left_open: list[str] = []
    actions: list[str] = ["Génération du manifeste structurel de base (sans énergie)",
                           "Hardening de sécurité (securityContext, NetworkPolicy si pertinent)",
                           "Configuration observabilité (annotations Prometheus si pertinent)",
                           "ServiceAccount dédié par composant, RBAC/Ingress/PVC si demandés"]
    warnings: list[str] = []

    if spec.namespace and spec.namespace != "default":
        manifest_parts.append(_namespace_yaml(spec.namespace))
        actions.append(f"Namespace '{spec.namespace}' généré (une seule fois, déterministe)")
        fields_addressed.append("namespace")

    if spec.admission_policies:
        policy_result = generate_admission_policy_skeletons(spec.admission_policies)
        if policy_result["manifest_yaml"]:
            manifest_parts.append(policy_result["manifest_yaml"])
        actions.append(
            f"Policies d'admission (Kyverno, mode Audit) : "
            f"{len(policy_result['addressed'])} générée(s) déterministiquement "
            f"(pattern matching, pas de LLM sur ce domaine sensible)"
        )
        fields_addressed += [f"admission_policies: {a}" for a in policy_result["addressed"]]
        fields_left_open += [f"admission_policies: {o}" for o in policy_result["left_open"]]
        for o in policy_result["left_open"]:
            log_warning("Agent 2 - Template", o)

    if spec.target_clusters:
        # Génération DÉTERMINISTE (pas de LLM) : un squelette ArgoCD
        # ApplicationSet avec placeholders explicites. Le pipeline ne
        # connaît ni les adresses API réelles des clusters cibles ni l'URL
        # du dépôt GitOps de l'utilisateur — halluciner ces informations
        # via un LLM serait pire que de générer un squelette honnête à
        # compléter. Un squelette par composant serait redondant (même
        # topologie de clusters pour toute l'app) : un seul ApplicationSet
        # au niveau de la spec entière.
        app_name = spec.components[0].component_name if spec.components else "app"
        appset_yaml = generate_applicationset_skeleton(app_name, spec.target_clusters, spec.namespace)
        manifest_parts.append(appset_yaml)
        msg = (
            f"target_clusters={spec.target_clusters} détecté(s) : squelette ArgoCD "
            f"ApplicationSet généré (placeholders URL de cluster + dépôt Git à "
            f"compléter avant tout déploiement réel). Nécessite ArgoCD installé."
        )
        warnings.append(msg)
        log_warning("Agent 2 - Template", msg)
        actions.append(f"ApplicationSet multi-cluster généré déterministiquement pour {spec.target_clusters}")
        fields_addressed.append(f"target_clusters: {spec.target_clusters} -> ApplicationSet")
        fields_left_open.append(
            "target_clusters: placeholders URL cluster + dépôt Git à renseigner manuellement"
        )

    for component in spec.components:
        injection_map = build_injection_mode_map(component.sidecars, component.component_name)
        if injection_map:
            state.sidecar_injection_mode[component.component_name] = injection_map

        result = _generate_component(spec.namespace, component, spec.global_constraints, injection_map)
        prefix = f"[{component.component_name}] "

        applied = filter_constraints(component.component_name, spec.global_constraints)
        if applied:
            actions.append(
                f"{prefix}{len(applied)} contrainte(s) globale(s) du blackboard "
                f"appliquée(s) : {[c.text for c in applied]}"
            )
            fields_addressed += [f"{prefix}global_constraints: {c.text}" for c in applied]

        yaml_chunk = result.get("manifest_yaml", "")
        if yaml_chunk:
            manifest_parts.append(yaml_chunk)

        for w in result.get("warnings", []):
            log_warning("Agent 2 - Template", prefix + w)
            warnings.append(prefix + w)

        sec_open = result.get("security_requirements_left_open", [])
        obs_open = result.get("observability_requirements_left_open", [])
        ingress_open = result.get("ingress_left_open", [])
        rbac_open = result.get("rbac_left_open", [])

        for label, open_list in (
            ("Sécurité", sec_open), ("Observabilité", obs_open),
            ("Ingress", ingress_open), ("RBAC", rbac_open),
        ):
            if open_list:
                log_warning("Agent 2 - Template", f"{prefix}{label} non implémenté(e) : {open_list}")

        if component.sidecars:
            manual = [s.name for s in component.sidecars
                      if injection_map.get(s.name, {}).get("mode") != ANNOTATIONS]
            auto = [s.name for s in component.sidecars
                    if injection_map.get(s.name, {}).get("mode") == ANNOTATIONS]
            if manual:
                actions.append(
                    f"{prefix}{len(manual)} sidecar(s) empaqueté(s) comme conteneur(s) "
                    f"dans le même Pod : {manual}"
                )
            for sc_name in auto:
                cfg = injection_map[sc_name]
                actions.append(
                    f"{prefix}Sidecar '{sc_name}' reconnu comme injection automatique "
                    f"(pattern déterministe, voir utils/sidecar_injection.py) : "
                    f"annotations {list(cfg['annotations'].keys())} générées à la place "
                    f"d'un conteneur manuel."
                )
                msg = (
                    f"{prefix}Sidecar '{sc_name}' en mode annotations : nécessite "
                    f"{cfg['requires_operator']} installé dans le cluster cible."
                )
                warnings.append(msg)
                log_warning("Agent 2 - Template", msg)
        if component.ingress and component.ingress.enabled:
            if component.ingress.api_style == "gateway_api":
                actions.append(
                    f"{prefix}HTTPRoute généré (Gateway API) rattaché à "
                    f"'{component.ingress.gateway_name or 'Gateway placeholder à créer'}'"
                )
            else:
                actions.append(f"{prefix}Ingress généré (host={component.ingress.host or 'placeholder'})")
            if component.ingress.cert_manager_issuer:
                actions.append(
                    f"{prefix}Certificate cert-manager généré (issuer="
                    f"{component.ingress.cert_manager_issuer})"
                )
        if component.rbac.enabled and component.rbac.rules_description:
            actions.append(f"{prefix}RBAC : Role/RoleBinding pour {component.rbac.rules_description}")
        if any(v.kind == "pvc" for v in component.volumes):
            if component.workload_type == "StatefulSet":
                actions.append(
                    f"{prefix}spec.volumeClaimTemplates généré (un volume PAR RÉPLICA, "
                    f"pattern StatefulSet natif — pas un PVC externe partagé)"
                )
            else:
                actions.append(f"{prefix}PersistentVolumeClaim externe généré pour le stockage persistant demandé")
        if component.workload_type == "CronJob":
            actions.append(f"{prefix}CronJob.spec.schedule = '{component.cron_schedule}'")

        fields_addressed += [prefix + f for f in result.get("fields_addressed", [])]
        for key, out_key in (
            ("security_requirements_addressed", "security_requirements"),
            ("observability_requirements_addressed", "observability_requirements"),
            ("ingress_addressed", "ingress"),
            ("rbac_addressed", "rbac"),
        ):
            fields_addressed += [f"{prefix}{out_key}: {v}" for v in result.get(key, [])]

        fields_left_open += [prefix + f for f in result.get("fields_left_open", [])]
        fields_left_open += [prefix + f for f in sec_open]
        fields_left_open += [prefix + f for f in obs_open]
        fields_left_open += [prefix + f for f in ingress_open]
        fields_left_open += [prefix + f for f in rbac_open]

    if spec.unmapped_requirements:
        raw_unmapped_yaml = _generate_unmapped_fragments(spec.unmapped_requirements, spec.global_constraints)
        unmapped_yaml, was_valid = _quarantine_if_invalid(raw_unmapped_yaml)
        applied = filter_constraints(None, spec.global_constraints)
        if applied:
            actions.append(
                f"Génération best-effort : {len(applied)} contrainte(s) globale(s) "
                f"du blackboard transmise(s) (ex: chiffrement au repos sur tous "
                f"les volumes) : {[c.text for c in applied]}"
            )
        if unmapped_yaml:
            manifest_parts.append(unmapped_yaml)
        actions.append(
            f"Génération BEST-EFFORT (non vérifiée) pour "
            f"{len(spec.unmapped_requirements)} exigence(s) hors du schéma "
            f"structuré : {[r.text for r in spec.unmapped_requirements]}"
            + ("" if was_valid else " — YAML invalide, mis en quarantaine (commenté)")
        )
        fields_left_open.append(
            f"unmapped_requirements: {len(spec.unmapped_requirements)} fragment(s) "
            f"généré(s) en best-effort, non vérifié(s) par les contrôles habituels "
            f"(pas de cross-référence, pas de connaissance du schéma OpenAPI de ce "
            f"kind) — à valider manuellement avant tout déploiement."
        )
        if not was_valid:
            msg = (
                "Le fragment best-effort généré n'était pas du YAML valide : mis "
                "en quarantaine (commenté) pour ne pas faire échouer le reste du "
                "pipeline. Contenu original visible dans le manifeste, à corriger "
                "manuellement."
            )
            warnings.append(msg)
            log_warning("Agent 2 - Template", msg)
        log_warning(
            "Agent 2 - Template",
            f"{len(spec.unmapped_requirements)} exigence(s) hors schéma générée(s) "
            f"en best-effort, non vérifiée(s) — voir manifeste final."
        )

    state.manifest_v1_yaml = "\n---\n".join(manifest_parts)
    # Initialise le blackboard de la boucle Generator<->Validator : Agent 3
    # lira/mettra à jour `current_yaml`, pas manifest_v1_yaml (qui reste la
    # trace figée de la toute première génération, pour l'audit).
    state.current_yaml = state.manifest_v1_yaml

    state.reports.append(AgentReport(
        agent_name="Agent 2 - Template",
        fields_addressed=fields_addressed,
        fields_left_open=fields_left_open,
        actions=actions,
        warnings=warnings,
    ))
    return state
