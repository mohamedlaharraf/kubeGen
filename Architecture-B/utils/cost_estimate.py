"""
utils/cost_estimate.py

Deux briques déterministes (Python pur, PAS de LLM) pour rendre le
dimensionnement de l'Agent 4 moins heuristique :

1. `size_from_metrics()` — si des métriques historiques réelles sont
   fournies (CPU/mémoire p50/p95 mesurés, ex: export Prometheus ou
   recommandation VPA), calcule `requests`/`limits` par une formule
   transparente plutôt que de laisser le LLM deviner des valeurs "de bon
   sens". Utilisé par l'Agent 4 UNIQUEMENT si des métriques sont fournies
   pour le composant (voir `--metrics-source` dans `main.py`) ; sinon
   comportement inchangé (heuristique LLM).

2. `estimate_monthly_cost()` — estimation de coût mensuel à partir de
   requests CPU/mémoire + nombre de réplicas + un tarif par vCPU et par
   Go de RAM. Les tarifs par défaut sont des ORDRES DE GRANDEUR génériques
   (pas les tarifs exacts d'un cloud provider donné) — présentés comme
   des estimations, jamais comme une facture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_QUANTITY_RE = re.compile(r"^(\d+(?:\.\d+)?)(m|Mi|Gi|Ki|G|M|K)?$")

_UNIT_TO_BASE = {
    None: 1, "m": 1e-3,
    "Ki": 1024, "Mi": 1024 ** 2, "Gi": 1024 ** 3,
    "K": 1000, "M": 1000 ** 2, "G": 1000 ** 3,
}


def _parse_quantity(q: str) -> float:
    """Parse une quantité K8s ('500m', '2Gi', '1') en valeur de base
    (vCPU pour le CPU, octets pour la mémoire)."""
    match = _QUANTITY_RE.match(str(q).strip())
    if not match:
        raise ValueError(f"Quantité Kubernetes invalide : '{q}'")
    value, unit = match.groups()
    return float(value) * _UNIT_TO_BASE[unit]


@dataclass
class HistoricalMetrics:
    """Métriques mesurées pour un composant (export Prometheus,
    recommandation VPA...). Unités K8s natives."""
    cpu_p50: str
    cpu_p95: str
    memory_p50: str
    memory_p95: str


def size_from_metrics(metrics: HistoricalMetrics, safety_margin: float = 1.3) -> dict:
    """
    Calcule requests/limits à partir de métriques réelles, formule
    transparente et documentée (pas une boîte noire LLM) :
      - requests = p50 mesuré (dimensionnement "normal")
      - limits   = p95 mesuré * marge de sécurité
    """
    cpu_request_vcpu = _parse_quantity(metrics.cpu_p50)
    cpu_limit_vcpu = _parse_quantity(metrics.cpu_p95) * safety_margin
    mem_request_bytes = _parse_quantity(metrics.memory_p50)
    mem_limit_bytes = _parse_quantity(metrics.memory_p95) * safety_margin

    return {
        "requests": {
            "cpu": f"{max(round(cpu_request_vcpu * 1000), 1)}m",
            "memory": f"{max(round(mem_request_bytes / (1024 ** 2)), 1)}Mi",
        },
        "limits": {
            "cpu": f"{max(round(cpu_limit_vcpu * 1000), 1)}m",
            "memory": f"{max(round(mem_limit_bytes / (1024 ** 2)), 1)}Mi",
        },
        "source": "métriques historiques mesurées (pas une estimation LLM)",
    }


@dataclass
class PricingTable:
    """Tarifs génériques €/heure — ordre de grandeur "cloud générique
    on-demand", PAS le tarif exact d'un provider donné."""
    eur_per_vcpu_hour: float = 0.033
    eur_per_gb_ram_hour: float = 0.0045
    hours_per_month: float = 730.0


@dataclass
class ComponentCostEstimate:
    component_name: str
    replicas: int
    monthly_cost_eur: float
    detail: dict = field(default_factory=dict)


def estimate_monthly_cost(component_name: str, cpu_request: str, memory_request: str,
                           replicas: int, pricing: PricingTable | None = None) -> ComponentCostEstimate:
    """
    Estimation de coût mensuel basée sur les `requests` (ce qui est
    réellement réservé), pas les `limits`.

    C'est un ORDRE DE GRANDEUR pour comparer des scénarios entre eux
    (avant/après optimisation énergie), PAS une facture.
    """
    pricing = pricing or PricingTable()
    vcpu = _parse_quantity(cpu_request)
    gb_ram = _parse_quantity(memory_request) / (1024 ** 3)

    cost_per_replica_hour = (
        vcpu * pricing.eur_per_vcpu_hour + gb_ram * pricing.eur_per_gb_ram_hour
    )
    monthly = cost_per_replica_hour * replicas * pricing.hours_per_month

    return ComponentCostEstimate(
        component_name=component_name,
        replicas=replicas,
        monthly_cost_eur=round(monthly, 2),
        detail={
            "vcpu_per_replica": round(vcpu, 3),
            "gb_ram_per_replica": round(gb_ram, 3),
            "cost_per_replica_per_month_eur": round(cost_per_replica_hour * pricing.hours_per_month, 2),
        },
    )
