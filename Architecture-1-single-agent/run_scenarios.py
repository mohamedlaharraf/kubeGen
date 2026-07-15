"""
Lance l'agent unique sur tous les scénarios du dossier scenarios/ et agrège
les métriques dans results/single_agent_results.csv.

Ce CSV est pensé pour être directement comparable aux résultats des
architectures 2, 3 et 4 (mêmes colonnes clés : architecture, latence,
nombre d'appels LLM, validité YAML) afin de faciliter l'analyse finale.

Usage :
    python run_scenarios.py
    python run_scenarios.py -m llama3.2:1b
"""
import argparse
import csv
from pathlib import Path

from single_agent import SingleAgentGenerator

SCENARIOS_DIR = Path("scenarios")
RESULTS_DIR = Path("results")
RESULTS_CSV = RESULTS_DIR / "single_agent_results.csv"

CSV_FIELDS = [
    "architecture", "scenario", "model", "latency_seconds",
    "num_llm_calls", "yaml_valid", "output_chars", "timestamp", "run_dir",
]


def main():
    parser = argparse.ArgumentParser(description="Benchmark de l'Architecture 1 sur tous les scénarios.")
    parser.add_argument("-m", "--model", type=str, default=None)
    args = parser.parse_args()

    kwargs = {}
    if args.model:
        kwargs["model"] = args.model
    agent = SingleAgentGenerator(**kwargs)

    RESULTS_DIR.mkdir(exist_ok=True)
    scenario_files = sorted(SCENARIOS_DIR.glob("*.txt"))
    if not scenario_files:
        print(f"Aucun scénario trouvé dans {SCENARIOS_DIR}/")
        return

    rows = []
    for path in scenario_files:
        requirement = path.read_text(encoding="utf-8").strip()
        scenario_name = path.stem
        print(f"--- Scénario: {scenario_name} ---")
        result = agent.generate(requirement, run_name=scenario_name)
        print(f"  -> latence={result['latency_seconds']}s valide={result['yaml_valid']}")
        rows.append({k: result.get(k) for k in CSV_FIELDS})

    write_header = not RESULTS_CSV.exists()
    with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    print(f"\nRésultats agrégés dans {RESULTS_CSV}")


if __name__ == "__main__":
    main()
