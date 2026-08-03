"""
benchmark/adapters/base.py

Interface commune que chaque architecture (A, B, C, D) doit implémenter
pour être benchmarkée par `run_benchmark.py`.

C'EST LE POINT D'EXTENSION PRINCIPAL : quand les architectures B
(pipeline multi-agents), C (orchestrateur+blackboard) et D
(orchestrateur+débat) seront prêtes, il suffit d'écrire un nouveau
fichier dans `benchmark/adapters/` qui expose une classe héritant de
`ArchitectureAdapter`, puis de l'enregistrer dans `ARCHITECTURE_REGISTRY`
(voir `benchmark/adapters/__init__.py`). Rien d'autre à toucher : le
reste du harnais (scénarios, validateurs, scoring énergie, pricing,
rapport) est déjà architecture-agnostique.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class StepTelemetry:
    """Télémétrie d'UN appel LLM (une étape / un agent).

    Pour l'architecture 1 (agent unique), il n'y aura qu'un seul
    StepTelemetry par run. Pour les architectures multi-agents (2, 3, 4),
    chaque agent/étape du graphe doit produire le sien, ce qui permet
    la ventilation "latence par sous-agent" demandée dans la tâche.
    """
    step_name: str
    latency_seconds: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    llm_calls: int = 1
    failed: bool = False


@dataclass
class RunResult:
    """Résultat homogène d'UN run (une architecture x un scénario)."""
    architecture_id: str          # ex: "A_single_agent"
    architecture_label: str       # ex: "Architecture 1 - Agent unique"
    scenario_id: str              # ex: "02_simple_web_app_hpa"
    requirement: str
    model: str
    manifest_yaml: str            # texte YAML brut (peut contenir plusieurs docs `---`)
    manifest_path: str | None
    total_latency_seconds: float
    steps: list[StepTelemetry] = field(default_factory=list)
    error: str | None = None      # si le run a échoué (exception capturée), le reste
                                   # des champs peut être vide/partiel

    @property
    def total_input_tokens(self) -> int:
        return sum(s.input_tokens or 0 for s in self.steps)

    @property
    def total_output_tokens(self) -> int:
        return sum(s.output_tokens or 0 for s in self.steps)

    @property
    def total_llm_calls(self) -> int:
        return sum(s.llm_calls for s in self.steps)

    @property
    def tokens_known(self) -> bool:
        """False si l'API n'a jamais renvoyé de usage_metadata exploitable
        pour au moins une étape (évite de calculer un coût faussement bas)."""
        return len(self.steps) > 0 and all(
            s.input_tokens is not None and s.output_tokens is not None for s in self.steps
        )


class ArchitectureAdapter(ABC):
    """Interface que chaque architecture doit implémenter."""

    architecture_id: str
    architecture_label: str

    @abstractmethod
    def run(self, requirement: str, scenario_id: str, run_name: str) -> RunResult:
        """Exécute l'architecture sur UNE exigence et retourne un RunResult.

        Ne doit PAS lever d'exception pour un échec "normal" (erreur API,
        YAML invalide, etc.) : capturer l'erreur et la mettre dans
        `RunResult.error` pour que le benchmark puisse continuer sur les
        autres scénarios. Une exception qui remonte est traitée comme un
        bug de l'adaptateur lui-même par `run_benchmark.py`.
        """
        raise NotImplementedError
