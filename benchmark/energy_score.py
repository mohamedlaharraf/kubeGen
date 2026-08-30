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
reproductible, avec des poids dérivés par AHP (Analytic Hierarchy
Process, voir benchmark/ahp.py) à partir d'une matrice de comparaisons
par paires documentée et vérifiée cohérente (CR < 0.10), plutôt que
choisis à la main. Documentée ici pour que le rapport final puisse citer
précisément ce qui est mesuré, comment les poids ont été obtenus, et les
limites de la méthode -- plutôt que de présenter un chiffre opaque.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .validators.k8s_validate import POD_TEMPLATE_KINDS, WORKLOAD_KINDS, _pod_template
from .ahp import compute_weights


@dataclass
class EnergyScoreResult:
    score: float | None              # /100, None si aucun critère applicable
    breakdown: dict[str, float | None] = field(default_factory=dict)  # nom -> fraction (0..1) ou None si non-applicable
    weights: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Poids DÉRIVÉS PAR AHP (Analytic Hierarchy Process), pas choisis à la main.
#
# Matrice de comparaisons par paires (échelle de Saaty 1-9) : M[i][j] =
# combien le critère i est jugé plus important que j pour l'EFFICACITÉ
# ÉNERGÉTIQUE d'un manifeste Kubernetes. Justification résumée par ligne :
#
# - resource_requests_limits (sizing) : le levier le plus DIRECT --
#   c'est littéralement la quantité de ressources réservée 24/7.
#   Nettement plus important que PDB (5, sans lien avec l'énergie) et
#   probes (4, lien indirect via les pods zombies) ; modérément plus
#   important que node_scheduling (3, qui affecte le packing mais pas la
#   quantité totale réservée) et qu'autoscaling (2, qui n'a d'effet que
#   si la charge varie réellement).
# - autoscaling : réduit le sur-provisionnement dans le TEMPS (contexte
#   de charge variable) là où le sizing le réduit dans l'ESPACE (une
#   allocation figée) -- deuxième levier le plus direct.
# - node_scheduling_efficiency : améliore la densité de bin-packing
#   (moins de nœuds actifs à ressources égales), mais n'affecte pas la
#   quantité de ressources demandée elle-même -- effet réel mais indirect.
# - disruption_budget (PDB) : mécanisme de DISPONIBILITÉ, sans lien causal
#   direct avec la consommation énergétique -- inclus dans la rubrique
#   pour cohérence avec le reste du projet (évite le sur-provisionnement
#   "de sécurité" ad hoc), mais légitimement le critère le moins pertinent.
# - probes : évite des pods "zombies" qui continuent de consommer des
#   ressources sans servir -- effet réel mais marginal comparé au sizing.
#
# Ratio de cohérence CR = 0.0153 (<< seuil de 0.10) : les jugements
# ci-dessus ne se contredisent pas entre eux -- voir benchmark/ahp.py
# pour la méthode de calcul complète.
# ---------------------------------------------------------------------------
_AHP_LABELS = [
    "resource_requests_limits", "autoscaling",
    "node_scheduling_efficiency", "disruption_budget", "probes",
]
_AHP_MATRIX = [
    #                        sizing  autosc  node_sched  pdb   probes
    [1,     2,    3,    5,    4],     # resource_requests_limits
    [1/2,   1,    2,    4,    3],     # autoscaling
    [1/3,   1/2,  1,    3,    2],     # node_scheduling_efficiency
    [1/5,   1/4,  1/3,  1,    1/2],   # disruption_budget
    [1/4,   1/3,  1/2,  2,    1],     # probes
]
_AHP_RESULT = compute_weights(_AHP_LABELS, _AHP_MATRIX)
assert _AHP_RESULT.is_consistent, (
    f"Matrice AHP des critères énergie incohérente (CR={_AHP_RESULT.consistency_ratio} "
    f">= {0.10}) -- revoir les jugements de comparaison avant de faire confiance à ces poids."
)
# Poids en /100 (plutôt qu'en fractions sommant à 1) pour rester lisible
# dans les rapports et compatible avec l'échelle /100 du score final.
_WEIGHTS = {k: round(v * 100, 1) for k, v in _AHP_RESULT.weights.items()}


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
