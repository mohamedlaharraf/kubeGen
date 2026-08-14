"""
tests/test_sidecar_injection_consistency.py

Bug réel de production : l'Agent 2 traduisait un sidecar Dapr en
annotations (`dapr.io/enabled`, etc.) SANS conteneur manuel -- décision
correcte, documentée dans son propre prompt. Mais l'Agent 3 (validation)
et l'Agent 5 (vérification finale) avaient chacun leur propre règle
générique "un sidecar déclaré doit apparaître comme conteneur", sans
connaître cette décision : l'un d'eux réintroduisait le conteneur manuel,
créant un doublon (annotations + conteneur) avec l'injecteur Dapr réel du
cluster.

Ces tests verrouillent la correction :
1. `utils/sidecar_injection.classify_sidecar` reconnaît bien Dapr/Istio/
   Linkerd/Consul Connect et laisse les autres sidecars en mode
   "manual_container" (comportement inchangé pour un sidecar inconnu).
2. `build_injection_mode_map` produit le mapping partagé attendu.
3. `_strip_duplicate_auto_inject_containers` (filet de sécurité
   déterministe utilisé par l'Agent 3 ET l'Agent 5) retire bien tout
   conteneur manuel correspondant à un sidecar en mode "annotations",
   sans toucher au reste du manifeste, et ne touche à RIEN si le
   sidecar est en mode "manual_container" (pas de faux positif).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.sidecar_injection import (  # noqa: E402
    classify_sidecar,
    build_injection_mode_map,
    ANNOTATIONS,
    MANUAL_CONTAINER,
)
from agents.agent3_validation import _strip_duplicate_auto_inject_containers  # noqa: E402


class _FakePort:
    def __init__(self, port):
        self.container_port = port


class _FakeSidecar:
    def __init__(self, name, purpose, port=None):
        self.name = name
        self.purpose = purpose
        self.ports = [_FakePort(port)] if port else []


def test_classify_known_auto_inject_sidecars():
    assert classify_sidecar("dapr-sidecar", "pub/sub via Dapr") == "dapr"
    assert classify_sidecar("mesh", "sidecar Istio") == "istio"
    assert classify_sidecar("proxy", "linkerd data plane") == "linkerd"
    assert classify_sidecar("connect", "Consul Connect proxy") == "consul_connect"


def test_classify_unknown_sidecar_stays_manual():
    assert classify_sidecar("log-shipper", "collecteur de logs vers stdout") is None


def test_build_injection_mode_map_mixed():
    sidecars = [
        _FakeSidecar("dapr-sidecar", "pub/sub via Dapr", port=3500),
        _FakeSidecar("log-shipper", "collecteur de logs"),
    ]
    mode_map = build_injection_mode_map(sidecars, "analytics-api")

    assert mode_map["dapr-sidecar"]["mode"] == ANNOTATIONS
    assert mode_map["dapr-sidecar"]["annotations"]["dapr.io/app-id"] == "analytics-api"
    assert mode_map["dapr-sidecar"]["annotations"]["dapr.io/app-port"] == "3500"
    assert mode_map["dapr-sidecar"]["requires_operator"]

    assert mode_map["log-shipper"]["mode"] == MANUAL_CONTAINER
    assert mode_map["log-shipper"]["annotations"] is None


_MANIFEST_WITH_DUPLICATE_DAPR = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: analytics-api
  namespace: data
spec:
  template:
    metadata:
      annotations:
        dapr.io/enabled: "true"
        dapr.io/app-id: analytics-api
    spec:
      containers:
      - name: analytics-api
        image: myregistry/analytics:2.0
      - name: dapr-sidecar
        image: daprio/daprd:1.12.0
"""


def test_strip_removes_duplicate_auto_inject_container():
    injection_mode = {
        "analytics-api": {
            "dapr-sidecar": {"mode": ANNOTATIONS, "annotations": {}, "requires_operator": "Dapr"}
        }
    }
    fixed_yaml, notes = _strip_duplicate_auto_inject_containers(
        _MANIFEST_WITH_DUPLICATE_DAPR, injection_mode
    )
    assert notes, "une note de correction doit être produite"
    assert "dapr-sidecar" not in fixed_yaml
    assert "analytics-api" in fixed_yaml  # le conteneur principal doit rester intact
    assert "dapr.io/enabled" in fixed_yaml  # les annotations doivent rester intactes


def test_strip_does_not_touch_manual_container_sidecars():
    injection_mode = {
        "analytics-api": {
            "dapr-sidecar": {"mode": MANUAL_CONTAINER, "annotations": None, "requires_operator": None}
        }
    }
    fixed_yaml, notes = _strip_duplicate_auto_inject_containers(
        _MANIFEST_WITH_DUPLICATE_DAPR, injection_mode
    )
    assert notes == []
    assert "dapr-sidecar" in fixed_yaml  # rien n'est retiré : mode manuel = comportement inchangé


def test_strip_noop_without_injection_mode():
    fixed_yaml, notes = _strip_duplicate_auto_inject_containers(
        _MANIFEST_WITH_DUPLICATE_DAPR, {}
    )
    assert notes == []
    assert fixed_yaml == _MANIFEST_WITH_DUPLICATE_DAPR


if __name__ == "__main__":
    test_classify_known_auto_inject_sidecars()
    test_classify_unknown_sidecar_stays_manual()
    test_build_injection_mode_map_mixed()
    test_strip_removes_duplicate_auto_inject_container()
    test_strip_does_not_touch_manual_container_sidecars()
    test_strip_noop_without_injection_mode()
    print("Tous les tests sidecar_injection sont passés.")
