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

Même principe pour `unmapped_requirements` (génération best-effort, cf.
`_generate_unmapped_fragments`) : un appel LLM PAR exigence, pas un appel
groupé pour toute la liste. Ça évite qu'une réponse volumineuse couvrant
plusieurs exigences dépasse `LLM_MAX_OUTPUT_TOKENS` et soit tronquée avant
la fin (ce qui, avec un appel groupé, fait échouer TOUT le bloc — y compris
les exigences qui auraient été correctement traitées) ; et ça permet de
mettre en quarantaine chaque fragment invalide individuellement plutôt que
tout le bloc.

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

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SYSTEM = (PROMPTS_DIR / "agent2_system.txt").read_text(encoding="utf-8")


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


def _generate_unmapped_fragment_one(requirement) -> str:
    """
    Génère le fragment best-effort pour UNE SEULE exigence non mappée
    (un seul appel LLM, un seul budget `LLM_MAX_OUTPUT_TOKENS`). Voir
    `_generate_unmapped_fragments` pour pourquoi c'est fait exigence par
    exigence plutôt qu'en un appel groupé.

    Pas de `extract_json` ici : contrairement au reste du pipeline, la
    structure de la réponse n'est PAS prévisible (un `PostgresCluster`,
    un CRD maison... n'ont aucun schéma commun à imposer). On récupère
    du YAML brut, clairement étiqueté comme non vérifié.
    """
    text = f"- {requirement.text}" + (
        f" (kind supposé : {requirement.suggested_kind})" if requirement.suggested_kind else ""
    )
    prompt = (
        "Exigences non standard, hors du schéma structuré habituel de ce "
        "pipeline (une seule exigence ci-dessous) :\n"
        f"{text}\n\n"
        "Commence par déterminer si cette exigence correspond à une VRAIE "
        "ressource Kubernetes/CRD existante et identifiable (ex: un CRD "
        "d'un opérateur communautaire réel et reconnu comme CrunchyData "
        "PostgresCluster, ECK Elasticsearch, cert-manager Certificate...) :\n"
        "- SI OUI : génère un fragment YAML best-effort pour cette "
        "ressource, en te basant sur ta connaissance de son schéma réel. "
        "Précède le fragment d'un commentaire exact :\n"
        "  # ⚠️ GÉNÉRATION LIBRE — non vérifiée par les contrôles "
        "habituels du pipeline, à valider manuellement avant tout "
        "déploiement.\n"
        "- SI NON (l'exigence n'est pas une ressource Kubernetes du tout — "
        "ex: un langage de programmation, une convention d'équipe, une "
        "politique organisationnelle, une exigence opérationnelle comme "
        "une rotation de clés) : N'INVENTE JAMAIS un `apiVersion`/`kind` "
        "de toutes pièces pour la faire ressembler à une ressource "
        "Kubernetes — un faux CRD est trompeur (il donne l'illusion d'une "
        "ressource déployable qui n'existe dans aucun cluster réel) et "
        "plus dangereux qu'une absence de fragment. Dans ce cas, "
        "documente-la SEULEMENT via un commentaire :\n"
        "  # ℹ️ Exigence hors périmètre Kubernetes (aucune ressource K8s "
        "correspondante) : <exigence> — à tracer par un autre moyen "
        "(documentation, label, process d'équipe).\n"
        "Si tu n'as vraiment aucune base pour déterminer avec confiance de "
        "quel CRD réel il s'agit, n'invente rien non plus : utilise le "
        "commentaire '# Impossible de générer un fragment plausible pour : "
        "<exigence> (CRD réel inconnu)' à la place. Réponds UNIQUEMENT "
        "avec le YAML (+ commentaires) pour CETTE exigence, rien d'autre "
        "autour."
    )
    return call_llm(SYSTEM, prompt, agent_name="Agent 2 - Template (best-effort)")


def _generate_unmapped_fragments(unmapped: list) -> list[str]:
    """
    Chemin de génération BEST-EFFORT, séparé du chemin structuré
    `_generate_component` (qui ne change jamais, ne serait-ce que d'une
    ligne, à cause de cette fonction).

    Un appel LLM PAR exigence (pas un appel groupé pour toute la liste,
    comme précédemment) : avec un appel groupé, une réponse volumineuse
    couvrant plusieurs exigences pouvait dépasser `LLM_MAX_OUTPUT_TOKENS`
    et être tronquée avant la fin — ce qui faisait échouer (mise en
    quarantaine) TOUT le bloc, y compris les exigences qui, seules,
    auraient été correctement traitées. Ici, chaque exigence a son propre
    budget de tokens et son propre sort en cas d'échec (voir
    `run_agent2`, qui met chaque fragment en quarantaine individuellement).

    Renvoie une liste de fragments YAML bruts (même longueur que
    `unmapped`, un fragment par exigence, dans le même ordre).
    """
    return [_generate_unmapped_fragment_one(r) for r in unmapped]


def _generate_component(namespace: str, component) -> dict:
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

    prompt = f"ServiceComponent (un seul composant, champs pertinents) :\n{relevant}"
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
        result = _generate_component(spec.namespace, component)
        prefix = f"[{component.component_name}] "

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
            actions.append(
                f"{prefix}{len(component.sidecars)} sidecar(s) empaqueté(s) dans le "
                f"même Pod : {[s.purpose for s in component.sidecars]}"
            )
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
        raw_fragments = _generate_unmapped_fragments(spec.unmapped_requirements)

        unmapped_parts: list[str] = []
        quarantined_texts: list[str] = []
        for requirement, raw_fragment in zip(spec.unmapped_requirements, raw_fragments):
            fragment_yaml, was_valid = _quarantine_if_invalid(raw_fragment)
            if fragment_yaml:
                unmapped_parts.append(fragment_yaml)
            if not was_valid:
                quarantined_texts.append(requirement.text)
                msg = (
                    f"Fragment best-effort pour '{requirement.text}' invalide "
                    "(pas du YAML valide) : mis en quarantaine (commenté) pour "
                    "ne pas faire échouer le reste du pipeline. Contenu "
                    "original visible dans le manifeste, à corriger manuellement."
                )
                warnings.append(msg)
                log_warning("Agent 2 - Template", msg)

        if unmapped_parts:
            manifest_parts.append("\n---\n".join(unmapped_parts))

        actions.append(
            f"Génération BEST-EFFORT (non vérifiée, un appel LLM par exigence) "
            f"pour {len(spec.unmapped_requirements)} exigence(s) hors du schéma "
            f"structuré : {[r.text for r in spec.unmapped_requirements]}"
            + (f" — {len(quarantined_texts)} fragment(s) invalide(s) mis en "
               f"quarantaine : {quarantined_texts}" if quarantined_texts else "")
        )
        fields_left_open.append(
            f"unmapped_requirements: {len(spec.unmapped_requirements)} fragment(s) "
            f"généré(s) en best-effort, non vérifié(s) par les contrôles habituels "
            f"(pas de cross-référence, pas de connaissance du schéma OpenAPI de ce "
            f"kind) — à valider manuellement avant tout déploiement."
        )
        log_warning(
            "Agent 2 - Template",
            f"{len(spec.unmapped_requirements)} exigence(s) hors schéma générée(s) "
            f"en best-effort, non vérifiée(s) — voir manifeste final."
        )

    state.manifest_v1_yaml = "\n---\n".join(manifest_parts)

    state.reports.append(AgentReport(
        agent_name="Agent 2 - Template",
        fields_addressed=fields_addressed,
        fields_left_open=fields_left_open,
        actions=actions,
        warnings=warnings,
    ))
    return state
