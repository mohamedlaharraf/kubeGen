"""
tests/test_cluster_validate.py

Teste utils/cluster_validate.py avec `subprocess.run` mocké — pas de
dépendance à un vrai binaire kubeconform/kubectl installé en CI. La
logique de parsing (notamment le bug réel rencontré : kubeconform renvoie
`status: "statusInvalid"`, pas `"invalid"`) est verrouillée par ces tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import cluster_validate as cv  # noqa: E402


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_kubeconform_unavailable_degrades_gracefully(monkeypatch):
    monkeypatch.setattr(cv, "_binary_available", lambda name: False)
    result = cv.run_kubeconform("apiVersion: v1\nkind: Namespace\n")
    assert result["available"] is False
    assert result["passed"] is None


def test_kubeconform_parses_real_status_invalid_format(monkeypatch):
    """Verrouille le bug réel : kubeconform renvoie 'statusInvalid', pas
    'invalid'. Un mauvais matching laisserait passer un YAML cassé."""
    fake_json = (
        '{"resources": [{"kind": "Deployment", "name": "api", '
        '"status": "statusInvalid", "msg": "got string, want integer"}], '
        '"summary": {"valid": 0, "invalid": 1}}'
    )

    monkeypatch.setattr(cv, "_binary_available", lambda name: True)
    monkeypatch.setattr(
        cv.subprocess, "run",
        lambda *a, **k: _FakeCompletedProcess(returncode=1, stdout=fake_json),
    )

    result = cv.run_kubeconform("some: yaml")
    assert result["available"] is True
    assert result["passed"] is False
    assert len(result["errors"]) == 1
    assert "Deployment/api" in result["errors"][0]


def test_kubeconform_valid_manifest_passes(monkeypatch):
    fake_json = '{"resources": [], "summary": {"valid": 1, "invalid": 0}}'
    monkeypatch.setattr(cv, "_binary_available", lambda name: True)
    monkeypatch.setattr(
        cv.subprocess, "run",
        lambda *a, **k: _FakeCompletedProcess(returncode=0, stdout=fake_json),
    )
    result = cv.run_kubeconform("some: yaml")
    assert result["passed"] is True
    assert result["errors"] == []


def test_dry_run_apply_unavailable_degrades_gracefully(monkeypatch):
    monkeypatch.setattr(cv, "_binary_available", lambda name: False)
    result = cv.run_dry_run_apply("some: yaml")
    assert result["available"] is False


def test_dry_run_apply_failure_captures_stderr(monkeypatch):
    monkeypatch.setattr(cv, "_binary_available", lambda name: True)
    monkeypatch.setattr(
        cv.subprocess, "run",
        lambda *a, **k: _FakeCompletedProcess(
            returncode=1, stderr="error: admission webhook denied the request\n"
        ),
    )
    result = cv.run_dry_run_apply("some: yaml")
    assert result["passed"] is False
    assert any("admission webhook" in e for e in result["errors"])


def test_check_cluster_dependencies_detects_missing_crd(monkeypatch):
    monkeypatch.setattr(cv, "_binary_available", lambda name: True)
    monkeypatch.setattr(
        cv.subprocess, "run",
        lambda *a, **k: _FakeCompletedProcess(
            returncode=0,
            stdout="customresourcedefinition.apiextensions.k8s.io/ingresses.networking.k8s.io\n",
        ),
    )
    result = cv.check_cluster_dependencies({"ScaledObject", "Ingress"})
    assert result["checked"] is True
    assert len(result["missing"]) == 1
    assert "scaledobjects.keda.sh" in result["missing"][0]


def test_check_cluster_dependencies_no_relevant_kinds_skips_check(monkeypatch):
    # Aucun kind du set n'a de CRD associée -> pas besoin d'appeler kubectl
    called = {"count": 0}

    def fake_run(*a, **k):
        called["count"] += 1
        return _FakeCompletedProcess(returncode=0, stdout="")

    monkeypatch.setattr(cv.subprocess, "run", fake_run)
    result = cv.check_cluster_dependencies({"Deployment", "Service"})
    assert result["missing"] == []
    assert called["count"] == 0
