"""
tests/test_main_cli.py

Vérifie le comportement CLI demandé :
1. Chaque run crée son propre sous-dossier horodaté (run_YYYYMMDD_HHMMSS_ffffff)
   dans le dossier de sortie.
2. La sortie de CHAQUE agent est sauvegardée séparément (JSON pour
   l'Agent 1, YAML pour les Agents 2 à 5).
3. En cas d'erreur en cours de pipeline, les sorties déjà produites sont
   quand même écrites sur disque (utile pour déboguer).

Réutilise les mocks LLM "component-aware" de tests/test_pipeline.py (même
FAKE_SPEC à un composant + sidecar) plutôt que de les dupliquer.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import agents.agent1_analyse as a1  # noqa: E402
import agents.agent2_template as a2  # noqa: E402
import agents.agent3_validation as a3  # noqa: E402
import agents.agent4_energie as a4  # noqa: E402
import agents.agent5_verification as a5  # noqa: E402
import main as main_module  # noqa: E402

from tests.test_pipeline import (  # noqa: E402
    fake_call_llm_agent1,
    fake_call_llm_agent2,
    fake_call_llm_agent3,
    fake_call_llm_agent4,
    fake_call_llm_agent5,
)

RUN_DIR_PATTERN = re.compile(r"^run_\d{8}_\d{6}_\d{6}$")


@pytest.fixture(autouse=True)
def patch_llm(monkeypatch):
    monkeypatch.setattr(a1, "call_llm", fake_call_llm_agent1)
    monkeypatch.setattr(a2, "call_llm", fake_call_llm_agent2)
    monkeypatch.setattr(a3, "call_llm", fake_call_llm_agent3)
    monkeypatch.setattr(a4, "call_llm", fake_call_llm_agent4)
    monkeypatch.setattr(a5, "call_llm", fake_call_llm_agent5)


def _run_cli(tmp_path, monkeypatch, argv_extra):
    output_root = tmp_path / "output"
    argv = ["main.py", "--output-dir", str(output_root)] + argv_extra
    monkeypatch.setattr(sys, "argv", argv)
    return output_root


def test_creates_one_timestamped_run_dir_per_execution(tmp_path, monkeypatch):
    output_root = _run_cli(tmp_path, monkeypatch, ["Déploie checkout-api..."])

    main_module.main()  # pas d'erreur -> ne doit PAS lever SystemExit

    run_dirs = list(output_root.iterdir())
    assert len(run_dirs) == 1
    assert RUN_DIR_PATTERN.match(run_dirs[0].name)


def test_run_dir_naming_and_per_agent_files(tmp_path, monkeypatch):
    output_root = _run_cli(tmp_path, monkeypatch, ["Déploie checkout-api..."])
    try:
        main_module.main()
    except SystemExit:
        pass

    run_dirs = list(output_root.iterdir())
    assert len(run_dirs) == 1, "Un seul sous-dossier de run doit être créé"
    run_dir = run_dirs[0]
    assert RUN_DIR_PATTERN.match(run_dir.name), f"Nom de dossier inattendu : {run_dir.name}"

    expected_files = {
        "00_request.txt",
        "agent1_normalized_spec.json",
        "agent2_template.yaml",
        "agent3_validated.yaml",
        "agent4_energie.yaml",
        "agent5_manifest_final.yaml",
        "audit_report.md",
    }
    actual_files = {f.name for f in run_dir.iterdir()}
    assert expected_files.issubset(actual_files)

    # Contenu minimal sanity-check
    assert "checkout-api" in (run_dir / "agent1_normalized_spec.json").read_text(encoding="utf-8")
    assert "Deployment" in (run_dir / "agent2_template.yaml").read_text(encoding="utf-8")
    assert "envoy-proxy" in (run_dir / "agent2_template.yaml").read_text(encoding="utf-8")  # sidecar bien présent
    assert "HorizontalPodAutoscaler" in (run_dir / "agent4_energie.yaml").read_text(encoding="utf-8")

    audit = (run_dir / "audit_report.md").read_text(encoding="utf-8")
    assert "microservices" not in audit  # architecture "single" ici
    assert "checkout-api" in audit


def test_two_runs_do_not_overwrite_each_other(tmp_path, monkeypatch):
    output_root = _run_cli(tmp_path, monkeypatch, ["Déploie checkout-api..."])
    try:
        main_module.main()
    except SystemExit:
        pass

    # Deuxième run, même dossier racine
    monkeypatch.setattr(sys, "argv", ["main.py", "--output-dir", str(output_root), "Déploie autre-api..."])
    try:
        main_module.main()
    except SystemExit:
        pass

    run_dirs = list(output_root.iterdir())
    assert len(run_dirs) == 2, "Deux exécutions doivent créer deux dossiers distincts"


def test_partial_outputs_saved_on_error(tmp_path, monkeypatch):
    """Si le pipeline s'arrête en erreur, les sorties déjà produites (par
    les agents qui ont tourné avant l'échec) doivent quand même être
    écrites sur disque."""

    def broken_agent3(system_prompt, user_prompt, temperature=None):
        return "ceci n'est pas du json valide"

    monkeypatch.setattr(a3, "call_llm", broken_agent3)

    output_root = _run_cli(tmp_path, monkeypatch, ["Déploie checkout-api..."])
    with pytest.raises(SystemExit) as exc_info:
        main_module.main()
    assert exc_info.value.code == 2  # code d'erreur du pipeline

    run_dir = next(output_root.iterdir())
    files = {f.name for f in run_dir.iterdir()}

    # Agent 1 et 2 ont réussi -> leurs sorties doivent être présentes
    assert "agent1_normalized_spec.json" in files
    assert "agent2_template.yaml" in files
    # Agent 3 a échoué -> pas de sortie pour lui ni les suivants
    assert "agent3_validated.yaml" not in files
    assert "agent4_energie.yaml" not in files
    assert "agent5_manifest_final.yaml" not in files
    # Le rapport d'audit doit quand même exister et mentionner l'erreur
    assert "audit_report.md" in files
    audit_content = (run_dir / "audit_report.md").read_text(encoding="utf-8")
    assert "erreur" in audit_content.lower()
