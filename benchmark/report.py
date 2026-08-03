"""
benchmark/report.py

Construit un enregistrement homogène par run (une architecture x un
scénario), l'enrichit avec les résultats de validation/scoring, puis
exporte :
  - benchmark_telemetry.json  (détail complet, imbriqué -- source de vérité)
  - benchmark_telemetry.csv   (vue plate, une ligne par run, pour Excel/pandas)
  - benchmark_report.md       (tableau de comparaison agrégé par architecture)
"""
from __future__ import annotations

import csv
import json
import statistics
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import yaml

from .adapters.base import RunResult
from .energy_score import score as energy_score
from .pricing import estimate_cost_usd
from .validators import kube_linter
from .validators.k8s_validate import full_validation


def _parse_docs(manifest_yaml: str) -> tuple[list[dict], str | None]:
    """Retourne (docs, erreur_parsing). Une erreur de parsing YAML est en
    soi le pire cas de "syntactic validity" -- elle est propagée telle
    quelle plutôt que masquée derrière une liste de docs vide."""
    if not manifest_yaml.strip():
        return [], "Sortie vide (aucun YAML produit)."
    try:
        docs = [d for d in yaml.safe_load_all(manifest_yaml) if d is not None]
    except yaml.YAMLError as e:
        return [], f"Erreur de parsing YAML : {e}"
    if not docs:
        return [], "Aucun document YAML trouvé."
    return docs, None


def build_record(run: RunResult) -> dict:
    record: dict = {
        "architecture_id": run.architecture_id,
        "architecture_label": run.architecture_label,
        "scenario_id": run.scenario_id,
        "model": run.model,
        "total_latency_seconds": run.total_latency_seconds,
        "total_llm_calls": run.total_llm_calls,
        "tokens_known": run.tokens_known,
        "input_tokens": run.total_input_tokens if run.tokens_known else None,
        "output_tokens": run.total_output_tokens if run.tokens_known else None,
        "steps": [asdict(s) for s in run.steps],
        "run_error": run.error,
    }

    record["cost_usd"] = estimate_cost_usd(
        run.model, record["input_tokens"], record["output_tokens"]
    )

    if run.error and not run.manifest_yaml.strip():
        # Échec total : aucun manifeste à valider/scorer. Pour un échec
        # PARTIEL (ex: Architecture B qui a produit agent2_template.yaml
        # avant de planter à l'agent 3), on continue plus bas pour quand
        # même valider/scorer ce qui a été produit -- c'est une donnée de
        # benchmark en soi (jusqu'où l'architecture est-elle allée ?).
        record.update({
            "parse_error": None,
            "k8s_validate_valid": False,
            "k8s_validate_errors": [],
            "kube_linter_available": kube_linter.is_available(),
            "kube_linter_passed": None,
            "kube_linter_checks_failed": [],
            "energy_score": None,
            "energy_score_breakdown": {},
        })
        return record

    docs, parse_error = _parse_docs(run.manifest_yaml)
    record["parse_error"] = parse_error

    k8s_errors = full_validation(docs) if docs else []
    record["k8s_validate_valid"] = bool(docs) and not k8s_errors and not parse_error
    record["k8s_validate_errors"] = k8s_errors

    kl_result = kube_linter.lint_yaml(run.manifest_yaml) if run.manifest_yaml.strip() else \
        kube_linter.KubeLinterResult(available=kube_linter.is_available(), passed=None, checks_failed=[])
    record["kube_linter_available"] = kl_result.available
    record["kube_linter_passed"] = kl_result.passed
    record["kube_linter_checks_failed"] = kl_result.checks_failed

    es = energy_score(docs) if docs else energy_score([])
    record["energy_score"] = es.score
    record["energy_score_breakdown"] = es.breakdown

    return record


def write_csv(records: list[dict], path: Path) -> None:
    fieldnames = [
        "architecture_id", "architecture_label", "scenario_id", "model",
        "total_latency_seconds", "total_llm_calls", "input_tokens", "output_tokens",
        "cost_usd", "k8s_validate_valid", "kube_linter_available", "kube_linter_passed",
        "energy_score", "run_error", "parse_error",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def write_json(records: list[dict], path: Path) -> None:
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def _avg(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.mean(vals), 3) if vals else None


def _rate(values: list[bool | None]) -> float | None:
    known = [v for v in values if v is not None]
    return round(100 * sum(1 for v in known if v) / len(known), 1) if known else None


def aggregate_by_architecture(records: list[dict]) -> dict[str, dict]:
    aggregates: dict[str, dict] = {}
    by_arch: dict[str, list[dict]] = {}
    for r in records:
        by_arch.setdefault(r["architecture_id"], []).append(r)

    for arch_id, rs in by_arch.items():
        n_total = len(rs)
        n_failed = sum(1 for r in rs if r["run_error"])
        aggregates[arch_id] = {
            "architecture_label": rs[0]["architecture_label"],
            "n_scenarios": n_total,
            "n_failed_runs": n_failed,
            "avg_latency_seconds": _avg([r["total_latency_seconds"] for r in rs]),
            "avg_input_tokens": _avg([r["input_tokens"] for r in rs]),
            "avg_output_tokens": _avg([r["output_tokens"] for r in rs]),
            "avg_cost_usd": _avg([r["cost_usd"] for r in rs]),
            "total_cost_usd": round(sum(r["cost_usd"] for r in rs if r["cost_usd"] is not None), 6),
            "k8s_validate_validity_rate_pct": _rate([r["k8s_validate_valid"] for r in rs]),
            "kube_linter_pass_rate_pct": _rate([r["kube_linter_passed"] for r in rs]),
            "avg_energy_score": _avg([r["energy_score"] for r in rs]),
        }
    return aggregates


def write_markdown_report(records: list[dict], path: Path) -> None:
    aggregates = aggregate_by_architecture(records)
    n_scenarios = len({r["scenario_id"] for r in records})

    lines = [
        "# Rapport de benchmark comparatif - Architectures A/B/C/D",
        "",
        f"Généré le {datetime.now().isoformat(timespec='seconds')} "
        f"· {n_scenarios} scénarios · {len(aggregates)} architecture(s) évaluée(s).",
        "",
        "> ⚠️ Architectures non encore implémentées au moment de ce run : "
        "elles n'apparaissent simplement pas dans ce tableau (voir "
        "`benchmark/adapters/__init__.py` pour le statut d'implémentation).",
        "",
        "## Tableau comparatif (moyennes sur l'ensemble des scénarios)",
        "",
        "| Architecture | Scénarios | Échecs | Latence moy. (s) | Tokens in moy. | "
        "Tokens out moy. | Coût moy. ($) | Coût total ($) | Validité "
        "k8s_validate (%) | Validité kube-linter (%) | Score énergie moy. (/100) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    def fmt(v, suffix=""):
        return f"{v}{suffix}" if v is not None else "N/A"

    for arch_id, a in sorted(aggregates.items()):
        lines.append(
            f"| {a['architecture_label']} | {a['n_scenarios']} | {a['n_failed_runs']} | "
            f"{fmt(a['avg_latency_seconds'])} | {fmt(a['avg_input_tokens'])} | "
            f"{fmt(a['avg_output_tokens'])} | {fmt(a['avg_cost_usd'])} | "
            f"{fmt(a['total_cost_usd'])} | {fmt(a['k8s_validate_validity_rate_pct'], '%')} | "
            f"{fmt(a['kube_linter_pass_rate_pct'], '%')} | {fmt(a['avg_energy_score'])} |"
        )

    lines += [
        "",
        "## Détail par scénario",
        "",
        "| Architecture | Scénario | Latence (s) | Coût ($) | k8s_validate | "
        "kube-linter | Score énergie | Erreur |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(records, key=lambda r: (r["architecture_id"], r["scenario_id"])):
        kl = "N/A" if r["kube_linter_passed"] is None else ("✔" if r["kube_linter_passed"] else "✖")
        k8sv = "✔" if r["k8s_validate_valid"] else "✖"
        err = (r["run_error"] or r["parse_error"] or "")[:60]
        lines.append(
            f"| {r['architecture_id']} | {r['scenario_id']} | "
            f"{fmt(r['total_latency_seconds'])} | {fmt(r['cost_usd'])} | {k8sv} | {kl} | "
            f"{fmt(r['energy_score'])} | {err} |"
        )

    lines += [
        "",
        "## Notes méthodologiques",
        "",
        "- **Validité syntaxique (k8s_validate)** : validateur déterministe "
        "commun (vendored depuis pipeline-kubegen), sans dépendance externe, "
        "appliqué de façon identique à toutes les architectures — voir "
        "`benchmark/validators/k8s_validate.py`.",
        "- **Validité syntaxique (kube-linter)** : nécessite le binaire "
        "`kube-linter` sur le PATH ; `N/A` si absent (voir `benchmark/README.md`).",
        "- **Score énergie** : rubrique statique pondérée (requests/limits, "
        "autoscaling, node scheduling, PodDisruptionBudget, probes), "
        "normalisée sur les critères applicables à chaque scénario — voir "
        "`benchmark/energy_score.py` pour le détail des poids.",
        "- **Coût monétaire** : extrapolé depuis `benchmark/pricing.py` "
        "(tarifs à re-vérifier avant publication, voir avertissement dans ce "
        "fichier).",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
