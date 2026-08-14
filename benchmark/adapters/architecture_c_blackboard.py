"""
benchmark/adapters/architecture_c_blackboard.py

Adaptateur pour l'Architecture C (blackboard de contraintes globales +
boucle de réparation bornée). Même squelette que l'Architecture B (5
agents + LangGraph), donc même stratégie d'intégration : sous-processus,
pas import direct -- projet séparé avec ses propres dépendances
(langgraph, tenacity...).

    python main.py --file <scenario> --output-dir <dossier>

Par défaut, le chemin est déduit automatiquement de la structure du repo
(dossier frère `Architecture-3-blackboard/`) -- rien à configurer si vous
suivez la disposition standard. Ne définissez ARCH_C_DIR / ARCH_C_PYTHON_EXE
que si votre disposition diffère.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .base import ArchitectureAdapter, RunResult, StepTelemetry

_REPO_ROOT = Path(__file__).resolve().parents[2]

ARCH_C_DIR = Path(
    os.getenv("ARCH_C_DIR") or (_REPO_ROOT / "Architecture-3-blackboard")
)


def _detect_python() -> str:
    override = os.getenv("ARCH_C_PYTHON_EXE")
    if override:
        return override
    candidates = [
        ARCH_C_DIR / "venv" / "Scripts" / "python.exe",
        ARCH_C_DIR / "venv" / "bin" / "python",
        ARCH_C_DIR / ".venv" / "Scripts" / "python.exe",
        ARCH_C_DIR / ".venv" / "bin" / "python",
        _REPO_ROOT / "venv" / "Scripts" / "python.exe",
        _REPO_ROOT / "venv" / "bin" / "python",
        _REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        _REPO_ROOT / ".venv" / "bin" / "python",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return sys.executable


ARCH_C_PYTHON_EXE = _detect_python()


def _utf8_env() -> dict:
    """Même correctif que pour l'Architecture B : sur Windows, un
    sous-processus dont stdout/stderr sont capturés via un pipe (pas un
    vrai terminal) retombe sur l'encodage ANSI du système, qui ne sait pas
    encoder les caractères '✖'/'⚠'/'✔' que ce projet imprime -- sans ce
    correctif, le sous-processus plante côté ENFANT avant même de produire
    la moindre sortie exploitable."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _deps_available() -> bool:
    try:
        out = subprocess.run(
            [ARCH_C_PYTHON_EXE, "-c", "import langgraph"],
            capture_output=True, timeout=15, env=_utf8_env(),
        )
        return out.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _extract_audit_error(audit_path: Path) -> str | None:
    """Même mécanisme que pour B : la vraie raison d'un échec (state.error)
    est écrite dans audit_report.md, plus fiable que de parser stdout/
    stderr du sous-processus."""
    if not audit_path.exists():
        return None
    text = audit_path.read_text(encoding="utf-8")
    marker = "## ⚠️ Le pipeline s'est arrêté en erreur"
    idx = text.find(marker)
    if idx == -1:
        return None
    return text[idx + len(marker):].strip()[:1500]


_MANIFEST_STAGES = [
    "agent5_manifest_final.yaml",  # reflète déjà toute réparation ciblée
                                    # appliquée : run_repair écrit dans le
                                    # même state.manifest_final_yaml
                                    # qu'Agent 5, voir agents/agent_repair.py
    "agent4_energie.yaml",
    "agent3_validated.yaml",
    "agent2_template.yaml",
]


class BlackboardAdapter(ArchitectureAdapter):
    architecture_id = "C_blackboard"
    architecture_label = "Architecture C - Blackboard + réparation bornée"

    def __init__(self):
        main_py = ARCH_C_DIR / "main.py"
        if not main_py.exists():
            raise FileNotFoundError(
                f"Architecture-3-blackboard introuvable à {ARCH_C_DIR} "
                f"(main.py absent). Définissez ARCH_C_DIR ou éditez la "
                f"constante en tête de architecture_c_blackboard.py."
            )
        if not _deps_available():
            print(
                f"[avertissement] 'langgraph' non importable avec "
                f"{ARCH_C_PYTHON_EXE} -- l'architecture C échouera "
                f"probablement. Définissez ARCH_C_PYTHON_EXE vers "
                f"l'interpréteur qui a les dépendances de "
                f"Architecture-3-blackboard/requirements.txt installées."
            )
        self.model = self._read_model_name()

    def _read_model_name(self) -> str:
        try:
            out = subprocess.run(
                [ARCH_C_PYTHON_EXE, "-c",
                 "from config import settings; print(settings.GEMMA_MODEL)"],
                cwd=ARCH_C_DIR, capture_output=True, text=True, timeout=15,
                env=_utf8_env(),
            )
            return out.stdout.strip() or "unknown"
        except Exception:  # noqa: BLE001
            return "unknown"

    def run(self, requirement: str, scenario_id: str, run_name: str) -> RunResult:
        start = time.time()

        with tempfile.TemporaryDirectory(prefix=f"bench_{scenario_id}_") as tmp:
            tmp_dir = Path(tmp)
            req_file = tmp_dir / "requirement.txt"
            req_file.write_text(requirement, encoding="utf-8")
            out_dir = tmp_dir / "output"

            proc = subprocess.run(
                [ARCH_C_PYTHON_EXE, "main.py",
                 "--file", str(req_file), "--output-dir", str(out_dir)],
                cwd=ARCH_C_DIR, capture_output=True, text=True,
                encoding="utf-8", errors="replace", env=_utf8_env(),
            )
            elapsed = round(time.time() - start, 3)

            run_dirs = list(out_dir.glob("run_*")) if out_dir.exists() else []
            if not run_dirs:
                return RunResult(
                    architecture_id=self.architecture_id,
                    architecture_label=self.architecture_label,
                    scenario_id=scenario_id, requirement=requirement, model=self.model,
                    manifest_yaml="", manifest_path=None, total_latency_seconds=elapsed,
                    steps=[StepTelemetry(step_name="pipeline_total", latency_seconds=elapsed, failed=True)],
                    error=(
                        f"Aucun dossier run_* produit.\n"
                        f"stdout (fin): {proc.stdout[-800:]}\n"
                        f"stderr (fin): {proc.stderr[-500:]}"
                    ),
                )
            run_dir = run_dirs[0]

            # Un StepTelemetry par agent -- INCLUT les passages du noeud
            # "Réparation ciblée" (potentiellement plusieurs, un par
            # tentative de boucle), puisque `by_agent` est déjà générique
            # par `agent_name` côté execution_metrics.json. C'est ce qui
            # permet, dans le rapport du benchmark, de voir concrètement
            # combien la boucle de réparation a coûté en tokens/latence
            # par rapport à l'Architecture B qui n'a jamais ce coût.
            steps: list[StepTelemetry] = []
            metrics_file = run_dir / "execution_metrics.json"
            if metrics_file.exists():
                metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
                for agent_name, agent_metrics in metrics.get("llm_calls", {}).get("by_agent", {}).items():
                    steps.append(StepTelemetry(
                        step_name=agent_name,
                        latency_seconds=agent_metrics.get("latency_seconds", 0.0),
                        input_tokens=agent_metrics.get("prompt_tokens") if agent_metrics.get("tokens_known") else None,
                        output_tokens=agent_metrics.get("completion_tokens") if agent_metrics.get("tokens_known") else None,
                        llm_calls=agent_metrics.get("calls", 1),
                        failed=agent_metrics.get("failed_calls", 0) > 0,
                    ))
            if not steps:
                steps.append(StepTelemetry(step_name="pipeline_total", latency_seconds=elapsed))

            manifest_yaml = ""
            manifest_path = None
            for stage_file in _MANIFEST_STAGES:
                candidate = run_dir / stage_file
                if candidate.exists():
                    manifest_yaml = candidate.read_text(encoding="utf-8")
                    manifest_path = str(candidate)
                    break

            persisted_dir = _REPO_ROOT / "benchmark" / "generated-k8s-templates" / "C" / run_name
            persisted_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(run_dir, persisted_dir, dirs_exist_ok=True)
            if manifest_path is not None:
                manifest_path = str(persisted_dir / Path(manifest_path).name)

            pipeline_error = None
            if proc.returncode not in (0,):
                audit_error = _extract_audit_error(run_dir / "audit_report.md")
                if audit_error:
                    pipeline_error = f"main.py a retourné le code {proc.returncode} : {audit_error}"
                else:
                    pipeline_error = (
                        f"main.py a retourné le code {proc.returncode}, et "
                        f"audit_report.md est absent ou sans section d'erreur "
                        f"reconnaissable ({run_dir / 'audit_report.md'}).\n"
                        f"stdout (fin): {proc.stdout[-800:]}\n"
                        f"stderr (fin): {proc.stderr[-500:]}"
                    )

            return RunResult(
                architecture_id=self.architecture_id,
                architecture_label=self.architecture_label,
                scenario_id=scenario_id,
                requirement=requirement,
                model=self.model,
                manifest_yaml=manifest_yaml,
                manifest_path=manifest_path,
                total_latency_seconds=elapsed,
                steps=steps,
                error=pipeline_error,
            )