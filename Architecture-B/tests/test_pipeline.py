"""
tests/test_pipeline.py

Test de bout en bout du câblage du pipeline (StateGraph LangGraph +
schémas Pydantic), avec le LLM entièrement simulé (monkeypatch de
`call_llm` dans chaque module agent). Aucun appel réseau, aucune clé API
requise. Objectif : garantir que l'assemblage du graphe, le passage de
state, et le parsing JSON->Pydantic fonctionnent, indépendamment de la
qualité réelle des réponses du modèle Gemma.

Les mocks des Agents 2 et 4 sont "component-aware" : comme ces agents
sont maintenant appelés une fois par composant (voir agents/agent2_template.py
et agents/agent4_energie.py), les mocks parsent le nom du composant dans le
prompt reçu pour générer une réponse cohérente — nécessaire pour tester
correctement les scénarios microservices à plusieurs composants.

Lancer avec : pytest tests/test_pipeline.py -v
"""

import ast
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas import PipelineState  # noqa: E402
import agents.agent1_analyse as a1  # noqa: E402
import agents.agent2_template as a2  # noqa: E402
import agents.agent3_validation as a3  # noqa: E402
import agents.agent4_energie as a4  # noqa: E402
import agents.agent5_verification as a5  # noqa: E402
from graph import build_pipeline  # noqa: E402


# ---------------------------------------------------------------------------
# Spec factice : architecture "single", un composant avec un sidecar, pour
# exercer à la fois le chemin standard ET le pattern sidecar en un seul test.
# ---------------------------------------------------------------------------

FAKE_SPEC = {
    "architecture_type": "single",
    "namespace": "payments",
    "components": [{
        "component_name": "checkout-api",
        "workload_type": "Deployment",
        "image": "myregistry/checkout:1.4.2",
        "replicas": 3,
        "labels": {"app": "checkout-api"},
        "ports": [{"name": "http", "container_port": 8080, "protocol": "TCP", "expose_service": True}],
        "env_vars": [{"name": "NODE_ENV", "value": "production"}],
        "volumes": [],
        "sidecars": [{
            "name": "envoy-proxy",
            "image": "envoyproxy/envoy:v1.29-latest",
            "purpose": "proxy de service mesh",
            "ports": [{"name": "proxy", "container_port": 9901, "protocol": "TCP", "expose_service": False}],
            "env_vars": [],
        }],
        "depends_on": [],
        "energy_goals": ["scaler automatiquement pour économiser aux heures creuses"],
        "resource_hints": "trafic faible la nuit, élevé le matin",
        "traffic_windows": [],
        "constraints": [],
        "security_requirements": ["exposée en interne uniquement"],
        "observability_requirements": ["métriques Prometheus sur le port 9091"],
    }],
    "raw_user_request": "Déploie checkout-api avec un sidecar Envoy...",
    "ambiguities": [],
    "coverage": {
        "requirements_detected": ["nom app", "image", "port", "sidecar"],
        "requirements_mapped": ["nom app", "image", "port", "sidecar"],
        "requirements_unmapped": [],
        "repair_attempts": 0,
        "self_check_passed": True,
    },
}


def _deployment_yaml(name: str, namespace: str, image: str, port: int,
                      extra_containers: str = "") -> str:
    return (
        f"apiVersion: apps/v1\n"
        f"kind: Deployment\n"
        f"metadata:\n"
        f"  name: {name}\n"
        f"  namespace: {namespace}\n"
        f"spec:\n"
        f"  replicas: 3\n"
        f"  selector:\n"
        f"    matchLabels:\n"
        f"      app: {name}\n"
        f"  template:\n"
        f"    metadata:\n"
        f"      labels:\n"
        f"        app: {name}\n"
        f"    spec:\n"
        f"      containers:\n"
        f"        - name: {name}\n"
        f"          image: {image}\n"
        f"          ports:\n"
        f"            - containerPort: {port}\n"
        f"{extra_containers}"
    )


def _service_yaml(name: str, namespace: str, port: int) -> str:
    return (
        f"---\n"
        f"apiVersion: v1\n"
        f"kind: Service\n"
        f"metadata:\n"
        f"  name: {name}\n"
        f"  namespace: {namespace}\n"
        f"spec:\n"
        f"  type: ClusterIP\n"
        f"  selector:\n"
        f"    app: {name}\n"
        f"  ports:\n"
        f"    - port: {port}\n"
        f"      targetPort: {port}\n"
    )


def _extract_trailing_dict(text: str, marker: str) -> dict:
    """Extrait et parse le dict Python (repr `str(dict)`) qui suit `marker`
    jusqu'à la fin du texte — utilisé pour retrouver, dans le prompt reçu
    par un mock, quel composant est en cours de traitement."""
    idx = text.rfind(marker)
    assert idx != -1, f"marker '{marker}' introuvable dans le prompt"
    raw = text[idx + len(marker):].strip()
    return ast.literal_eval(raw)


def fake_call_llm_agent1(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
    if "AUTO-VÉRIFICATION" in system_prompt or "gaps" in system_prompt.lower():
        return json.dumps({"gaps": []})
    return json.dumps(FAKE_SPEC)


def fake_call_llm_agent2(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
    component = _extract_trailing_dict(user_prompt, "champs pertinents) :\n")
    name = component["component_name"]
    namespace = component["namespace"]
    image = component["image"]
    port = component["ports"][0]["container_port"] if component.get("ports") else 8080

    extra_containers = ""
    for sc in component.get("sidecars", []):
        extra_containers += (
            f"        - name: {sc['name']}\n"
            f"          image: {sc['image']}\n"
        )

    manifest = _deployment_yaml(name, namespace, image, port, extra_containers) + \
        _service_yaml(name, namespace, port)

    return json.dumps({
        "manifest_yaml": manifest,
        "fields_addressed": ["component_name", "image", "ports", "replicas"],
        "fields_left_open": ["energy_goals (agent 4)"],
        "security_requirements_addressed": ["exposée en interne uniquement -> Service ClusterIP"],
        "security_requirements_left_open": [],
        "observability_requirements_addressed": [
            "métriques Prometheus -> annotations prometheus.io/scrape sur le pod"
        ],
        "observability_requirements_left_open": [],
        "warnings": [],
    })


def fake_call_llm_agent3(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
    match = re.search(r"Manifeste à valider :\n(.*?)\n\nNormalizedSpec", user_prompt, re.DOTALL)
    manifest = match.group(1) if match else ""
    return json.dumps({
        "manifest_yaml": manifest,
        "checks_passed": ["apiVersion présent", "selector cohérent"],
        "checks_failed_and_fixed": [],
        "fields_addressed": ["component_name", "image"],
        "fields_left_open": [],
        "warnings": [],
    })


def fake_call_llm_agent4(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
    component = _extract_trailing_dict(user_prompt, "champs pertinents) :\n")
    name = component["component_name"]
    chunk_match = re.search(r"Manifeste validé de ce composant :\n(.*?)\n\nContexte énergie",
                             user_prompt, re.DOTALL)
    chunk = chunk_match.group(1) if chunk_match else ""

    enriched = chunk + (
        f"---\n"
        f"apiVersion: autoscaling/v2\n"
        f"kind: HorizontalPodAutoscaler\n"
        f"metadata:\n"
        f"  name: {name}-hpa\n"
        f"spec:\n"
        f"  scaleTargetRef:\n"
        f"    apiVersion: apps/v1\n"
        f"    kind: Deployment\n"
        f"    name: {name}\n"
        f"  minReplicas: 2\n"
        f"  maxReplicas: 8\n"
    )
    return json.dumps({
        "manifest_yaml": enriched,
        "energy_goals_addressed": ["scaler automatiquement pour économiser aux heures creuses"],
        "energy_goals_left_open": [],
        "actions": ["Ajout HPA min=2 max=8"],
        "fields_addressed": ["resources", "hpa"],
        "fields_left_open": [],
        "warnings": [],
    })


def fake_call_llm_agent5(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
    match = re.search(r"Manifeste final \(avant vérification\) :\n(.*?)\n\nNormalizedSpec",
                       user_prompt, re.DOTALL)
    manifest = match.group(1) if match else ""
    return json.dumps({
        "manifest_yaml": manifest,
        "syntax_checks": ["yaml.safe_load_all OK"],
        "syntax_fixes": [],
        "traceability_matrix": [],
        "unresolved_items": [],
        "fields_addressed": ["tout"],
        "warnings": [],
    })


@pytest.fixture(autouse=True)
def patch_llm(monkeypatch):
    monkeypatch.setattr(a1, "call_llm", fake_call_llm_agent1)
    monkeypatch.setattr(a2, "call_llm", fake_call_llm_agent2)
    monkeypatch.setattr(a3, "call_llm", fake_call_llm_agent3)
    monkeypatch.setattr(a4, "call_llm", fake_call_llm_agent4)
    monkeypatch.setattr(a5, "call_llm", fake_call_llm_agent5)


def test_full_pipeline_runs_end_to_end():
    pipeline = build_pipeline()
    initial_state = PipelineState(user_request="Déploie checkout-api avec un sidecar Envoy...")

    result_dict = pipeline.invoke(initial_state)
    state = PipelineState.model_validate(result_dict)

    assert state.error is None
    assert state.spec is not None
    assert state.spec.architecture_type == "single"
    assert len(state.spec.components) == 1
    assert state.spec.components[0].component_name == "checkout-api"
    assert state.manifest_final_yaml is not None
    assert "HorizontalPodAutoscaler" in state.manifest_final_yaml
    assert "envoy-proxy" in state.manifest_v1_yaml  # sidecar bien packagé par l'Agent 2
    assert len(state.reports) == 5
    assert state.reports[0].agent_name == "Agent 1 - Analyse"
    assert state.reports[-1].agent_name == "Agent 5 - Vérification finale"


def test_agent_order_is_strict_sequential():
    pipeline = build_pipeline()
    initial_state = PipelineState(user_request="Déploie checkout-api...")
    result_dict = pipeline.invoke(initial_state)
    state = PipelineState.model_validate(result_dict)

    names = [r.agent_name for r in state.reports]
    assert names == [
        "Agent 1 - Analyse",
        "Agent 2 - Template",
        "Agent 3 - Validation",
        "Agent 4 - Énergie",
        "Agent 5 - Vérification finale",
    ]


def test_stops_cleanly_on_error(monkeypatch):
    def broken_agent1(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        return "ceci n'est pas du json valide"

    monkeypatch.setattr(a1, "call_llm", broken_agent1)

    pipeline = build_pipeline()
    initial_state = PipelineState(user_request="test")
    result_dict = pipeline.invoke(initial_state)
    state = PipelineState.model_validate(result_dict)

    assert state.error is not None
    assert state.manifest_final_yaml is None


# ---------------------------------------------------------------------------
# Scénario microservices : plusieurs composants en interaction
# ---------------------------------------------------------------------------

MICROSERVICES_SPEC = {
    "architecture_type": "microservices",
    "namespace": "shop",
    "components": [
        {
            "component_name": "api-gateway",
            "workload_type": "Deployment",
            "image": "shop/gateway:1.0",
            "replicas": 2,
            "labels": {}, "ports": [{"name": "http", "container_port": 8080, "expose_service": True}],
            "env_vars": [], "volumes": [], "sidecars": [],
            "depends_on": ["order-worker"],
            "energy_goals": [], "resource_hints": None, "traffic_windows": [],
            "constraints": [], "security_requirements": [], "observability_requirements": [],
        },
        {
            "component_name": "order-worker",
            "workload_type": "Deployment",
            "image": "shop/worker:1.0",
            "replicas": 1,
            "labels": {}, "ports": [], "env_vars": [], "volumes": [], "sidecars": [],
            "depends_on": [],
            "energy_goals": [], "resource_hints": None, "traffic_windows": [],
            "constraints": [], "security_requirements": [], "observability_requirements": [],
        },
    ],
    "raw_user_request": "Déploie un api-gateway et un order-worker qui communiquent...",
    "ambiguities": [],
    "coverage": {
        "requirements_detected": ["gateway", "worker"],
        "requirements_mapped": ["gateway", "worker"],
        "requirements_unmapped": [],
        "repair_attempts": 0,
        "self_check_passed": True,
    },
}


def test_microservices_generates_one_deployment_per_component(monkeypatch):
    def fake_agent1(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "AUTO-VÉRIFICATION" in system_prompt or "gaps" in system_prompt.lower():
            return json.dumps({"gaps": []})
        return json.dumps(MICROSERVICES_SPEC)

    monkeypatch.setattr(a1, "call_llm", fake_agent1)

    pipeline = build_pipeline()
    initial_state = PipelineState(user_request="Déploie api-gateway + order-worker...")
    result_dict = pipeline.invoke(initial_state)
    state = PipelineState.model_validate(result_dict)

    assert state.error is None
    assert state.spec.architecture_type == "microservices"
    assert len(state.spec.components) == 2
    assert "api-gateway" in state.manifest_final_yaml
    assert "order-worker" in state.manifest_final_yaml
    # Chaque composant doit avoir reçu son propre HPA (généré par l'Agent 4, par composant)
    assert "api-gateway-hpa" in state.manifest_final_yaml
    assert "order-worker-hpa" in state.manifest_final_yaml


# ---------------------------------------------------------------------------
# Scénario "toutes les nouvelles capacités" : Ingress, RBAC, PVC, CronJob,
# Namespace dédié — bout-en-bout à travers tout le pipeline.
# ---------------------------------------------------------------------------

FULL_FEATURED_SPEC = {
    "architecture_type": "single",
    "namespace": "reporting",
    "components": [{
        "component_name": "report-generator",
        "workload_type": "CronJob",
        "cron_schedule": "0 3 * * *",
        "image": "reports/generator:1.0",
        "replicas": 1,
        "labels": {}, "ports": [], "env_vars": [],
        "volumes": [{"name": "output", "mount_path": "/data", "kind": "pvc",
                     "size": "20Gi", "storage_class_name": None}],
        "sidecars": [], "depends_on": [],
        "energy_goals": [], "resource_hints": None, "traffic_windows": [],
        "constraints": [], "security_requirements": [], "observability_requirements": [],
        "ingress": {"enabled": True, "host": "reports.exemple.com", "path": "/",
                    "tls": True, "tls_secret_name": None, "ingress_class": None},
        "rbac": {"enabled": True, "rules_description": ["lire les ConfigMaps du namespace"]},
        "service_mesh_routing": [],
        "observability_style": "annotations",
    }],
    "raw_user_request": "Déploie un générateur de rapports planifié tous les jours à 3h...",
    "ambiguities": [],
    "coverage": {"requirements_detected": [], "requirements_mapped": [],
                 "requirements_unmapped": [], "repair_attempts": 0, "self_check_passed": True},
}


def fake_call_llm_agent2_full_featured(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
    component = _extract_trailing_dict(user_prompt, "champs pertinents) :\n")
    name = component["component_name"]
    ns = component["namespace"]

    manifest = (
        f"apiVersion: batch/v1\n"
        f"kind: CronJob\n"
        f"metadata:\n  name: {name}\n  namespace: {ns}\n"
        f"spec:\n"
        f"  schedule: \"{component['cron_schedule']}\"\n"
        f"  jobTemplate:\n"
        f"    spec:\n"
        f"      template:\n"
        f"        metadata:\n"
        f"          labels:\n"
        f"            app: {name}\n"
        f"        spec:\n"
        f"          serviceAccountName: {name}-sa\n"
        f"          containers:\n"
        f"            - name: {name}\n"
        f"              image: {component['image']}\n"
        f"          volumes:\n"
        f"            - name: output\n"
        f"              persistentVolumeClaim:\n"
        f"                claimName: {name}-output\n"
        f"---\n"
        f"apiVersion: v1\nkind: PersistentVolumeClaim\n"
        f"metadata:\n  name: {name}-output\n  namespace: {ns}\n"
        f"spec:\n  accessModes: [ReadWriteOnce]\n  resources:\n    requests:\n      storage: 20Gi\n"
        f"---\n"
        f"apiVersion: v1\nkind: ServiceAccount\n"
        f"metadata:\n  name: {name}-sa\n  namespace: {ns}\n"
        f"---\n"
        f"apiVersion: rbac.authorization.k8s.io/v1\nkind: Role\n"
        f"metadata:\n  name: {name}-role\n  namespace: {ns}\n"
        f"rules:\n  - apiGroups: [\"\"]\n    resources: [\"configmaps\"]\n    verbs: [\"get\",\"list\",\"watch\"]\n"
        f"---\n"
        f"apiVersion: rbac.authorization.k8s.io/v1\nkind: RoleBinding\n"
        f"metadata:\n  name: {name}-rb\n  namespace: {ns}\n"
        f"roleRef:\n  name: {name}-role\n  kind: Role\n  apiGroup: rbac.authorization.k8s.io\n"
        f"subjects:\n  - kind: ServiceAccount\n    name: {name}-sa\n"
        f"---\n"
        f"apiVersion: v1\nkind: Service\n"
        f"metadata:\n  name: {name}\n  namespace: {ns}\n"
        f"spec:\n  selector:\n    app: {name}\n  ports:\n    - port: 80\n"
        f"---\n"
        f"apiVersion: networking.k8s.io/v1\nkind: Ingress\n"
        f"metadata:\n  name: {name}-ingress\n  namespace: {ns}\n"
        f"spec:\n  rules:\n    - host: {component['ingress']['host']}\n"
        f"      http:\n        paths:\n          - path: /\n            pathType: Prefix\n"
        f"            backend:\n              service:\n                name: {name}\n"
        f"                port:\n                  number: 80\n"
    )
    return json.dumps({
        "manifest_yaml": manifest,
        "fields_addressed": ["component_name", "image"],
        "fields_left_open": [],
        "security_requirements_addressed": [], "security_requirements_left_open": [],
        "observability_requirements_addressed": [], "observability_requirements_left_open": [],
        "ingress_addressed": ["exposition externe -> Ingress + TLS"],
        "ingress_left_open": [],
        "rbac_addressed": ["lire les ConfigMaps -> Role/RoleBinding"],
        "rbac_left_open": [],
        "warnings": ["Secret TLS non précisé, nom supposé par convention à vérifier."],
    })


def fake_call_llm_agent4_no_hpa_for_cronjob(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
    """CronJob : pas d'HPA/ScaledObject pertinent, on renvoie le chunk tel quel
    (juste un passage, comme si l'Agent 4 n'avait rien à optimiser de plus)."""
    chunk_match = re.search(r"Manifeste validé de ce composant :\n(.*?)\n\nContexte énergie",
                             user_prompt, re.DOTALL)
    chunk = chunk_match.group(1) if chunk_match else ""
    return json.dumps({
        "manifest_yaml": chunk,
        "energy_goals_addressed": [], "energy_goals_left_open": [],
        "actions": ["workload_type='CronJob' : pas de HPA/ScaledObject généré"],
        "fields_addressed": [], "fields_left_open": [], "warnings": [],
    })


def test_full_featured_pipeline_ingress_rbac_pvc_cronjob(monkeypatch):
    def fake_agent1(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "AUTO-VÉRIFICATION" in system_prompt or "gaps" in system_prompt.lower():
            return json.dumps({"gaps": []})
        return json.dumps(FULL_FEATURED_SPEC)

    monkeypatch.setattr(a1, "call_llm", fake_agent1)
    monkeypatch.setattr(a2, "call_llm", fake_call_llm_agent2_full_featured)
    monkeypatch.setattr(a4, "call_llm", fake_call_llm_agent4_no_hpa_for_cronjob)

    pipeline = build_pipeline()
    initial_state = PipelineState(user_request="Déploie un générateur de rapports...")
    result_dict = pipeline.invoke(initial_state)
    state = PipelineState.model_validate(result_dict)

    assert state.error is None, state.error
    final = state.manifest_final_yaml

    # Namespace dédié généré une seule fois (déterministe, pas par le LLM)
    assert "kind: Namespace" in state.manifest_v1_yaml
    assert state.manifest_v1_yaml.count("name: reporting") >= 1

    # Toutes les nouvelles ressources doivent apparaître dans le final
    for expected in ("kind: CronJob", "kind: PersistentVolumeClaim",
                      "kind: ServiceAccount", "kind: Role", "kind: RoleBinding",
                      "kind: Ingress", "0 3 * * *", "report-generator-sa",
                      "report-generator-output", "reports.exemple.com"):
        assert expected in final, f"'{expected}' absent du manifeste final"

    # Le contrôle déterministe de l'Agent 5 ne doit remonter aucune
    # incohérence cross-ressources sur ce manifeste cohérent.
    from utils.yaml_utils import load_all_documents
    from utils.k8s_validate import full_validation
    docs = load_all_documents(final)
    assert full_validation(docs) == []


# ---------------------------------------------------------------------------
# Priorité 6 : couverture de branches supplémentaires
# ---------------------------------------------------------------------------

def test_job_workload_type_gets_no_hpa(monkeypatch):
    """Un Job simple (pas CronJob) ne doit recevoir ni HPA ni ScaledObject."""
    job_spec = dict(FAKE_SPEC)
    job_spec["components"] = [dict(FAKE_SPEC["components"][0])]
    job_spec["components"][0]["workload_type"] = "Job"
    job_spec["components"][0]["sidecars"] = []

    def fake_agent1(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "AUTO-VÉRIFICATION" in system_prompt or "gaps" in system_prompt.lower():
            return json.dumps({"gaps": []})
        return json.dumps(job_spec)

    def fake_agent4_no_hpa(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        chunk_match = re.search(r"Manifeste validé de ce composant :\n(.*?)\n\nContexte énergie",
                                 user_prompt, re.DOTALL)
        chunk = chunk_match.group(1) if chunk_match else ""
        return json.dumps({
            "manifest_yaml": chunk, "energy_goals_addressed": [], "energy_goals_left_open": [],
            "actions": ["workload_type='Job' : pas de HPA/ScaledObject généré"],
            "fields_addressed": [], "fields_left_open": [], "warnings": [],
        })

    monkeypatch.setattr(a1, "call_llm", fake_agent1)
    monkeypatch.setattr(a4, "call_llm", fake_agent4_no_hpa)

    pipeline = build_pipeline()
    state = PipelineState.model_validate(
        pipeline.invoke(PipelineState(user_request="Déploie un job ponctuel..."))
    )
    assert state.error is None
    assert "HorizontalPodAutoscaler" not in state.manifest_final_yaml
    assert "ScaledObject" not in state.manifest_final_yaml


def test_multiple_sidecars_all_packaged_in_same_pod():
    multi_sidecar_spec = dict(FAKE_SPEC)
    multi_sidecar_spec["components"] = [dict(FAKE_SPEC["components"][0])]
    multi_sidecar_spec["components"][0]["sidecars"] = [
        {"name": "envoy-proxy", "image": "envoyproxy/envoy:v1.29-latest",
         "purpose": "proxy de service mesh", "ports": [], "env_vars": []},
        {"name": "log-shipper", "image": "fluent/fluent-bit:latest",
         "purpose": "collecteur de logs", "ports": [], "env_vars": []},
    ]

    def fake_agent1(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "AUTO-VÉRIFICATION" in system_prompt or "gaps" in system_prompt.lower():
            return json.dumps({"gaps": []})
        return json.dumps(multi_sidecar_spec)

    def fake_agent2_multi_sidecar(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        component = _extract_trailing_dict(user_prompt, "champs pertinents) :\n")
        extra = "".join(
            f"        - name: {sc['name']}\n          image: {sc['image']}\n"
            for sc in component.get("sidecars", [])
        )
        manifest = _deployment_yaml(component["component_name"], component["namespace"],
                                     component["image"], 8080, extra)
        return json.dumps({
            "manifest_yaml": manifest, "fields_addressed": [], "fields_left_open": [],
            "security_requirements_addressed": [], "security_requirements_left_open": [],
            "observability_requirements_addressed": [], "observability_requirements_left_open": [],
            "warnings": [],
        })

    with pytest.MonkeyPatch.context() as m:
        m.setattr(a1, "call_llm", fake_agent1)
        m.setattr(a2, "call_llm", fake_agent2_multi_sidecar)

        pipeline = build_pipeline()
        state = PipelineState.model_validate(
            pipeline.invoke(PipelineState(user_request="Déploie avec deux sidecars..."))
        )

    assert state.error is None
    # Un seul document Deployment doit contenir les 2 sidecars + le conteneur principal
    from utils.yaml_utils import load_all_documents
    docs = load_all_documents(state.manifest_v1_yaml)
    deployment = next(d for d in docs if d.get("kind") == "Deployment")
    container_names = {c["name"] for c in deployment["spec"]["template"]["spec"]["containers"]}
    assert container_names == {"checkout-api", "envoy-proxy", "log-shipper"}


def test_circular_dependency_is_surfaced_in_audit_report(monkeypatch, tmp_path):
    """Vérifie que main.py signale bien un cycle A<->B dans le rapport
    d'audit, sans empêcher le pipeline (qui reste une chaîne stricte) de
    tourner jusqu'au bout."""
    circular_spec = {
        "architecture_type": "microservices",
        "namespace": "shop",
        "components": [
            {"component_name": "svc-a", "workload_type": "Deployment", "image": "a:1",
             "replicas": 1, "labels": {}, "ports": [], "env_vars": [], "volumes": [],
             "sidecars": [], "depends_on": ["svc-b"],
             "energy_goals": [], "resource_hints": None, "traffic_windows": [],
             "constraints": [], "security_requirements": [], "observability_requirements": []},
            {"component_name": "svc-b", "workload_type": "Deployment", "image": "b:1",
             "replicas": 1, "labels": {}, "ports": [], "env_vars": [], "volumes": [],
             "sidecars": [], "depends_on": ["svc-a"],
             "energy_goals": [], "resource_hints": None, "traffic_windows": [],
             "constraints": [], "security_requirements": [], "observability_requirements": []},
        ],
        "raw_user_request": "svc-a et svc-b dépendent l'un de l'autre...",
        "ambiguities": [],
        "coverage": {"requirements_detected": [], "requirements_mapped": [],
                     "requirements_unmapped": [], "repair_attempts": 0, "self_check_passed": True},
    }

    def fake_agent1(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "AUTO-VÉRIFICATION" in system_prompt or "gaps" in system_prompt.lower():
            return json.dumps({"gaps": []})
        return json.dumps(circular_spec)

    monkeypatch.setattr(a1, "call_llm", fake_agent1)
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--output-dir", str(tmp_path / "output"), "svc-a et svc-b se dépendent...",
    ])

    import main as main_module
    main_module.main()

    run_dir = next((tmp_path / "output").iterdir())
    audit = (run_dir / "audit_report.md").read_text(encoding="utf-8")
    assert "circulaires" in audit
    assert "svc-a" in audit and "svc-b" in audit


# ---------------------------------------------------------------------------
# Gateway API, cert-manager, volumeClaimTemplates (StatefulSet), multi-cluster
# ---------------------------------------------------------------------------

GATEWAY_MULTICLUSTER_SPEC = {
    "architecture_type": "single",
    "namespace": "data",
    "target_clusters": ["prod-eu-west", "prod-us-east"],
    "components": [{
        "component_name": "event-store",
        "workload_type": "StatefulSet",
        "image": "eventstore/eventstore:1.0",
        "replicas": 3,
        "labels": {}, "ports": [{"name": "http", "container_port": 8080, "expose_service": True}],
        "env_vars": [], "volumes": [{"name": "data", "mount_path": "/var/lib/eventstore",
                                      "kind": "pvc", "size": "50Gi", "storage_class_name": None}],
        "sidecars": [], "depends_on": [],
        "energy_goals": [], "resource_hints": None, "traffic_windows": [],
        "constraints": [], "security_requirements": [], "observability_requirements": [],
        "ingress": {"enabled": True, "host": "events.exemple.com", "path": "/", "tls": True,
                    "tls_secret_name": None, "ingress_class": None,
                    "api_style": "gateway_api", "gateway_name": "shared-gateway",
                    "cert_manager_issuer": "letsencrypt-prod", "cert_manager_issuer_kind": "ClusterIssuer"},
        "rbac": {"enabled": False, "rules_description": []},
        "service_mesh_routing": [], "observability_style": "annotations",
    }],
    "raw_user_request": "Déploie event-store en StatefulSet multi-cluster avec Gateway API et cert-manager...",
    "ambiguities": [],
    "coverage": {"requirements_detected": [], "requirements_mapped": [],
                 "requirements_unmapped": [], "repair_attempts": 0, "self_check_passed": True},
}


def fake_call_llm_agent2_gateway_multicluster(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
    component = _extract_trailing_dict(user_prompt, "champs pertinents) :\n")
    name = component["component_name"]
    ns = component["namespace"]

    manifest = (
        f"apiVersion: apps/v1\n"
        f"kind: StatefulSet\n"
        f"metadata:\n  name: {name}\n  namespace: {ns}\n"
        f"spec:\n"
        f"  replicas: 3\n"
        f"  serviceName: {name}\n"
        f"  selector:\n    matchLabels:\n      app: {name}\n"
        f"  volumeClaimTemplates:\n"
        f"    - metadata:\n        name: data\n"
        f"      spec:\n        accessModes: [ReadWriteOnce]\n"
        f"        resources:\n          requests:\n            storage: 50Gi\n"
        f"  template:\n"
        f"    metadata:\n      labels:\n        app: {name}\n"
        f"    spec:\n"
        f"      serviceAccountName: {name}-sa\n"
        f"      containers:\n"
        f"        - name: {name}\n"
        f"          image: {component['image']}\n"
        f"          ports:\n            - containerPort: 8080\n"
        f"          volumeMounts:\n            - name: data\n              mountPath: /var/lib/eventstore\n"
        f"---\n"
        f"apiVersion: v1\nkind: Service\n"
        f"metadata:\n  name: {name}\n  namespace: {ns}\n"
        f"spec:\n  selector:\n    app: {name}\n  ports:\n    - port: 8080\n      targetPort: 8080\n"
        f"---\n"
        f"apiVersion: v1\nkind: ServiceAccount\n"
        f"metadata:\n  name: {name}-sa\n  namespace: {ns}\n"
        f"---\n"
        f"apiVersion: gateway.networking.k8s.io/v1\nkind: HTTPRoute\n"
        f"metadata:\n  name: {name}-route\n  namespace: {ns}\n"
        f"spec:\n"
        f"  parentRefs:\n    - name: {component['ingress']['gateway_name']}\n"
        f"  hostnames:\n    - {component['ingress']['host']}\n"
        f"  rules:\n    - backendRefs:\n        - name: {name}\n          port: 8080\n"
        f"---\n"
        f"apiVersion: cert-manager.io/v1\nkind: Certificate\n"
        f"metadata:\n  name: {name}-tls-cert\n  namespace: {ns}\n"
        f"spec:\n"
        f"  secretName: {name}-tls\n"
        f"  dnsNames:\n    - {component['ingress']['host']}\n"
        f"  issuerRef:\n    name: {component['ingress']['cert_manager_issuer']}\n"
        f"    kind: {component['ingress']['cert_manager_issuer_kind']}\n"
    )
    return json.dumps({
        "manifest_yaml": manifest,
        "fields_addressed": ["component_name", "image", "volumes"], "fields_left_open": [],
        "security_requirements_addressed": [], "security_requirements_left_open": [],
        "observability_requirements_addressed": [], "observability_requirements_left_open": [],
        "ingress_addressed": ["exposition externe -> HTTPRoute + Certificate cert-manager"],
        "ingress_left_open": [],
        "rbac_addressed": [], "rbac_left_open": [],
        "warnings": ["HTTPRoute nécessite les CRD Gateway API installées.",
                     "Certificate nécessite cert-manager installé avec l'Issuer configuré."],
    })


def test_gateway_api_certmanager_statefulset_pvc_multicluster_end_to_end(monkeypatch):
    def fake_agent1(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "AUTO-VÉRIFICATION" in system_prompt or "gaps" in system_prompt.lower():
            return json.dumps({"gaps": []})
        return json.dumps(GATEWAY_MULTICLUSTER_SPEC)

    monkeypatch.setattr(a1, "call_llm", fake_agent1)
    monkeypatch.setattr(a2, "call_llm", fake_call_llm_agent2_gateway_multicluster)
    monkeypatch.setattr(a4, "call_llm", fake_call_llm_agent4_no_hpa_for_cronjob)  # pas de scaling pertinent ici

    pipeline = build_pipeline()
    state = PipelineState.model_validate(
        pipeline.invoke(PipelineState(user_request="event-store multi-cluster..."))
    )

    assert state.error is None, state.error
    final = state.manifest_final_yaml

    for expected in ("kind: StatefulSet", "volumeClaimTemplates", "kind: HTTPRoute",
                      "kind: Certificate", "kind: ApplicationSet", "shared-gateway",
                      "letsencrypt-prod", "REMPLACER-PAR-URL-API-DU-CLUSTER-prod-eu-west",
                      "REMPLACER-PAR-URL-API-DU-CLUSTER-prod-us-east"):
        assert expected in final, f"'{expected}' absent du manifeste final"

    # Aucun PersistentVolumeClaim externe ne doit être généré pour ce
    # StatefulSet (volumeClaimTemplates natif attendu à la place).
    assert "kind: PersistentVolumeClaim" not in final

    from utils.yaml_utils import load_all_documents
    from utils.k8s_validate import full_validation
    docs = load_all_documents(final)
    assert full_validation(docs) == []


# ---------------------------------------------------------------------------
# unmapped_requirements : filet de sécurité générique pour l'inconnu
# ---------------------------------------------------------------------------

UNMAPPED_SPEC = dict(FAKE_SPEC)
UNMAPPED_SPEC["components"] = [dict(FAKE_SPEC["components"][0])]
UNMAPPED_SPEC["components"][0]["sidecars"] = []
UNMAPPED_SPEC["unmapped_requirements"] = [
    {"text": "utilise un opérateur PostgreSQL pour la base de données",
     "suggested_kind": "PostgresCluster"},
]


def fake_call_llm_agent1_unmapped(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
    if "AUTO-VÉRIFICATION" in system_prompt or "gaps" in system_prompt.lower():
        return json.dumps({"gaps": []})
    return json.dumps(UNMAPPED_SPEC)


def fake_call_llm_agent2_with_unmapped_fragment(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
    """
    Simule le comportement réel d'Agent 2 : deux types d'appels LLM
    distincts sur le même mock -- un par composant (retourne du JSON,
    comme d'habitude) et un pour le fragment best-effort (retourne du YAML
    brut, PAS du JSON -- reconnu par l'absence du marqueur habituel dans
    le prompt).
    """
    if "Exigences non standard" in user_prompt:
        return (
            "# ⚠️ GÉNÉRATION LIBRE — non vérifiée, à valider manuellement.\n"
            "apiVersion: postgres-operator.crunchydata.com/v1beta1\n"
            "kind: PostgresCluster\n"
            "metadata:\n"
            "  name: checkout-db\n"
            "spec:\n"
            "  postgresVersion: 15\n"
        )
    return fake_call_llm_agent2(system_prompt, user_prompt, temperature)


def test_unmapped_requirement_generates_best_effort_fragment(monkeypatch):
    monkeypatch.setattr(a1, "call_llm", fake_call_llm_agent1_unmapped)
    monkeypatch.setattr(a2, "call_llm", fake_call_llm_agent2_with_unmapped_fragment)

    pipeline = build_pipeline()
    state = PipelineState.model_validate(
        pipeline.invoke(PipelineState(user_request="Déploie checkout-api + un opérateur Postgres..."))
    )

    assert state.error is None, state.error
    assert "PostgresCluster" in state.manifest_final_yaml
    assert "GÉNÉRATION LIBRE" in state.manifest_v1_yaml
    assert "checkout-api" in state.manifest_final_yaml
    assert "kind: Deployment" in state.manifest_final_yaml


def test_unmapped_requirement_is_surfaced_in_audit_report(monkeypatch, tmp_path):
    monkeypatch.setattr(a1, "call_llm", fake_call_llm_agent1_unmapped)
    monkeypatch.setattr(a2, "call_llm", fake_call_llm_agent2_with_unmapped_fragment)
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--output-dir", str(tmp_path / "output"),
        "Déploie checkout-api + un opérateur Postgres...",
    ])

    import main as main_module
    main_module.main()

    run_dir = next((tmp_path / "output").iterdir())
    audit = (run_dir / "audit_report.md").read_text(encoding="utf-8")

    assert "hors schéma structuré" in audit.lower() or "BEST-EFFORT" in audit
    assert "PostgresCluster" in audit
    assert "opérateur PostgreSQL" in audit
    assert "Aucun point ouvert détecté ✅" not in audit


def test_no_unmapped_requirements_still_allows_clean_audit(monkeypatch, tmp_path):
    """Vérifie l'absence de régression : sans unmapped_requirements, le
    pipeline peut toujours légitimement afficher un audit propre."""
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--output-dir", str(tmp_path / "output"), "Déploie checkout-api...",
    ])

    import main as main_module
    main_module.main()

    run_dir = next((tmp_path / "output").iterdir())
    audit = (run_dir / "audit_report.md").read_text(encoding="utf-8")
    assert "hors schéma structuré" not in audit.lower()


def test_invalid_best_effort_fragment_does_not_crash_pipeline(monkeypatch):
    """Si le LLM produit un fragment SYNTAXIQUEMENT invalide (pas juste
    sémantiquement incomplet) pour l'inconnu, le pipeline doit continuer
    normalement (mise en quarantaine), pas planter sur le manifeste entier."""
    def fake_agent2_broken_fragment(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "Exigences non standard" in user_prompt:
            # Syntaxiquement invalide (crochet jamais fermé) -- pas
            # seulement sémantiquement incomplet (ce cas-là, YAML valide
            # mais manifeste incomplet, est couvert par check_required_fields
            # en aval, un cas différent et déjà testé ailleurs).
            return "kind: [unclosed\n  nested: {also unclosed"
        return fake_call_llm_agent2(system_prompt, user_prompt, temperature)

    monkeypatch.setattr(a1, "call_llm", fake_call_llm_agent1_unmapped)
    monkeypatch.setattr(a2, "call_llm", fake_agent2_broken_fragment)

    pipeline = build_pipeline()
    state = PipelineState.model_validate(
        pipeline.invoke(PipelineState(user_request="Déploie checkout-api + un truc inconnu..."))
    )

    assert state.error is None, state.error
    assert "checkout-api" in state.manifest_final_yaml
    assert "GÉNÉRATION LIBRE INVALIDE" in state.manifest_v1_yaml


def test_semantically_incomplete_best_effort_fragment_is_flagged_not_hidden(monkeypatch):
    """Cas différent du précédent : un fragment SYNTAXIQUEMENT valide mais
    incomplet (pas de kind/apiVersion) n'est PAS mis en quarantaine (ce
    n'est pas le rôle de la quarantaine, réservée aux erreurs de parsing) —
    il doit rester visible tel quel et être signalé par les contrôles
    déterministes habituels (check_required_fields), sans crash."""
    def fake_agent2_incomplete_fragment(system_prompt, user_prompt, temperature=None, agent_name="unknown"):
        if "Exigences non standard" in user_prompt:
            return "juste: une-map-sans-kind-ni-apiversion"
        return fake_call_llm_agent2(system_prompt, user_prompt, temperature)

    monkeypatch.setattr(a1, "call_llm", fake_call_llm_agent1_unmapped)
    monkeypatch.setattr(a2, "call_llm", fake_agent2_incomplete_fragment)

    pipeline = build_pipeline()
    state = PipelineState.model_validate(
        pipeline.invoke(PipelineState(user_request="Déploie checkout-api + un truc inconnu..."))
    )

    assert state.error is None, state.error
    assert "checkout-api" in state.manifest_final_yaml
    assert "GÉNÉRATION LIBRE INVALIDE" not in state.manifest_v1_yaml  # pas une erreur de syntaxe
    # Signalé par le rapport Agent 5 (fields_left_open), pas silencieux
    agent5_report = next(r for r in state.reports if r.agent_name == "Agent 5 - Vérification finale")
    assert any("apiVersion" in f or "kind" in f for f in agent5_report.fields_left_open)
