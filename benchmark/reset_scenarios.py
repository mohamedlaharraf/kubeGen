#!/usr/bin/env python3
"""
reset_scenarios.py

Réinitialise (supprime) les résultats d'un ou plusieurs scénarios --
et éventuellement d'une ou plusieurs architectures -- avant de les
relancer avec run_benchmark.py.

Pourquoi ce script alors que run_benchmark.py fusionne déjà les runs ?
------------------------------------------------------------------
En pratique, relancer directement suffit dans 95% des cas :

    python run_benchmark.py --scenarios 01,05 --architectures A

remplace automatiquement l'entrée (architecture, scénario) existante
dans benchmark_telemetry.json, et energy_score / TOPSIS / AHP sont
recalculés depuis zéro à chaque écriture -- donc les "valeurs et
résultats" ne restent jamais périmés après un rerun.

Ce script sert pour les deux cas où un simple rerun ne suffit pas :
  1. Tu veux repartir d'un état "table rase" AVANT de relancer (par ex.
     pour vérifier dans le JSON qu'il n'y a plus aucune trace de
     l'ancien run, ou parce que tu ne relanceras que plus tard).
  2. Tu veux nettoyer les anciens dossiers de sortie accumulés dans
     generated-k8s-templates/<ARCH>/bench_*_<scenario>/ (manifest.yaml,
     metadata.json, raw_llm_output.txt) -- ces dossiers timestampés
     s'accumulent à chaque run et ne sont PAS nettoyés par le merge de
     run_benchmark.py, ni utilisés pour recalculer le score : ils ne
     servent qu'à l'inspection manuelle des sorties passées.

Ce que fait ce script :
  - Retire du fichier benchmark_telemetry.json les enregistrements dont
    (architecture_id, scenario_id) correspond à la sélection.
  - Réécrit benchmark_telemetry.json, benchmark_telemetry.csv et
    benchmark_report.md avec les enregistrements restants (mêmes
    fonctions que run_benchmark.py, donc score énergie / AHP / TOPSIS
    restent cohérents sur ce qu'il reste).
  - Avec --purge-outputs, supprime aussi les dossiers
    generated-k8s-templates/<ARCH>/bench_*_<scenario_id>/ correspondants.

Usage :
    # Aperçu sans rien supprimer (recommandé en premier)
    python reset_scenarios.py --scenarios 01,05 --dry-run

    # Supprimer les résultats de télémétrie des scénarios 01 et 05,
    # toutes architectures confondues
    python reset_scenarios.py --scenarios 01,05

    # Ne réinitialiser que l'architecture A sur le scénario 01
    python reset_scenarios.py --scenarios 01 --architectures A

    # Idem + supprimer aussi les vieux dossiers de sortie générés
    python reset_scenarios.py --scenarios 01,05 --purge-outputs

    # Tout réinitialiser (attention : supprime TOUT le contenu de
    # benchmark_telemetry.json)
    python reset_scenarios.py --all
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

def _find_benchmark_dir() -> Path:
    """
    Détecte où se trouve le dossier benchmark/ (results/,
    generated-k8s-templates/, ...) que le script soit placé :
      - à la racine du repo, à côté du dossier benchmark/ (ex:
        single-agent/reset_scenarios.py + single-agent/benchmark/...)
      - ou directement DANS le dossier benchmark/ lui-même (ex:
        single-agent/benchmark/reset_scenarios.py)
    """
    here = Path(__file__).resolve().parent
    if (here / "results").exists() or (here / "generated-k8s-templates").exists():
        return here  # le script est déjà dans benchmark/
    if (here / "benchmark" / "results").exists() or (here / "benchmark" / "generated-k8s-templates").exists():
        return here / "benchmark"  # le script est à côté de benchmark/
    # Ni l'un ni l'autre trouvé : on retombe sur l'ancien comportement
    # (l'erreur affichée plus bas guidera l'utilisateur).
    return here / "benchmark"


BENCHMARK_DIR = _find_benchmark_dir()
RESULTS_DIR = BENCHMARK_DIR / "results"
TEMPLATES_DIR = BENCHMARK_DIR / "generated-k8s-templates"


def matches(record: dict, scenario_ids: set[str] | None, arch_ids: set[str] | None) -> bool:
    """Un enregistrement 'matche' la sélection à supprimer si son
    scenario_id ET son architecture_id (quand filtrés) correspondent."""
    scenario_id = record.get("scenario_id", "")
    arch_id = record.get("architecture_id", "")

    scenario_ok = True
    if scenario_ids is not None:
        prefix = scenario_id.split("_")[0]
        scenario_ok = scenario_id in scenario_ids or prefix in scenario_ids

    arch_ok = True
    if arch_ids is not None:
        # Le JSON stocke "A_single_agent", "B_pipeline", etc. mais
        # run_benchmark.py --architectures s'utilise avec "A", "B" ...
        # -- on accepte donc les deux formes (nom complet ou préfixe).
        arch_prefix = arch_id.split("_")[0]
        arch_ok = arch_id in arch_ids or arch_prefix in arch_ids
    return scenario_ok and arch_ok


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenarios", default=None,
                         help="IDs de scénarios séparés par virgules (ex: 01,03,10). "
                              "Omis avec --all uniquement.")
    parser.add_argument("--architectures", default=None,
                         help="IDs d'architectures séparés par virgules (ex: A,B). "
                              "Par défaut : toutes les architectures pour les scénarios donnés.")
    parser.add_argument("--all", action="store_true",
                         help="Réinitialise TOUT (vide entièrement la télémétrie). "
                              "Ignore --scenarios/--architectures.")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR),
                         help=f"Dossier des résultats (défaut : {RESULTS_DIR})")
    parser.add_argument("--purge-outputs", action="store_true",
                         help="Supprime aussi les dossiers generated-k8s-templates/<ARCH>/bench_*_<scenario>/ "
                              "correspondants.")
    parser.add_argument("--dry-run", action="store_true",
                         help="N'écrit ni ne supprime rien, affiche seulement ce qui serait fait.")
    args = parser.parse_args()

    if not args.all and not args.scenarios:
        parser.error("indique --scenarios 01,05 (ou --all pour tout réinitialiser)")

    scenario_ids = None if args.all else {s.strip() for s in args.scenarios.split(",")}
    arch_ids = {a.strip() for a in args.architectures.split(",")} if args.architectures else None

    results_dir = Path(args.results_dir)
    json_path = results_dir / "benchmark_telemetry.json"
    csv_path = results_dir / "benchmark_telemetry.csv"
    md_path = results_dir / "benchmark_report.md"

    if not json_path.exists():
        print(f"[erreur] {json_path} introuvable.", file=sys.stderr)
        sys.exit(1)

    records = json.loads(json_path.read_text(encoding="utf-8"))
    to_remove = [r for r in records if args.all or matches(r, scenario_ids, arch_ids)]
    kept = [r for r in records if r not in to_remove]

    print(f"{len(records)} enregistrement(s) au total dans {json_path}")
    print(f"{len(to_remove)} à supprimer :")
    for r in to_remove:
        print(f"  - {r['architecture_id']:12s} / {r['scenario_id']:45s} "
              f"(energy_score={r.get('energy_score')})")
    print(f"{len(kept)} conservé(s).\n")

    # Dossiers de sortie concernés (aperçu / purge)
    dirs_to_purge: list[Path] = []
    if args.purge_outputs or args.dry_run:
        target_scenarios = None if args.all else scenario_ids
        target_archs = arch_ids
        if TEMPLATES_DIR.exists():
            for arch_dir in TEMPLATES_DIR.iterdir():
                if not arch_dir.is_dir():
                    continue
                if target_archs is not None and arch_dir.name not in target_archs:
                    continue
                for run_dir in arch_dir.iterdir():
                    if not run_dir.is_dir():
                        continue
                    if target_scenarios is None or any(
                        f"_{sid}" in run_dir.name or run_dir.name.endswith(sid)
                        for sid in target_scenarios
                    ):
                        dirs_to_purge.append(run_dir)

    if dirs_to_purge:
        action = "à supprimer" if args.purge_outputs else "seraient supprimés avec --purge-outputs"
        print(f"{len(dirs_to_purge)} dossier(s) generated-k8s-templates {action} :")
        for d in dirs_to_purge:
            print(f"  - {d}")
        print()

    if args.dry_run:
        print("[dry-run] rien n'a été écrit ni supprimé.")
        return

    # Réécrit les 3 fichiers de résultats avec ce qui reste.
    # report.py utilise des imports relatifs (`.energy_score`, etc.),
    # donc il doit être importé comme faisant partie du package
    # `benchmark` -- on ajoute le PARENT de BENCHMARK_DIR à sys.path et
    # on importe "<nom_du_dossier>.report" (fonctionne que le script
    # soit placé à côté de benchmark/ ou dedans, et même si le dossier
    # n'est pas nommé "benchmark").
    import importlib
    sys.path.insert(0, str(BENCHMARK_DIR.parent))
    report = importlib.import_module(f"{BENCHMARK_DIR.name}.report")
    write_csv = report.write_csv
    write_json = report.write_json
    write_markdown_report = report.write_markdown_report
    write_json(kept, json_path)
    write_csv(kept, csv_path)
    write_markdown_report(kept, md_path)
    print(f"OK : {json_path}, {csv_path} et {md_path} réécrits avec {len(kept)} enregistrement(s).")

    if args.purge_outputs:
        for d in dirs_to_purge:
            shutil.rmtree(d, ignore_errors=True)
        print(f"OK : {len(dirs_to_purge)} dossier(s) de sortie supprimé(s).")

    print("\nTu peux maintenant relancer, par ex. :")
    scen_arg = "all" if args.all else args.scenarios
    arch_arg = f" --architectures {args.architectures}" if args.architectures else ""
    print(f"  python run_benchmark.py --scenarios {scen_arg}{arch_arg}")


if __name__ == "__main__":
    main()