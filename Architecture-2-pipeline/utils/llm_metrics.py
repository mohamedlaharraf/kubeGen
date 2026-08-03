"""
utils/llm_metrics.py — collecte de métriques d'exécution du pipeline :
latence, nombre d'appels LLM, tokens consommés.

Un seul collecteur global (`_collector`), remis à zéro explicitement au
début de chaque run par `main.py` (`reset()`), puis lu à la fin
(`summary()`) pour produire le rapport. Volontairement global plutôt que
transmis dans `PipelineState` : les agents appellent `call_llm` directement
sans jamais passer par le state pour ça, et faire remonter cette
plomberie dans chaque signature d'agent aurait pollué leur rôle métier
pour un besoin purement transverse (même logique que `logging_utils`).

IMPORTANT pour la lecture des tests : les tests du pipeline (`test_pipeline.py`,
`test_main_cli.py`...) mockent `call_llm` directement au niveau de chaque
module agent (`agents.agentN_xxx.call_llm = fake_...`), donc l'instrumentation
réelle définie ici (dans `llm_client.py`) n'est PAS exercée par ces tests —
c'est attendu, pas un oubli. Ce module a ses propres tests dédiés
(`tests/test_llm_metrics.py`) qui mockent au niveau `_generate`, un cran
plus bas, pour exercer réellement le chemin d'instrumentation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class LLMCallRecord:
    agent: str
    latency_seconds: float
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    succeeded: bool
    timestamp: float = field(default_factory=time.time)


class LLMMetricsCollector:
    def __init__(self) -> None:
        self.calls: list[LLMCallRecord] = []

    def reset(self) -> None:
        self.calls = []

    def record(self, agent: str, latency_seconds: float,
               prompt_tokens: int | None, completion_tokens: int | None,
               succeeded: bool = True) -> None:
        total = None
        if prompt_tokens is not None and completion_tokens is not None:
            total = prompt_tokens + completion_tokens
        self.calls.append(LLMCallRecord(
            agent=agent, latency_seconds=latency_seconds,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_tokens=total, succeeded=succeeded,
        ))

    def summary(self) -> dict:
        """
        Résumé agrégé, toujours structurellement présent (même à 0 appel,
        ex: mode offline ou tests avec LLM mocké au niveau agent) — pour
        que le rapport d'exécution n'ait jamais besoin d'un cas particulier
        "pas de métriques disponibles".
        """
        n = len(self.calls)
        total_latency = sum(c.latency_seconds for c in self.calls)
        known_token_calls = [c for c in self.calls if c.total_tokens is not None]
        total_prompt = sum(c.prompt_tokens or 0 for c in known_token_calls)
        total_completion = sum(c.completion_tokens or 0 for c in known_token_calls)

        by_agent: dict[str, dict] = {}
        for c in self.calls:
            b = by_agent.setdefault(c.agent, {
                "calls": 0, "failed_calls": 0, "latency_seconds": 0.0,
                "prompt_tokens": 0, "completion_tokens": 0, "tokens_known": False,
            })
            b["calls"] += 1
            if not c.succeeded:
                b["failed_calls"] += 1
            b["latency_seconds"] += c.latency_seconds
            if c.total_tokens is not None:
                b["prompt_tokens"] += c.prompt_tokens or 0
                b["completion_tokens"] += c.completion_tokens or 0
                b["tokens_known"] = True

        for b in by_agent.values():
            b["latency_seconds"] = round(b["latency_seconds"], 3)

        return {
            "total_calls": n,
            "failed_calls": sum(1 for c in self.calls if not c.succeeded),
            "total_latency_seconds": round(total_latency, 3),
            "average_latency_seconds": round(total_latency / n, 3) if n else 0.0,
            "tokens_known": len(known_token_calls) > 0,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "by_agent": by_agent,
        }


_collector = LLMMetricsCollector()


def get_collector() -> LLMMetricsCollector:
    return _collector
