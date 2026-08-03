"""
main.py — point d'entrée CLI.

Usage de base :
    python main.py "Déploie une API Node.js appelée 'checkout-api', ..."
    python main.py --file examples/example_request.txt

Options ajoutées suite à un audit de couverture (voir README) :
    --interactive        Interrompt AVANT l'Agent 2 si l'Agent 1 a des
                          ambiguïtés non résolues, pose les questions à
                          l'utilisateur, puis relance le pipeline complet
                          avec la demande enrichie (pas de retour en
                          arrière DANS le graphe : on ne fait juste pas
                          avancer un run dont l'Agent 1 est incertain).
    --kubeconform         Valide le manifeste final contre les vrais
                          schémas OpenAPI Kubernetes (+ CRD tierces
                          connues) via le binaire `kubeconform` (optionnel,
                          dégrade proprement si absent).
    --dry-run-apply        `kubectl apply --dry-run=server` contre le
                          cluster configuré (kubeconfig courant) —
                          déclenche aussi les admission webhooks.
    --kube-context NAME    Contexte kubectl à utiliser pour --dry-run-apply
                          et --check-cluster-deps.
    --check-cluster-deps   Vérifie que les CRD requises (KEDA, Istio,
                          Prometheus Operator, Argo Rollouts) sont bien
                          installées sur le cluster cible.
    --metrics-source FILE  Fichier JSON {component_name: {cpu_p50, cpu_p95,
                          memory_p50, memory_p95}} : dimensionnement
                          déterministe basé sur des métriques réelles
                          plutôt qu'une heuristique LLM (voir Agent 4).
    --cost-estimate         Affiche une estimation de coût mensuel par
                          composant (ordre de grandeur, pas une facture).

Chaque exécution crée son propre sous-dossier horodaté dans OUTPUT_DIR :

    output/run_20260718_143012_482913/
    ├── 00_request.txt
    ├── agent1_normalized_spec.json
    ├── agent2_template.yaml
    ├── agent3_validated.yaml
    ├── agent4_energie.yaml
    ├── agent5_manifest_final.yaml
    ├── kubeconform_report.txt        (si --kubeconform)
    ├── dry_run_apply_report.txt      (si --dry-run-apply)
    └── audit_report.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from config import settings
from graph import build_pipeline
from schemas import PipelineState
from agents.agent1_analyse import run_agent1
from utils.logging_utils import console, log_success, log_error, log_warning, log_step
from utils.dependency_graph import find_circular_dependencies, find_dangling_dependencies
from utils.cost_estimate import estimate_monthly_cost
from utils.cluster_validate import run_kubeconform, run_dry_run_apply, check_cluster_dependencies
from utils.yaml_utils import load_all_documents
from utils.llm_metrics import get_collector


def build_audit_report_md(state: PipelineState, extra_sections: list[str] | None = None) -> str:
    lines = ["# Rapport d'audit du pipeline\n"]

    lines.append("## 1. Demande utilisateur (vue par l'Agent 1 uniquement)\n")
    lines.append(f"> {state.spec.raw_user_request}\n" if state.spec else "_(indisponible)_\n")

    if state.spec:
        lines.append("## 2. Architecture détectée\n")
        lines.append(f"- Type : **{state.spec.architecture_type}** "
                      f"({len(state.spec.components)} composant(s))")
        for c in state.spec.components:
            sidecar_note = (
                f", {len(c.sidecars)} sidecar(s): {[s.name for s in c.sidecars]}"
                if c.sidecars else ""
            )
            depends_note = f", dépend de: {c.depends_on}" if c.depends_on else ""
            lines.append(f"  - `{c.component_name}` ({c.workload_type}){sidecar_note}{depends_note}")

        cycles = find_circular_dependencies(state.spec.components)
        dangling = find_dangling_dependencies(state.spec.components)
        if cycles:
            lines.append(f"- ⚠️ Dépendances circulaires détectées : {cycles}")
        if dangling:
            lines.append(f"- ⚠️ Dépendances vers des noms non résolus (composant absent ou ressource externe) : {dangling}")
        if state.spec.target_clusters:
            lines.append(
                f"- `target_clusters={state.spec.target_clusters}` détecté(s) : "
                f"squelette ArgoCD ApplicationSet généré (voir manifeste), "
                f"placeholders à compléter."
            )
        lines.append("")

    lines.append("## 3. Auto-vérification Agent 1\n")
    if state.spec:
        cov = state.spec.coverage
        lines.append(f"- Auto-check réussi : **{cov.self_check_passed}**")
        lines.append(f"- Tentatives de réparation internes : {cov.repair_attempts}")
        if cov.requirements_unmapped:
            lines.append(f"- ⚠️ Exigences jamais couvertes : {cov.requirements_unmapped}")
        if state.spec.ambiguities:
            lines.append("- Hypothèses faites faute de précision de l'utilisateur :")
            for a in state.spec.ambiguities:
                lines.append(
                    f"  - `{a.field}` : {a.question} → hypothèse retenue : "
                    f"*{a.assumption_made}* (confiance {a.confidence})"
                )
    lines.append("")

    lines.append("## 4. Rapports par agent\n")
    for r in state.reports:
        lines.append(f"### {r.agent_name}")
        lines.append(f"- Champs traités : {r.fields_addressed}")
        if r.fields_left_open:
            lines.append(f"- ⚠️ Champs laissés ouverts : {r.fields_left_open}")
        if r.actions:
            lines.append("- Actions :")
            for a in r.actions:
                lines.append(f"  - {a}")
        if r.warnings:
            lines.append(f"- Avertissements : {r.warnings}")
        lines.append("")

    if state.traceability_matrix:
        lines.append("## 5. Matrice de traçabilité (Agent 5)\n")
        lines.append("| Champ spec | Valeur | Résolu dans |")
        lines.append("|---|---|---|")
        for row in state.traceability_matrix:
            lines.append(
                f"| {row.get('spec_field','?')} | {row.get('value','?')} | "
                f"{row.get('resolved_in','?')} |"
            )
        lines.append("")

    # Section dédiée, TOUJOURS présente si spec.unmapped_requirements n'est
    # pas vide — distincte du reste, pour qu'elle ne puisse jamais se
    # diluer dans la liste générique "à vérifier". C'est la réponse directe
    # au problème identifié : une fausse correspondance de champ produisait
    # un audit "tout va bien" ; ici, l'absence de correspondance reste
    # visible par construction, pas seulement si un agent pense à la
    # remonter correctement dans son fields_left_open.
    unmapped_list = state.spec.unmapped_requirements if state.spec else []
    if unmapped_list:
        lines.append("## 6. ⚠️ Exigences hors schéma structuré (BEST-EFFORT, NON VÉRIFIÉES)\n")
        lines.append(
            "Ces exigences ne correspondaient à AUCUN champ existant du schéma "
            "structuré. Plutôt que de les forcer dans un champ approximatif "
            "(ce qui produirait un audit faussement rassurant), elles ont été "
            "générées en best-effort par l'Agent 2 — **non couvertes par les "
            "cross-vérifications spécifiques du reste du pipeline** (pas de "
            "connaissance du schéma OpenAPI de ces `kind`, pas de "
            "cross-référence automatique). À valider manuellement avant tout "
            "déploiement réel.\n"
        )
        for r in unmapped_list:
            kind_note = f" (kind supposé : `{r.suggested_kind}`)" if r.suggested_kind else " (kind inconnu)"
            lines.append(f"- {r.text}{kind_note}")
        lines.append("")

    all_unresolved = []
    for r in state.reports:
        all_unresolved += r.fields_left_open
    # Garantie structurelle (indépendante de la propagation via les agents) :
    # tant que spec.unmapped_requirements n'est pas vide, la section 7
    # ci-dessous ne peut JAMAIS afficher "aucun point ouvert".
    if unmapped_list:
        all_unresolved.append(
            f"unmapped_requirements: {len(unmapped_list)} exigence(s) générée(s) "
            f"en best-effort — voir section 6 ci-dessus."
        )
    if all_unresolved:
        lines.append("## 7. ⚠️ À vérifier / relancer si besoin\n")
        for item in sorted(set(all_unresolved)):
            lines.append(f"- {item}")
    else:
        lines.append("## 7. Aucun point ouvert détecté ✅\n")

    if extra_sections:
        lines.append("\n" + "\n\n".join(extra_sections))

    if state.error:
        lines.append("\n## ⚠️ Le pipeline s'est arrêté en erreur\n")
        lines.append(f"> {state.error}")

    return "\n".join(lines)


def run_interactive_clarification(user_request: str) -> str:
    """
    Exécute l'Agent 1 SEUL, et si des ambiguïtés existent, les pose à
    l'utilisateur avant de lancer le pipeline complet. Ne modifie pas le
    graphe (toujours 5 agents, toujours strictement séquentiel) : on
    choisit juste, en amont, d'attendre une clarification plutôt que de
    lancer un run complet sur une hypothèse incertaine.
    """
    log_step("Mode interactif", "Analyse préliminaire (Agent 1 seul)...")
    probe_state = run_agent1(PipelineState(user_request=user_request))

    if probe_state.error or probe_state.spec is None:
        return user_request  # on laisse le run normal gérer l'erreur

    spec = probe_state.spec
    if spec.coverage.self_check_passed and not spec.ambiguities:
        log_success("Aucune ambiguïté détectée, pas de question nécessaire.")
        return user_request

    console.print("\n[bold yellow]Quelques points à clarifier avant de continuer :[/bold yellow]")
    clarifications = []
    for amb in spec.ambiguities:
        console.print(f"\n[cyan]{amb.question}[/cyan]")
        console.print(f"  (hypothèse actuelle : {amb.assumption_made})")
        answer = input("  Votre précision (Entrée pour garder l'hypothèse) : ").strip()
        if answer:
            clarifications.append(f"{amb.field}: {answer}")

    if not clarifications:
        log_warning("Mode interactif", "Aucune précision apportée, poursuite avec les hypothèses initiales.")
        return user_request

    augmented = (
        user_request
        + "\n\nPrécisions apportées par l'utilisateur suite à une clarification :\n"
        + "\n".join(clarifications)
    )
    log_success("Demande enrichie, lancement du pipeline complet.")
    return augmented


def save_run_outputs(state: PipelineState, run_dir: Path, user_request: str,
                      extra_files: dict[str, str] | None = None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "00_request.txt").write_text(user_request, encoding="utf-8")

    if state.spec:
        (run_dir / "agent1_normalized_spec.json").write_text(
            json.dumps(state.spec.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8",
        )
        log_success(f"Agent 1 (spec)      : {run_dir/'agent1_normalized_spec.json'}")

    for filename, content, label in (
        ("agent2_template.yaml", state.manifest_v1_yaml, "Agent 2 (template)"),
        ("agent3_validated.yaml", state.manifest_v2_yaml, "Agent 3 (validé)"),
        ("agent4_energie.yaml", state.manifest_v3_yaml, "Agent 4 (énergie)"),
        ("agent5_manifest_final.yaml", state.manifest_final_yaml, "Agent 5 (final)"),
    ):
        if content:
            (run_dir / filename).write_text(content, encoding="utf-8")
            log_success(f"{label:<20}: {run_dir/filename}")

    for filename, content in (extra_files or {}).items():
        (run_dir / filename).write_text(content, encoding="utf-8")
        log_success(f"{'Rapport externe':<20}: {run_dir/filename}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline séquentiel strict à 5 agents — génération de "
                     "manifestes Kubernetes optimisés en énergie."
    )
    parser.add_argument("request", nargs="?", help="Demande en langage naturel")
    parser.add_argument("--file", type=str, help="Lire la demande depuis un fichier texte")
    parser.add_argument("--output-dir", type=str, default=None,
                         help="Dossier racine des runs (défaut: variable OUTPUT_DIR).")
    parser.add_argument("--interactive", action="store_true",
                         help="Pose des questions ciblées avant de lancer le pipeline "
                              "complet si l'Agent 1 a des ambiguïtés non résolues.")
    parser.add_argument("--kubeconform", action="store_true",
                         help="Valide le manifeste final contre les schémas OpenAPI "
                              "Kubernetes réels via kubeconform (si installé).")
    parser.add_argument("--dry-run-apply", action="store_true",
                         help="kubectl apply --dry-run=server contre le cluster configuré.")
    parser.add_argument("--kube-context", type=str, default=None,
                         help="Contexte kubectl pour --dry-run-apply / --check-cluster-deps.")
    parser.add_argument("--check-cluster-deps", action="store_true",
                         help="Vérifie que les CRD requises (KEDA/Istio/Prometheus "
                              "Operator/Argo Rollouts) sont installées sur le cluster cible.")
    parser.add_argument("--metrics-source", type=str, default=None,
                         help="Fichier JSON {component_name: {cpu_p50, cpu_p95, "
                              "memory_p50, memory_p95}} pour un dimensionnement basé "
                              "sur des métriques réelles plutôt qu'une heuristique LLM.")
    parser.add_argument("--cost-estimate", action="store_true",
                         help="Affiche une estimation de coût mensuel par composant.")
    args = parser.parse_args()

    if args.file:
        user_request = Path(args.file).read_text(encoding="utf-8")
    elif args.request:
        user_request = args.request
    else:
        parser.print_help()
        sys.exit(1)

    # Reset AVANT tout appel LLM possible dans ce run, y compris le mode
    # interactif (qui fait un vrai appel LLM via run_agent1 en amont du
    # pipeline principal) — sinon cet appel échapperait aux métriques.
    get_collector().reset()
    run_started = time.perf_counter()

    if args.interactive:
        user_request = run_interactive_clarification(user_request)

    historical_metrics = {}
    if args.metrics_source:
        historical_metrics = json.loads(Path(args.metrics_source).read_text(encoding="utf-8"))

    root_output_dir = Path(args.output_dir or settings.OUTPUT_DIR)
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
    run_dir = root_output_dir / run_id

    pipeline = build_pipeline()
    initial_state = PipelineState(user_request=user_request, historical_metrics=historical_metrics)

    result_dict = pipeline.invoke(initial_state)
    state = PipelineState.model_validate(result_dict)
    pipeline_latency_seconds = time.perf_counter() - run_started

    extra_sections: list[str] = []
    extra_files: dict[str, str] = {}

    if not state.error and state.manifest_final_yaml:
        if args.kubeconform:
            log_step("Validation externe", "kubeconform (schémas OpenAPI réels)...")
            kc = run_kubeconform(state.manifest_final_yaml)
            if not kc["available"]:
                log_warning("kubeconform", kc["raw"])
                extra_sections.append(f"## kubeconform\n\n_{kc['raw']}_")
            else:
                status = "✅ PASSED" if kc["passed"] else "❌ FAILED"
                extra_sections.append(
                    "## kubeconform (validation OpenAPI réelle)\n\n"
                    f"**{status}**\n\n" + "\n".join(f"- {e}" for e in kc["errors"])
                )
                extra_files["kubeconform_report.txt"] = kc["raw"]
                if not kc["passed"]:
                    for e in kc["errors"]:
                        log_error("kubeconform", e)

        if args.dry_run_apply:
            log_step("Validation externe", "kubectl apply --dry-run=server...")
            dr = run_dry_run_apply(state.manifest_final_yaml, kube_context=args.kube_context)
            if not dr["available"]:
                log_warning("dry-run-apply", dr["raw"])
                extra_sections.append(f"## dry-run-apply\n\n_{dr['raw']}_")
            else:
                status = "✅ PASSED" if dr["passed"] else "❌ FAILED"
                extra_sections.append(
                    "## kubectl apply --dry-run=server\n\n"
                    f"**{status}**\n\n" + "\n".join(f"- {e}" for e in dr["errors"])
                )
                extra_files["dry_run_apply_report.txt"] = dr["raw"] or "\n".join(dr["errors"])
                if not dr["passed"]:
                    for e in dr["errors"]:
                        log_error("dry-run-apply", e)

        if args.check_cluster_deps:
            log_step("Validation externe", "Vérification des CRD requises sur le cluster...")
            docs = load_all_documents(state.manifest_final_yaml)
            kinds_used = {d.get("kind") for d in docs}
            dep = check_cluster_dependencies(kinds_used, kube_context=args.kube_context)
            if not dep["checked"]:
                extra_sections.append(f"## Dépendances cluster\n\n_{dep['raw']}_")
            elif dep["missing"]:
                extra_sections.append(
                    "## ⚠️ Dépendances cluster manquantes\n\n"
                    + "\n".join(f"- {m}" for m in dep["missing"])
                )
                for m in dep["missing"]:
                    log_error("check-cluster-deps", m)
            else:
                extra_sections.append("## Dépendances cluster\n\nToutes les CRD requises sont présentes ✅")

        if args.cost_estimate and state.spec:
            docs = load_all_documents(state.manifest_final_yaml)
            cost_lines = ["## Estimation de coût mensuel (ordre de grandeur, pas une facture)\n"]
            total = 0.0
            for component in state.spec.components:
                doc = next((d for d in docs if d.get("metadata", {}).get("name") == component.component_name
                            and d.get("kind") in {"Deployment", "StatefulSet", "DaemonSet", "Rollout"}), None)
                if not doc:
                    continue
                containers = doc.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
                main_container = next((c for c in containers if c.get("name") == component.component_name), None)
                requests = (main_container or {}).get("resources", {}).get("requests", {})
                if not requests.get("cpu") or not requests.get("memory"):
                    continue
                estimate = estimate_monthly_cost(
                    component.component_name, requests["cpu"], requests["memory"], component.replicas,
                )
                total += estimate.monthly_cost_eur
                cost_lines.append(f"- `{component.component_name}` : ~{estimate.monthly_cost_eur} €/mois "
                                   f"({component.replicas} réplica(s))")
            cost_lines.append(f"\n**Total estimé : ~{round(total, 2)} €/mois**")
            extra_sections.append("\n".join(cost_lines))
            console.print("\n".join(cost_lines))

    # Métriques d'exécution : latence, appels LLM, tokens. Calculées en tout
    # dernier pour inclure aussi le temps des validations externes optionnelles
    # (kubeconform, dry-run-apply...) dans le total, en plus du temps du
    # pipeline seul (mesuré juste après pipeline.invoke, voir plus haut).
    total_latency_seconds = time.perf_counter() - run_started
    llm_metrics = get_collector().summary()
    execution_metrics = {
        "pipeline_latency_seconds": round(pipeline_latency_seconds, 3),
        "total_latency_seconds": round(total_latency_seconds, 3),
        "llm_calls": llm_metrics,
    }

    metrics_lines = [
        "## Métriques d'exécution\n",
        f"- Latence totale du run : **{execution_metrics['total_latency_seconds']} s** "
        f"(dont pipeline seul : {execution_metrics['pipeline_latency_seconds']} s)",
        f"- Appels LLM : **{llm_metrics['total_calls']}** "
        f"({llm_metrics['failed_calls']} échoué(s)/retenté(s))",
        f"- Latence cumulée des appels LLM : {llm_metrics['total_latency_seconds']} s "
        f"(moyenne {llm_metrics['average_latency_seconds']} s/appel)",
    ]
    if llm_metrics["tokens_known"]:
        metrics_lines.append(
            f"- Tokens consommés : **{llm_metrics['total_tokens']}** "
            f"({llm_metrics['total_prompt_tokens']} prompt + "
            f"{llm_metrics['total_completion_tokens']} completion)"
        )
    else:
        metrics_lines.append(
            "- Tokens consommés : _inconnus_ (mode offline, ou le SDK n'a pas "
            "renvoyé `usage_metadata` pour cet appel)"
        )
    metrics_lines.append("\n| Agent | Appels | Latence cumulée (s) | Tokens |")
    metrics_lines.append("|---|---|---|---|")
    for agent_name, b in llm_metrics["by_agent"].items():
        tokens_display = (
            f"{b['prompt_tokens'] + b['completion_tokens']}" if b["tokens_known"] else "inconnu"
        )
        failed_note = f" ({b['failed_calls']} échoué(s))" if b["failed_calls"] else ""
        metrics_lines.append(
            f"| {agent_name} | {b['calls']}{failed_note} | {b['latency_seconds']} | {tokens_display} |"
        )
    extra_sections.append("\n".join(metrics_lines))

    log_success(
        f"Métriques           : {llm_metrics['total_calls']} appel(s) LLM, "
        f"{execution_metrics['total_latency_seconds']} s au total"
        + (f", {llm_metrics['total_tokens']} tokens" if llm_metrics["tokens_known"] else "")
    )

    save_run_outputs(state, run_dir, user_request, extra_files)
    (run_dir / "execution_metrics.json").write_text(
        json.dumps(execution_metrics, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    log_success(f"Métriques (JSON)    : {run_dir/'execution_metrics.json'}")
    (run_dir / "audit_report.md").write_text(
        build_audit_report_md(state, extra_sections), encoding="utf-8"
    )
    log_success(f"Rapport d'audit     : {run_dir/'audit_report.md'}")

    if state.error:
        log_error("Pipeline", state.error)
        log_warning("Pipeline", f"Sorties partielles disponibles dans : {run_dir}")
        sys.exit(2)

    console.print(f"\n[bold]Run complet : {run_dir}[/bold]")
    console.print("\n[bold]--- Manifeste final ---[/bold]\n")
    console.print(state.manifest_final_yaml)


if __name__ == "__main__":
    main()
