"""
agents/agent1_analyse.py

Agent 1 — ANALYSE.

C'est ici que se joue la réponse à votre question : comment s'assurer
que l'agent qui voit la demande brute la comprend bien et la traduit
fidèlement pour le reste du pipeline ?

Réponse implémentée : une boucle interne en 3 temps, EXÉCUTÉE ENTIÈREMENT
DANS CE NOEUD (donc sans violer la règle "pas de retour en arrière" du
graphe) :

    1) EXTRACTION : le LLM extrait une NormalizedSpec depuis le texte brut.
    2) SELF-CHECK  : le LLM relit le texte brut + son propre JSON et liste
                      les "gaps" (exigences non couvertes).
    3) RÉPARATION  : si des gaps existent, le LLM corrige son JSON pour les
                      intégrer. On répète jusqu'à AGENT1_MAX_REPAIR_ATTEMPTS
                      fois ou jusqu'à ce qu'il n'y ait plus de gap.

Le résultat (`coverage`) est conservé dans la NormalizedSpec et sera
consultable par l'Agent 5 dans son audit final.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from config import settings
from llm_client import call_llm, extract_json
from schemas import NormalizedSpec, CoverageCheck, AgentReport, PipelineState
from utils.logging_utils import log_step, log_warning

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

SYSTEM_EXTRACT = (PROMPTS_DIR / "agent1_system.txt").read_text(encoding="utf-8")
SYSTEM_SELFCHECK = (PROMPTS_DIR / "agent1_selfcheck_system.txt").read_text(encoding="utf-8")
SYSTEM_REPAIR = (PROMPTS_DIR / "agent1_repair_system.txt").read_text(encoding="utf-8")
SYSTEM_SCHEMA_REPAIR = (PROMPTS_DIR / "agent1_schema_repair_system.txt").read_text(encoding="utf-8")

SCHEMA_HINT = """
Schéma NormalizedSpec attendu (JSON) :
{
  "architecture_type": "single"|"microservices",
  "namespace": str,
  "components": [
    {
      "component_name": str,
      "workload_type": "Deployment"|"StatefulSet"|"DaemonSet"|"Job"|"CronJob",
      "image": str,
      "replicas": int,
      "labels": {str: str},
      "ports": [{"name": str, "container_port": int, "protocol": "TCP"|"UDP", "expose_service": bool}],
      "env_vars": [{"name": str, "value": str|null, "from_secret": str|null, "from_configmap": str|null, "secret_key": str|null, "configmap_key": str|null}],
      "volumes": [{"name": str, "mount_path": str, "kind": "emptyDir"|"configMap"|"secret"|"pvc", "source_name": str|null, "size": str|null, "storage_class_name": str|null}],
      "sidecars": [{"name": str, "image": str, "purpose": str, "ports": [...même forme que ports ci-dessus...], "env_vars": [...même forme...], "resource_hints": str|null}],
      "depends_on": [str, ...autres component_name dont celui-ci dépend...],
      "energy_goals": [str],
      "resource_hints": str|null,
      "traffic_windows": [{"start_time": "HH:MM", "end_time": "HH:MM", "level": "low"|"high"|"normal", "timezone": str|null, "target_replicas_hint": int|null}],
      "constraints": [str],
      "security_requirements": [str],
      "observability_requirements": [str],
      "ingress": {"enabled": bool, "host": str|null, "path": str, "tls": bool, "tls_secret_name": str|null, "ingress_class": str|null, "api_style": "ingress"|"gateway_api", "gateway_name": str|null, "cert_manager_issuer": str|null, "cert_manager_issuer_kind": "Issuer"|"ClusterIssuer"} | null,
      "rbac": {"enabled": bool, "rules_description": [str]},
      "service_mesh_routing": [str],
      "observability_style": "annotations"|"service_monitor"|"both",
      "cron_schedule": str|null,
      "config_maps": [{"name": str, "data": {str: str}}],
      "network_policy": {"restrict_egress": bool, "allowed_egress_targets": [str], "allowed_ingress_sources": [str]} | null,
      "deployment_strategy": {"strategy": "canary"|"blue_green", "steps_description": [str]} | null
    }
  ],
  "admission_policies": [str],
  "target_clusters": [str],
  "unmapped_requirements": [{"text": str, "suggested_kind": str|null}],
  "raw_user_request": str,
  "ambiguities": [{"field": str, "question": str, "assumption_made": str, "confidence": "low"|"medium"|"high"}],
  "coverage": {
     "requirements_detected": [str],
     "requirements_mapped": [str],
     "requirements_unmapped": [str],
     "repair_attempts": int,
     "self_check_passed": bool
  }
}

NE PAS CONFONDRE `unmapped_requirements` ET `coverage.requirements_unmapped` :
`coverage.requirements_unmapped` est un indicateur interne de ta propre
auto-vérification (utilisé par la boucle self-check/réparation, voir plus
bas) — de simples chaînes de texte. `unmapped_requirements` (structuré,
`text` + `suggested_kind`) est le résultat FINAL destiné à la génération
best-effort de l'Agent 2 et à l'audit. Une exigence qui reste dans
`coverage.requirements_unmapped` après la boucle de réparation DOIT aussi
apparaître dans `unmapped_requirements` — les deux se recoupent, mais
`unmapped_requirements` est ce qui compte pour la suite du pipeline.

RÈGLES POUR `architecture_type` ET `components` :
- `architecture_type: "single"` + UN SEUL élément dans `components` : cas
  par défaut, largement le plus fréquent (une seule application à déployer).
- `architecture_type: "microservices"` UNIQUEMENT si l'utilisateur décrit
  EXPLICITEMENT plusieurs services distincts qui interagissent (ex: "un
  service API, un service de paiement, et un worker asynchrone qui
  communiquent entre eux"). Dans ce cas, `components` contient UN élément
  PAR service décrit, et `depends_on` capture qui appelle qui si mentionné.
  Ne découpe JAMAIS artificiellement une appli unique en plusieurs
  composants si l'utilisateur n'a décrit qu'un seul service.
- `sidecars` sur un `component` UNIQUEMENT si l'utilisateur demande
  explicitement un conteneur additionnel dans le même Pod (proxy, agent de
  logs, exportateur de métriques dédié...). N'invente jamais un sidecar par
  défaut. Si l'utilisateur ne précise pas d'image exacte pour un besoin de
  sidecar connu, choisis une image standard reconnue du domaine et
  documente ce choix dans `ambiguities`.
- `ingress.enabled: true` UNIQUEMENT si l'utilisateur demande explicitement
  un accès depuis l'EXTÉRIEUR du cluster (nom de domaine, "accessible sur
  internet", "expose en HTTPS au public"...). Un simple port HTTP interne
  ne suffit pas. Si aucun nom de domaine n'est donné, laisse `host` vide et
  ajoute une entrée dans `ambiguities` précisant qu'un placeholder devra
  être remplacé avant déploiement.
- `ingress.api_style: "gateway_api"` UNIQUEMENT si l'utilisateur mentionne
  explicitement "Gateway API", "HTTPRoute", ou un équivalent technique
  précis. Sinon reste `"ingress"` (défaut) même si l'utilisateur parle
  juste d'exposition externe en général.
- `ingress.cert_manager_issuer` UNIQUEMENT si l'utilisateur mentionne
  explicitement cert-manager ou une émission automatique de certificat TLS
  (ex: "certificat TLS géré automatiquement via Let's Encrypt"). Une
  simple mention de "HTTPS" ou "TLS" sans détail sur la gestion du
  certificat ne suffit pas — laisse ce champ vide dans ce cas (le Secret
  TLS reste alors simplement référencé, comportement par défaut).
- `rbac.enabled: true` UNIQUEMENT si l'utilisateur décrit un besoin d'accès
  à l'API Kubernetes elle-même (ex: "l'app doit lister les pods du
  namespace via l'API"). Ne mets JAMAIS `enabled: true` pour un simple
  accès à une base de données externe ou un appel HTTP à un autre service
  — ce n'est pas du RBAC Kubernetes.
- `volumes[i].size`/`storage_class_name` UNIQUEMENT pour `kind: "pvc"`, si
  l'utilisateur les précise. Sinon laisser vide (l'Agent 2 assumera une
  taille par défaut et le documentera).
- `service_mesh_routing` UNIQUEMENT si l'utilisateur décrit un besoin de
  ROUTAGE explicite (canary, split de trafic, timeout, circuit breaker...)
  — la simple présence d'un sidecar proxy n'implique pas ce besoin.
- `observability_style` reste `"annotations"` (défaut) sauf si
  l'utilisateur mentionne explicitement "Prometheus Operator" ou
  "ServiceMonitor", auquel cas utilise `"service_monitor"` ou `"both"`
  selon ce qui est demandé.
- `cron_schedule` UNIQUEMENT si `workload_type: "CronJob"` ET que
  l'utilisateur donne un horaire de déclenchement. Convertis tout horaire
  en langage naturel en cron 5 champs SANS jamais laisser le champ heure
  en `*` pour un horaire quotidien fixe (ex: "tous les jours à 3h" →
  "0 3 * * *", PAS "3 * * * *" qui se déclencherait toutes les heures).
- `config_maps[i].data` UNIQUEMENT pour des données NON SENSIBLES
  explicitement fournies (paramètres de configuration, pas des mots de
  passe/clés API — ceux-là restent dans `env_vars[].from_secret`, jamais
  en clair). Une simple variable d'environnement isolée ne justifie pas
  une ConfigMap dédiée : réserve ce champ à un vrai bloc de configuration
  (plusieurs paramètres liés, fichier de conf...).
- `network_policy.restrict_egress: true` UNIQUEMENT si l'utilisateur
  exprime un besoin de contrôle réseau EN SORTIE explicite (ex: "ce
  service ne doit parler qu'à la base de données et à rien d'autre"). Le
  hardening réseau par défaut de l'Agent 2 (restriction d'ingress) reste
  suffisant pour une simple mention de "sécurité" générale.
- `deployment_strategy` UNIQUEMENT si l'utilisateur demande explicitement
  un déploiement progressif (canary, blue-green, "rollout progressif",
  "10% du trafic d'abord"...). Un `replicas` élevé ou un besoin de
  disponibilité ne justifie PAS, à lui seul, une stratégie canary/blue-green.
- `admission_policies` (niveau NormalizedSpec, pas par composant)
  UNIQUEMENT si l'utilisateur mentionne des règles organisationnelles à
  faire respecter par TOUS les pods (ex: "exige des limits de ressources
  partout", "interdis les images non signées"). Capture la règle en
  langage naturel ; l'Agent 2 décidera s'il peut la traduire fidèlement.
- `target_clusters` UNIQUEMENT si l'utilisateur mentionne explicitement
  plusieurs clusters/régions cibles. Ce pipeline reste conçu pour UN seul
  cluster cible à la fois — capture l'information pour que l'Agent 5 la
  signale comme hors périmètre, ne tente pas de dupliquer la génération.
"""


def _extract(user_request: str) -> dict:
    prompt = f"{SCHEMA_HINT}\n\nDemande utilisateur brute :\n\"\"\"\n{user_request}\n\"\"\""
    raw = call_llm(SYSTEM_EXTRACT, prompt, agent_name="Agent 1 - Analyse (extraction)")
    return extract_json(raw)


def _self_check(user_request: str, spec_json: dict) -> list[str]:
    prompt = (
        f"Texte original :\n\"\"\"\n{user_request}\n\"\"\"\n\n"
        f"JSON structuré actuel :\n{spec_json}"
    )
    raw = call_llm(SYSTEM_SELFCHECK, prompt, agent_name="Agent 1 - Analyse (self-check)")
    result = extract_json(raw)
    return result.get("gaps", [])


def _repair(spec_json: dict, gaps: list[str]) -> dict:
    prompt = f"JSON actuel :\n{spec_json}\n\nGaps détectés à intégrer :\n{gaps}"
    raw = call_llm(SYSTEM_REPAIR, prompt, agent_name="Agent 1 - Analyse (réparation)")
    return extract_json(raw)


def _format_pydantic_errors(exc: ValidationError) -> str:
    lines = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        value = err.get("input")
        lines.append(f"- {loc} : {err['msg']} (valeur reçue : {value!r})")
    return "\n".join(lines)


def _schema_repair(spec_json: dict, errors_text: str) -> dict:
    prompt = f"JSON actuel :\n{spec_json}\n\nErreurs de validation Pydantic à corriger :\n{errors_text}"
    raw = call_llm(SYSTEM_SCHEMA_REPAIR, prompt, agent_name="Agent 1 - Analyse (réparation schéma)")
    return extract_json(raw)


def _drop_invalid_components(spec_json: dict, exc: ValidationError) -> tuple[dict, list[str]]:
    """
    Dernier recours si même la réparation de schéma via LLM échoue encore :
    si TOUTES les erreurs restantes sont rattachables à des `components[i]`
    précis (pas à un champ racine de la spec), on retire ces composants
    plutôt que de faire échouer tout le run pour une ou deux mauvaises
    entrées — même logique que la mise en quarantaine des fragments
    best-effort invalides (agents/agent2_template.py) : une partie
    défaillante ne doit jamais couler le reste, qui peut être parfaitement
    valide. Déterministe, pas de nouvel appel LLM ici (celui-ci a déjà
    échoué deux fois, on ne lui redonne pas une troisième chance à
    l'aveugle).
    """
    bad_indices: set[int] = set()
    other_errors = []
    for err in exc.errors():
        loc = err["loc"]
        if len(loc) >= 2 and loc[0] == "components" and isinstance(loc[1], int):
            bad_indices.add(loc[1])
        else:
            other_errors.append(err)

    if other_errors or not bad_indices:
        # Erreur non rattachable à un composant précis (ex: un champ racine
        # de la spec) : rien de sûr à retirer automatiquement, on laisse
        # l'appelant échouer proprement plutôt que de deviner.
        return spec_json, []

    components = spec_json.get("components", [])
    dropped_names = [
        components[i].get("component_name", f"composant index {i}")
        for i in sorted(bad_indices) if i < len(components)
    ]
    spec_json["components"] = [c for i, c in enumerate(components) if i not in bad_indices]
    return spec_json, dropped_names


def _validate_with_recovery(spec_json: dict, user_request: str) -> tuple["NormalizedSpec | None", list[str], int]:
    """
    Valide `spec_json` contre `NormalizedSpec`, avec récupération en
    cascade si ça échoue : un JSON syntaxiquement correct (extract_json a
    réussi) peut quand même violer le schéma Pydantic (type incorrect,
    énumération invalide, champ obligatoire manquant) — un LLM ne suit pas
    toujours le schéma à la lettre, et une seule valeur mal formée ne doit
    jamais faire planter tout le run.

    Cascade : (1) réparation ciblée via LLM sur les erreurs exactes,
    répétée jusqu'à `AGENT1_MAX_REPAIR_ATTEMPTS` fois ; (2) si ça échoue
    encore, retrait déterministe des seuls composants fautifs (sans
    nouvel appel LLM) ; (3) si rien ne marche, on renvoie `None` et
    l'appelant décide (état d'erreur, run interrompu proprement).

    Renvoie (spec_ou_None, warnings_de_récupération, tentatives_effectuées).
    """
    try:
        return NormalizedSpec.model_validate(spec_json), [], 0
    except ValidationError as exc:
        last_exc = exc

    recovery_warnings: list[str] = []
    attempts = 0
    while attempts < settings.AGENT1_MAX_REPAIR_ATTEMPTS:
        errors_text = _format_pydantic_errors(last_exc)
        log_warning(
            "Agent 1 - Analyse",
            f"Erreurs de schéma détectées, tentative de correction "
            f"{attempts + 1}/{settings.AGENT1_MAX_REPAIR_ATTEMPTS} : {errors_text}",
        )
        attempts += 1
        try:
            spec_json = _schema_repair(spec_json, errors_text)
            spec_json.setdefault("raw_user_request", user_request)
        except ValueError as parse_exc:
            # La réponse de réparation elle-même n'était pas du JSON valide
            # -- on ne peut rien en tirer, on retente avec les mêmes erreurs
            # au tour suivant plutôt que de s'arrêter net.
            log_warning("Agent 1 - Analyse", f"Réponse de réparation de schéma illisible : {parse_exc}")
            continue
        try:
            return NormalizedSpec.model_validate(spec_json), recovery_warnings, attempts
        except ValidationError as exc2:
            last_exc = exc2

    spec_json, dropped = _drop_invalid_components(spec_json, last_exc)
    if dropped:
        msg = (
            f"Composant(s) invalide(s) retiré(s) après échec de correction "
            f"({attempts} tentative(s)) : {dropped}. Vérifiez si ces exigences "
            f"ont été récupérées dans `unmapped_requirements`, sinon elles "
            f"sont perdues et la demande doit être reformulée."
        )
        log_warning("Agent 1 - Analyse", msg)
        recovery_warnings.append(msg)
        try:
            return NormalizedSpec.model_validate(spec_json), recovery_warnings, attempts
        except ValidationError as exc3:
            last_exc = exc3

    recovery_warnings.append(f"Échec final de validation du schéma : {last_exc}")
    return None, recovery_warnings, attempts


def run_agent1(state: PipelineState) -> PipelineState:
    log_step("Agent 1 - Analyse", "Extraction de la demande utilisateur...")

    spec_json = _extract(state.user_request)
    spec_json.setdefault("raw_user_request", state.user_request)

    attempts = 0
    gaps = _self_check(state.user_request, spec_json)

    while gaps and attempts < settings.AGENT1_MAX_REPAIR_ATTEMPTS:
        log_warning(
            "Agent 1 - Analyse",
            f"{len(gaps)} exigence(s) manquante(s) détectée(s), tentative de "
            f"réparation {attempts + 1}/{settings.AGENT1_MAX_REPAIR_ATTEMPTS}: {gaps}",
        )
        spec_json = _repair(spec_json, gaps)
        spec_json.setdefault("raw_user_request", state.user_request)
        attempts += 1
        gaps = _self_check(state.user_request, spec_json)

    coverage = spec_json.get("coverage", {})
    coverage["repair_attempts"] = attempts
    coverage["self_check_passed"] = len(gaps) == 0
    if gaps:
        # On documente ce qui reste non couvert malgré les tentatives, au
        # lieu de le faire disparaître silencieusement.
        coverage["requirements_unmapped"] = list(
            set(coverage.get("requirements_unmapped", []) + gaps)
        )
    spec_json["coverage"] = coverage

    spec, recovery_warnings, schema_repair_attempts = _validate_with_recovery(spec_json, state.user_request)

    if spec is None:
        state.error = (
            f"Agent 1 - Analyse : impossible de produire une NormalizedSpec valide "
            f"après {schema_repair_attempts} tentative(s) de réparation de schéma. "
            f"{recovery_warnings[-1] if recovery_warnings else ''}"
        )
        return state

    if not spec.coverage.self_check_passed:
        log_warning(
            "Agent 1 - Analyse",
            f"Auto-vérification incomplète après {attempts} réparation(s). "
            f"Éléments non couverts transmis pour audit final: "
            f"{spec.coverage.requirements_unmapped}",
        )

    if spec.unmapped_requirements:
        log_warning(
            "Agent 1 - Analyse",
            f"{len(spec.unmapped_requirements)} exigence(s) hors du schéma "
            f"structuré, à générer en best-effort par l'Agent 2 : "
            f"{[r.text for r in spec.unmapped_requirements]}",
        )

    report = AgentReport(
        agent_name="Agent 1 - Analyse",
        fields_addressed=["architecture_type", "namespace"] + [
            f"components[{c.component_name}]" for c in spec.components
        ],
        fields_left_open=list(spec.coverage.requirements_unmapped) + [
            f"unmapped_requirements: {r.text} (suggested_kind={r.suggested_kind})"
            for r in spec.unmapped_requirements
        ] + recovery_warnings,
        actions=[
            f"Extraction initiale + {attempts} passe(s) de réparation interne",
            f"Architecture détectée : {spec.architecture_type} "
            f"({len(spec.components)} composant(s))",
        ] + ([f"Réparation de schéma : {schema_repair_attempts} tentative(s)"] if schema_repair_attempts else []),
        warnings=[a.question for a in spec.ambiguities] + recovery_warnings,
    )

    state.spec = spec
    state.reports.append(report)
    return state
