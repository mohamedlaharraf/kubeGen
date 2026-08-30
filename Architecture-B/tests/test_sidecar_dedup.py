"""
tests/test_sidecar_dedup.py

Bug réel corrigé (4 exécutions de production sur analytics-api/dapr,
checkout-api/envoy, search-api/vault-agent) : Agent 2 traduit correctement
un sidecar à injection automatique (Dapr, Istio, Vault Agent Injector...)
par une annotation, mais Agent 3 rajoutait ensuite un conteneur manuel du
même nom, sans aucune configuration réelle (pas d'args, pas de
volumeMounts) — un doublon qui plante au démarrage ou double le proxy
réellement injecté par le webhook du cluster.

En plus du fix de prompt (agent3_system.txt), ce module fournit un filet
de sécurité DÉTERMINISTE, indépendant du LLM :
`strip_duplicate_auto_injected_sidecars`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.k8s_validate import strip_duplicate_auto_injected_sidecars  # noqa: E402


def _deployment(annotations, containers):
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "analytics-api", "namespace": "data"},
        "spec": {
            "template": {
                "metadata": {"annotations": annotations},
                "spec": {"containers": containers},
            }
        },
    }


def test_removes_bare_duplicate_dapr_sidecar():
    doc = _deployment(
        annotations={"dapr.io/enabled": "true", "dapr.io/app-id": "analytics-api"},
        containers=[
            {"name": "analytics-api", "image": "myregistry/analytics:2.0",
             "ports": [{"containerPort": 8080}]},
            {"name": "dapr", "image": "daprio/dapr:1.13.0"},
        ],
    )
    docs = [doc]
    removed = strip_duplicate_auto_injected_sidecars(docs)
    containers = docs[0]["spec"]["template"]["spec"]["containers"]

    assert len(removed) == 1
    assert len(containers) == 1
    assert containers[0]["name"] == "analytics-api"


def test_preserves_a_genuinely_configured_sidecar():
    """Un sidecar avec une vraie config (args/volumeMounts) n'est jamais
    retiré, même s'il porte un nom connu et qu'une annotation d'injection
    est présente — on ne veut pas de faux positif sur un choix
    délibéré."""
    doc = _deployment(
        annotations={"sidecar.istio.io/inject": "true"},
        containers=[
            {"name": "checkout-api", "image": "myregistry/checkout:2.0"},
            {
                "name": "envoy",
                "image": "envoyproxy/envoy:v1.29.0",
                "args": ["-c", "/etc/envoy/envoy.yaml"],
                "volumeMounts": [{"name": "envoy-config", "mountPath": "/etc/envoy"}],
            },
        ],
    )
    docs = [doc]
    removed = strip_duplicate_auto_injected_sidecars(docs)

    assert removed == []
    assert len(docs[0]["spec"]["template"]["spec"]["containers"]) == 2


def test_noop_without_auto_injection_annotation():
    doc = _deployment(annotations={}, containers=[
        {"name": "worker", "image": "myregistry/worker:1.5"},
    ])
    docs = [doc]
    removed = strip_duplicate_auto_injected_sidecars(docs)

    assert removed == []
    assert len(docs[0]["spec"]["template"]["spec"]["containers"]) == 1


def test_noop_on_non_workload_kind():
    doc = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "x"}, "spec": {}}
    docs = [doc]
    assert strip_duplicate_auto_injected_sidecars(docs) == []
