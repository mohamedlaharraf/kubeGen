"""
benchmark/adapters/architecture_b_pipeline.py

Adaptateur pour l'Architecture B (pipeline séquentiel à 5 agents).

Le pipeline vit dans `Architecture-2-pipeline/`, un dossier frère de
`Architecture-1-single-agent/` (même repo). Il a ses propres
dépendances (langgraph, tenacity, etc.) que l'Architecture A n'a pas
besoin d'avoir, donc on l'invoque en sous-processus plutôt qu'en import
direct :

    python main.py --file <scenario> --output-dir <dossier>

Par défaut, le chemin est déduit automatiquement de la structure du
repo (comme pour l'Architecture A) -- rien à configurer si vous suivez
la disposition standard `Architecture-2-pipeline/` à la racine du repo.
Ne définissez PIPELINE_KUBEGEN_DIR / PIPELINE_PYTHON_EXE que si votre
disposition diffère (ex: pipeline dans un repo complètement séparé).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .base import ArchitectureAdapter, RunResult, StepTelemetry

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Dossier racine du pipeline (celui qui contient main.py). Auto-détecté :
# dossier frère "Architecture-2-pipeline/" à la racine du repo. Surchargeable
# via PIPELINE_KUBEGEN_DIR si votre disposition est différente.
PIPELINE_KUBEGEN_DIR = Path(
    os.getenv("PIPELINE_KUBEGEN_DIR") or (_REPO_ROOT / "Architecture-2-pipeline")
)

# Interpréteur Python à utiliser pour lancer le pipeline. Auto-détection,
# dans l'ordre : PIPELINE_PYTHON_EXE (env) -> venv dédié dans
# Architecture-2-pipeline/ -> venv/.venv partagé à la racine du repo ->
# l'interpréteur courant (fonctionne si toutes les dépendances des deux
# architectures sont installées dans le même environnement).
def _detect_pipeline_python() -> str:
    override = os.getenv("PIPELINE_PYTHON_EXE")
    if override:
        return override
    candidates = [
        PIPELINE_KUBEGEN_DIR / "venv" / "Scripts" / "python.exe",   # venv dédié, Windows
        PIPELINE_KUBEGEN_DIR / "venv" / "bin" / "python",           # venv dédié, macOS/Linux
        PIPELINE_KUBEGEN_DIR / ".venv" / "Scripts" / "python.exe",
        PIPELINE_KUBEGEN_DIR / ".venv" / "bin" / "python",
        _REPO_ROOT / "venv" / "Scripts" / "python.exe",              # venv partagé à la racine
        _REPO_ROOT / "venv" / "bin" / "python",
        _REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        _REPO_ROOT / ".venv" / "bin" / "python",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return sys.executable  # dernier recours -- peut ne pas avoir langgraph/tenacity installés


PIPELINE_PYTHON_EXE = _detect_pipeline_python()


def _utf8_env() -> dict:
    """Env pour les sous-processus qui force l'UTF-8 côté enfant.

    Sur Windows, quand stdout/stderr d'un sous-processus sont capturés via
    un pipe (pas un vrai terminal), Python retombe sur l'encodage ANSI du
    système (souvent cp1252) au lieu d'UTF-8 -- et pipeline-kubegen imprime
    des caractères comme '✖'/'⚠'/'✔' qui n'existent pas en cp1252, ce qui
    fait planter le PROCESSUS ENFANT avec un UnicodeEncodeError avant même
    d'avoir produit de sortie. PYTHONIOENCODING force l'UTF-8 quel que soit
    le contexte d'exécution (tty ou pipe)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _pipeline_deps_available() -> bool:
    """Vérifie concrètement que langgraph est importable avec l'interpréteur
    choisi, plutôt que de deviner à partir du chemin (qui peut légitimement
    être sys.executable si vous utilisez un seul venv partagé pour tout le
    repo -- dans ce cas, un avertissement basé uniquement sur l'égalité de
    chemin serait un faux positif)."""
    try:
        out = subprocess.run(
            [PIPELINE_PYTHON_EXE, "-c", "import langgraph"],
            capture_output=True, timeout=15, env=_utf8_env(),
        )
        return out.returncode == 0
    except Exception:  # noqa: BLE001
        return False

def _extract_audit_error(audit_path: Path) -> str | None:
    """Le pipeline écrit la vraie raison de l'échec (le `state.error` de
    `graph.py`) dans audit_report.md, sous le titre '## ⚠️ Le pipeline
    s'est arrêté en erreur' -- c'est plus fiable que de parser stdout/
    stderr du sous-processus, dont l'encodage/le formatage rich peut
    varier selon le terminal."""
    if not audit_path.exists():
        return None
    text = audit_path.read_text(encoding="utf-8")
    marker = "## ⚠️ Le pipeline s'est arrêté en erreur"
    idx = text.find(marker)
    if idx == -1:
        return None
    return text[idx + len(marker):].strip()[:1500]
# En cas d'échec partiel (voir vos logs précédents), le pipeline peut
# s'arrêter avant d'écrire agent5_manifest_final.yaml -- on prend alors
# le dernier stade disponible plutôt que de déclarer le run vide.
_MANIFEST_STAGES = [
    "agent5_manifest_final.yaml",
    "agent4_energie.yaml",
    "agent3_validated.yaml",
    "agent2_template.yaml",
]


class PipelineAdapter(ArchitectureAdapter):
    architecture_id = "B_pipeline"
    architecture_label = "Architecture B - Pipeline séquentiel (5 agents)"

    def __init__(self):
        main_py = PIPELINE_KUBEGEN_DIR / "main.py"
        if not main_py.exists():
            raise FileNotFoundError(
                f"pipeline-kubegen introuvable à {PIPELINE_KUBEGEN_DIR} "
                f"(main.py absent). Définissez PIPELINE_KUBEGEN_DIR ou éditez "
                f"la constante en tête de architecture_b_pipeline.py."
            )
        if not _pipeline_deps_available():
            print(
                f"[avertissement] 'langgraph' non importable avec "
                f"{PIPELINE_PYTHON_EXE} -- l'architecture B échouera "
                f"probablement. Définissez PIPELINE_PYTHON_EXE vers "
                f"l'interpréteur qui a les dépendances de "
                f"Architecture-2-pipeline/requirements.txt installées."
            )
        self.model = self._read_model_name()

    def _read_model_name(self) -> str:
        try:
            out = subprocess.run(
                [PIPELINE_PYTHON_EXE, "-c",
                 "from config import settings; print(settings.GEMMA_MODEL)"],
                cwd=PIPELINE_KUBEGEN_DIR, capture_output=True, text=True, timeout=15,
                env=_utf8_env(),
            )
            return out.stdout.strip() or "unknown"
        except Exception:  # noqa: BLE001
            return "unknown"

    def run(self, requirement: str, scenario_id: str, run_name: str) -> RunResult:
        start = time.time()

        # Fichier temporaire pour l'exigence + dossier de sortie DÉDIÉ à ce
        # run (pas le output/ partagé du pipeline) : le nom du sous-dossier
        # run_YYYYMMDD_HHMMSS_ffffff est généré par main.py lui-même, donc
        # le seul moyen fiable de le retrouver est de s'assurer qu'il est
        # seul dans ce dossier temporaire.
        import tempfile
        with tempfile.TemporaryDirectory(prefix=f"bench_{scenario_id}_") as tmp:
            tmp_dir = Path(tmp)
            req_file = tmp_dir / "requirement.txt"
            req_file.write_text(requirement, encoding="utf-8")
            out_dir = tmp_dir / "output"

            proc = subprocess.run(
                [PIPELINE_PYTHON_EXE, "main.py",
                 "--file", str(req_file), "--output-dir", str(out_dir)],
                cwd=PIPELINE_KUBEGEN_DIR, capture_output=True, text=True,
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

            # Métriques par agent -> un StepTelemetry par agent (contrairement
            # à l'Architecture A qui n'en a qu'un seul).
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
                # Pas de télémétrie détaillée dispo -- au moins un step global
                # pour ne pas perdre totalement la latence mesurée ici.
                steps.append(StepTelemetry(step_name="pipeline_total", latency_seconds=elapsed))

            manifest_yaml = ""
            manifest_path = None
            for stage_file in _MANIFEST_STAGES:
                candidate = run_dir / stage_file
                if candidate.exists():
                    manifest_yaml = candidate.read_text(encoding="utf-8")
                    manifest_path = str(candidate)
                    break

            # `run_dir` vit dans un TemporaryDirectory qui va être effacé à
            # la sortie du `with` -- rien ne persiste sur disque par défaut,
            # contrairement à l'Architecture A qui écrit toujours dans
            # generated-k8s-templates/. On copie donc tout le contenu du run
            # (manifeste(s), audit_report.md, execution_metrics.json, etc.)
            # vers un dossier permanent AVANT que le tempdir ne disparaisse,
            # dans le même esprit que l'Architecture A : un sous-dossier par
            # run, à un emplacement déterministe (indépendant du CWD depuis
            # lequel run_benchmark.py est lancé).
            persisted_dir = _REPO_ROOT / "benchmark" / "generated-k8s-templates" / "B" / run_name
            persisted_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(run_dir, persisted_dir, dirs_exist_ok=True)
            if manifest_path is not None:
                # Redirige manifest_path vers la copie persistante (le
                # fichier temporaire d'origine n'existera plus après le
                # `with`) -- le contenu YAML lui-même reste déjà capturé
                # dans manifest_yaml quoi qu'il arrive.
                manifest_path = str(persisted_dir / Path(manifest_path).name)

            pipeline_error = None
            if proc.returncode not in (0,):
                # returncode 2 chez pipeline-kubegen = échec partiel avec
                # sorties partielles (voir graph.py/_guard) -- on le note
                # comme erreur du run, mais on garde le manifeste partiel
                # trouvé ci-dessus si applicable pour la validation quand même.
                audit_error = _extract_audit_error(run_dir / "audit_report.md")
                if audit_error:
                    pipeline_error = f"main.py a retourné le code {proc.returncode} : {audit_error}"
                else:
                    # audit_report.md absent/sans la section attendue -- on
                    # inclut stdout ET stderr (pas seulement stderr : les
                    # messages rich '✖ Pipeline: ...' du pipeline vont sur
                    # stdout par défaut, pas stderr).
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