"""
utils/sidecar_injection.py — registre DÉTERMINISTE des sidecars à
injection automatique connus (Dapr, Istio, Linkerd, Consul Connect...).

Contexte (bug observé en production, Architecture C) : l'Agent 2 décidait
seul, via son prompt LLM, qu'un sidecar connu (ex: Dapr) devait être
traduit en annotations plutôt qu'en conteneur manuel — mais cette décision
n'était jamais transmise à l'Agent 3 (validation) ni à l'Agent 5
(vérification finale), qui vérifiaient chacun, via LEUR PROPRE prompt LLM,
que "les sidecars déclarés apparaissent bien comme conteneurs dans le
Pod". Résultat : l'Agent 3 "corrigeait" en rajoutant le conteneur que
l'Agent 2 avait volontairement omis, recréant le doublon (annotations +
conteneur manuel) que l'Agent 2 cherchait justement à éviter.

Logique UNIQUE, partagée par tous les agents concernés (Agent 2, Agent 3,
Agent 5) — même principe que `utils/global_constraints.py` : mieux vaut un
seul endroit à corriger si la liste doit évoluer (ajout d'un futur mesh),
plutôt que plusieurs prompts qui divergent silencieusement avec le temps.
La classification elle-même est un simple pattern-matching Python, PAS un
jugement LLM : elle est donc identique quel que soit l'agent qui l'appelle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

MANUAL_CONTAINER = "manual_container"
ANNOTATIONS = "annotations"


@dataclass(frozen=True)
class AutoInjectSidecar:
    """Définition d'un sidecar à injection automatique reconnu."""
    match: tuple[str, ...]  # sous-chaînes (name/purpose, lowercase) qui déclenchent la reconnaissance
    annotations: Callable[[str, int | None], dict[str, str]]
    requires_operator: str  # nom de l'opérateur/CRD requis dans le cluster cible, pour les warnings


def _dapr_annotations(component_name: str, app_port: int | None) -> dict[str, str]:
    ann = {
        "dapr.io/enabled": "true",
        "dapr.io/app-id": component_name,
    }
    if app_port is not None:
        ann["dapr.io/app-port"] = str(app_port)
    return ann


def _istio_annotations(component_name: str, app_port: int | None) -> dict[str, str]:
    return {"sidecar.istio.io/inject": "true"}


def _linkerd_annotations(component_name: str, app_port: int | None) -> dict[str, str]:
    return {"linkerd.io/inject": "enabled"}


def _consul_connect_annotations(component_name: str, app_port: int | None) -> dict[str, str]:
    ann = {"consul.hashicorp.com/connect-inject": "true"}
    if app_port is not None:
        ann["consul.hashicorp.com/connect-service-port"] = str(app_port)
    return ann


# Registre central : clé = identifiant interne, PAS un texte affiché tel quel.
AUTO_INJECT_SIDECARS: dict[str, AutoInjectSidecar] = {
    "dapr": AutoInjectSidecar(
        match=("dapr",),
        annotations=_dapr_annotations,
        requires_operator="Dapr (https://dapr.io)",
    ),
    "istio": AutoInjectSidecar(
        match=("istio", "envoy sidecar", "service mesh envoy"),
        annotations=_istio_annotations,
        requires_operator="Istio (sidecar injector)",
    ),
    "linkerd": AutoInjectSidecar(
        match=("linkerd",),
        annotations=_linkerd_annotations,
        requires_operator="Linkerd (proxy injector)",
    ),
    "consul_connect": AutoInjectSidecar(
        match=("consul connect", "consul-connect", "consul service mesh"),
        annotations=_consul_connect_annotations,
        requires_operator="Consul Connect (connect-injector)",
    ),
}


def classify_sidecar(name: str, purpose: str) -> str | None:
    """
    Retourne la clé de `AUTO_INJECT_SIDECARS` reconnue pour ce sidecar
    (d'après `name`/`purpose`), ou None si c'est un sidecar "classique"
    (conteneur manuel, comportement inchangé).
    """
    text = f"{name} {purpose}".lower()
    for key, cfg in AUTO_INJECT_SIDECARS.items():
        if any(m in text for m in cfg.match):
            return key
    return None


def injection_mode(name: str, purpose: str) -> str:
    """Raccourci : "annotations" ou "manual_container" pour un sidecar donné."""
    return ANNOTATIONS if classify_sidecar(name, purpose) else MANUAL_CONTAINER


def build_injection_mode_map(sidecars: list, component_name: str) -> dict[str, dict]:
    """
    Construit, pour TOUS les sidecars d'un composant, un mapping
    sidecar_name -> {"mode": ..., "annotations": {...} | None,
    "requires_operator": ... | None}. Utilisé par l'Agent 2 pour générer
    et par les Agents 3/5 pour valider — même source de vérité des deux
    côtés.
    """
    result: dict[str, dict] = {}
    for sc in sidecars:
        key = classify_sidecar(sc.name, sc.purpose)
        if key:
            cfg = AUTO_INJECT_SIDECARS[key]
            app_port = sc.ports[0].container_port if sc.ports else None
            result[sc.name] = {
                "mode": ANNOTATIONS,
                "annotations": cfg.annotations(component_name, app_port),
                "requires_operator": cfg.requires_operator,
            }
        else:
            result[sc.name] = {
                "mode": MANUAL_CONTAINER,
                "annotations": None,
                "requires_operator": None,
            }
    return result
