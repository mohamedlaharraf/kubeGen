#!/usr/bin/env python3
"""
run_benchmark.py

Commande unique pour benchmarker les architectures de génération de
manifestes Kubernetes (E6 - instrumentation homogène).

Usage :
    python run_benchmark.py
    python run_benchmark.py --architectures A          # sous-ensemble
    python run_benchmark.py --scenarios 01,02,05        # sous-ensemble de scénarios
    python run_benchmark.py --output-dir mes_resultats

Ce script :
  1. Charge les scénarios de `benchmark/scenarios/*.txt`.
  2. Instancie chaque architecture enregistrée dans
     `benchmark/adapters/__init__.py` (actuellement : A uniquement --
     voir ce fichier pour brancher B/C/D quand elles seront prêtes).
  3. Exécute chaque scénario sur chaque architecture, capture la
     télémétrie, valide et score le manifeste produit.
  4. Écrit benchmark_results/benchmark_telemetry.{json,csv} et
     benchmark_results/benchmark_report.md.

Chaque run fait un VRAI appel à l'API du modèle configuré (GOOGLE_API_KEY
/ GEMINI_API_KEY doit être définie dans l'environnement) -- ça consomme
du quota et coûte potentiellement de l'argent, voir benchmark/pricing.py.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.adapters import ARCHITECTURE_REGISTRY  # noqa: E402
from benchmark.report import build_record, write_csv, write_json, write_markdown_report  # noqa: E402

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


def load_scenarios(scenarios_dir: Path, only_ids: set[str] | None) -> list[tuple[str, str]]:
    scenarios = []
    for path in sorted(scenarios_dir.glob("*.txt")):
        scenario_id = path.stem
        prefix = scenario_id.split("_")[0]
        if only_ids and prefix not in only_ids and scenario_id not in only_ids:
            continue
        scenarios.append((scenario_id, path.read_text(encoding="utf-8")))
    return scenarios


def main():
    parser = argparse.ArgumentParser(description="Benchmark comparatif des architectures kubeGen.")
    parser.add_argument(
        "--architectures", default="all",
        help=f"Liste séparée par des virgules parmi {list(ARCHITECTURE_REGISTRY.keys())}, "
             f"ou 'all' (défaut).",
    )
    parser.add_argument(
        "--scenarios", default="all",
        help="Liste d'IDs de scénarios séparés par virgules (ex: 01,02,05), ou 'all' (défaut).",
    )
    parser.add_argument("--scenarios-dir", default=str(SCENARIOS_DIR))
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent / "results"))
    args = parser.parse_args()

    arch_ids = (
        list(ARCHITECTURE_REGISTRY.keys())
        if args.architectures == "all"
        else [a.strip() for a in args.architectures.split(",")]
    )
    unknown = set(arch_ids) - set(ARCHITECTURE_REGISTRY.keys())
    if unknown:
        print(f"[erreur] architecture(s) inconnue(s) : {sorted(unknown)}. "
              f"Disponibles : {list(ARCHITECTURE_REGISTRY.keys())}", file=sys.stderr)
        sys.exit(1)

    only_scenario_ids = None if args.scenarios == "all" else {s.strip() for s in args.scenarios.split(",")}
    scenarios = load_scenarios(Path(args.scenarios_dir), only_scenario_ids)
    if not scenarios:
        print("[erreur] aucun scénario trouvé.", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"Benchmark {run_batch_id} : {len(arch_ids)} architecture(s) x {len(scenarios)} scénario(s) "
          f"= {len(arch_ids) * len(scenarios)} runs.\n")

    records: list[dict] = []
    json_path = output_dir / "benchmark_telemetry.json"
    csv_path = output_dir / "benchmark_telemetry.csv"
    md_path = output_dir / "benchmark_report.md"

    for arch_id in arch_ids:
        adapter_cls = ARCHITECTURE_REGISTRY[arch_id]
        print(f"=== Architecture {arch_id} ===")
        try:
            adapter = adapter_cls()
        except Exception as e:  # noqa: BLE001
            print(f"  [erreur] impossible d'initialiser l'architecture {arch_id} : {e}\n"
                  f"  -> cette architecture est ignorée pour le reste du benchmark.\n")
            continue

        for scenario_id, requirement in scenarios:
            run_name = f"bench_{run_batch_id}_{arch_id}_{scenario_id}"
            t0 = time.time()
            print(f"  [{scenario_id}] ... ", end="", flush=True)
            run_result = adapter.run(requirement, scenario_id, run_name)
            record = build_record(run_result)
            records.append(record)

            elapsed = round(time.time() - t0, 1)
            if run_result.error:
                print(f"ÉCHEC ({elapsed}s) : {run_result.error}")
            else:
                status = "valide" if record["k8s_validate_valid"] else "INVALIDE"
                print(f"ok ({elapsed}s, {status}, score énergie="
                      f"{record['energy_score']})")

            # Écriture incrémentale : un crash au run N/M ne fait pas perdre
            # la télémétrie des runs 1..N-1.
            write_json(records, json_path)

        print()

    if not records:
        print("[erreur] aucun run n'a produit de résultat exploitable.", file=sys.stderr)
        sys.exit(1)

    write_json(records, json_path)
    write_csv(records, csv_path)
    write_markdown_report(records, md_path)

    print(f"Terminé. {len(records)} run(s) enregistré(s) dans :")
    print(f"  - {json_path}")
    print(f"  - {csv_path}")
    print(f"  - {md_path}")


if __name__ == "__main__":
    main()
