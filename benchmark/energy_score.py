"""
benchmark/energy_score.py

Rubrique statique et déterministe pour noter la "qualité énergétique" des
manifestes générés (limits/requests, HPA/KEDA, node affinity, PDB,
probes). Opère sur les documents YAML déjà parsés -- donc utilisable tel
quel pour n'importe quelle architecture (A, B, C, D), ce qui satisfait
l'exigence E6 d'instrumentation homogène.

PRINCIPE : chaque critère n'est compté que s'il est "applicable" au jeu
de manifestes évalué (ex: pas de pénalité HPA sur un scénario CronJob
qui n'a structurellement aucun workload scalable). Le score final est
une moyenne pondérée normalisée sur les seuls critères applicables,
ramenée sur 100.

Ce n'est PAS une vérité absolue -- c'est une rubrique déclarée et
reproductible, documentée ici pour que le rapport final puisse citer
précisément ce qui est mesuré (et ses limites) plutôt que de présenter
un chiffre opaque.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .validators.k8s_validate import POD_TEMPLATE_KINDS, WORKLOAD_KINDS, _pod_template


@dataclass
class EnergyScoreResult:
    score: float | None              # /100, None si aucun critère applicable
    breakdown: dict[str, float | None] = field(default_factory=dict)  # nom -> fraction (0..1) ou None si non-applicable
    weights: dict[str, int] = field(default_factory=dict)


# Poids relatifs (somme = 100 si TOUS les critères sont applicables ;
# sinon normalisation sur le sous-ensemble applicable, voir score()).
_WEIGHTS = {
    "resource_requests_limits": 40,   # right-sizing : le levier énergétique le plus direct
    "autoscaling": 25,                # HPA / KEDA ScaledObject -> pas de sur-provisionnement permanent
    "node_scheduling_efficiency": 20, # affinity / nodeSelector / topologySpreadConstraints
    "disruption_budget": 10,          # évite le sur-provisionnement "de sécurité" ad hoc
    "probes": 5,                      # évite de garder des pods zombies qui consomment des ressources
}


def _all_containers(docs: list[dict]) -> list[dict]:
    containers = []
    for doc in docs:
        if doc.get("kind") not in POD_TEMPLATE_KINDS:
            continue
        containers.extend(_pod_template(doc).get("spec", {}).get("containers", []))
    return containers


def _score_resource_requests_limits(docs: list[dict]) -> float | None:
    containers = _all_containers(docs)
    if not containers:
        return None
    with_requests = sum(
        1 for c in containers
        if {"cpu", "memory"} <= set(c.get("resources", {}).get("requests", {}).keys())
    )
    with_limits = sum(
        1 for c in containers
        if {"cpu", "memory"} <= set(c.get("resources", {}).get("limits", {}).keys())
    )
    return ((with_requests / len(containers)) + (with_limits / len(containers))) / 2


def _score_autoscaling(docs: list[dict]) -> float | None:
    scalable = {d["metadata"]["name"] for d in docs if d.get("kind") in WORKLOAD_KINDS}
    if not scalable:
        return None  # pas de workload scalable dans ce scénario (ex: CronJob seul)
    targets = set()
    for d in docs:
        if d.get("kind") in ("HorizontalPodAutoscaler", "ScaledObject"):
            targets.add(d.get("spec", {}).get("scaleTargetRef", {}).get("name"))
    return 1.0 if (scalable & targets) else 0.0


def _score_node_scheduling_efficiency(docs: list[dict]) -> float | None:
    workloads = [d for d in docs if d.get("kind") in POD_TEMPLATE_KINDS]
    if not workloads:
        return None
    hits = 0
    for w in workloads:
        pod_spec = _pod_template(w).get("spec", {})
        has_affinity = bool(pod_spec.get("affinity", {}).get("nodeAffinity"))
        has_node_selector = bool(pod_spec.get("nodeSelector"))
        has_topology_spread = bool(pod_spec.get("topologySpreadConstraints"))
        if has_affinity or has_node_selector or has_topology_spread:
            hits += 1
    return hits / len(workloads)


def _score_disruption_budget(docs: list[dict]) -> float | None:
    multi_replica_workloads = [
        d for d in docs
        if d.get("kind") in WORKLOAD_KINDS and d.get("spec", {}).get("replicas", 1) > 1
    ]
    if not multi_replica_workloads:
        return None  # pas de workload à plusieurs réplicas -> PDB non pertinent
    pdbs = [d for d in docs if d.get("kind") == "PodDisruptionBudget"]
    return 1.0 if pdbs else 0.0


def _score_probes(docs: list[dict]) -> float | None:
    # Seulement pertinent pour les workloads "service long-running"
    # (Deployment/StatefulSet/DaemonSet/Rollout) -- pas pour Job/CronJob,
    # où les probes de disponibilité n'ont pas de sens standard.
    containers = []
    for d in docs:
        if d.get("kind") not in WORKLOAD_KINDS:
            continue
        containers.extend(_pod_template(d).get("spec", {}).get("containers", []))
    if not containers:
        return None
    with_both = sum(
        1 for c in containers if "livenessProbe" in c and "readinessProbe" in c
    )
    return with_both / len(containers)


_SCORERS = {
    "resource_requests_limits": _score_resource_requests_limits,
    "autoscaling": _score_autoscaling,
    "node_scheduling_efficiency": _score_node_scheduling_efficiency,
    "disruption_budget": _score_disruption_budget,
    "probes": _score_probes,
}


def score(docs: list[dict]) -> EnergyScoreResult:
    breakdown: dict[str, float | None] = {}
    applicable_weight = 0
    weighted_sum = 0.0

    for name, weight in _WEIGHTS.items():
        fraction = _SCORERS[name](docs)
        breakdown[name] = fraction
        if fraction is not None:
            applicable_weight += weight
            weighted_sum += weight * fraction

    if applicable_weight == 0:
        return EnergyScoreResult(score=None, breakdown=breakdown, weights=_WEIGHTS)

    final = round(100 * weighted_sum / applicable_weight, 1)
    return EnergyScoreResult(score=final, breakdown=breakdown, weights=_WEIGHTS)
