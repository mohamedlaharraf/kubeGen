"""
benchmark/adapters/architecture_a_single_agent.py

Adaptateur pour l'Architecture 1 (agent unique / prompt monolithique).

On importe directement `SingleAgentGenerator` depuis
`Architecture-1-single-agent/single_agent.py` (ajout du dossier au
sys.path plutôt qu'un package pip, pour ne pas avoir à toucher au code
existant de l'architecture 1).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from .base import ArchitectureAdapter, RunResult, StepTelemetry

_ARCH_A_DIR = Path(__file__).resolve().parents[2] / "Architecture-1-single-agent"
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_ARCH_A_DIR) not in sys.path:
    sys.path.insert(0, str(_ARCH_A_DIR))


class SingleAgentAdapter(ArchitectureAdapter):
    architecture_id = "A_single_agent"
    architecture_label = "Architecture A - Agent unique (monolithique)"

    def __init__(self):
        # Import différé : si jamais GOOGLE_API_KEY n'est pas défini, on veut
        # que l'erreur remonte au moment de la construction de l'adaptateur
        # (donc avant de lancer les 10 scénarios), pas au milieu du run 1/10.
        from single_agent import SingleAgentGenerator  # noqa: PLC0415

        # `output_dir` par défaut de SingleAgentGenerator est un chemin
        # RELATIF ("generated-k8s-templates"), qui se résout par rapport au
        # dossier COURANT au moment de l'exécution -- pas forcément fiable
        # si vous lancez run_benchmark.py depuis un autre dossier. On force
        # ici un chemin absolu déterministe, à la racine du repo (un seul
        # generated-k8s-templates/ partagé entre toutes les architectures,
        # avec un sous-dossier "A" pour ne pas mélanger avec B/C/D).
        self._generator = SingleAgentGenerator(
            output_dir=str(_REPO_ROOT / "benchmark" / "generated-k8s-templates" / "A")
        )
        self.model = self._generator.model

    def run(self, requirement: str, scenario_id: str, run_name: str) -> RunResult:
        start = time.time()
        try:
            result = self._generator.generate(requirement, run_name=run_name)
        except Exception as e:  # noqa: BLE001 - on isole l'échec par scénario
            return RunResult(
                architecture_id=self.architecture_id,
                architecture_label=self.architecture_label,
                scenario_id=scenario_id,
                requirement=requirement,
                model=self.model,
                manifest_yaml="",
                manifest_path=None,
                total_latency_seconds=round(time.time() - start, 3),
                steps=[StepTelemetry(
                    step_name="monolithic_generation",
                    latency_seconds=round(time.time() - start, 3),
                    failed=True,
                )],
                error=str(e),
            )

        manifest_yaml = Path(result["manifest_path"]).read_text(encoding="utf-8")

        step = StepTelemetry(
            step_name="monolithic_generation",
            latency_seconds=result["latency_seconds"],
            input_tokens=result["prompt_tokens"],
            output_tokens=result["output_tokens"],
            llm_calls=result["num_llm_calls"],
        )

        return RunResult(
            architecture_id=self.architecture_id,
            architecture_label=self.architecture_label,
            scenario_id=scenario_id,
            requirement=requirement,
            model=self.model,
            manifest_yaml=manifest_yaml,
            manifest_path=result["manifest_path"],
            total_latency_seconds=result["latency_seconds"],
            steps=[step],
        )