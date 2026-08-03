"""
utils/cluster_validate.py — validation contre les VRAIS schémas Kubernetes,
au-delà des checks internes de k8s_validate.py.

Contexte : k8s_validate.py fait des vérifications déterministes "maison"
(cohérence de noms, format de quantités, cron...). C'est utile mais ce
n'est PAS une validation contre les schémas OpenAPI réels de l'API
Kubernetes — un champ mal orthographié, un type invalide sur un champ que
k8s_validate.py ne connaît pas, une valeur d'enum invalide, tout ça peut
passer au travers.

Ce module ajoute deux couches, TOUTES DEUX OPTIONNELLES et dégradant
proprement si les outils externes ne sont pas installés (aucun des deux
n'est un pré-requis pour utiliser le pipeline) :

1. `run_kubeconform()` — valide chaque document contre le schéma OpenAPI
   officiel de son `apiVersion`/`kind` (+ schémas CRD tiers comme KEDA/
   Istio/Prometheus Operator via le catalogue par défaut de kubeconform).
2. `run_dry_run_apply()` — `kubectl apply --dry-run=server` contre un
   cluster réel (ex: kind/k3d local), qui déclenche aussi les admission
   webhooks (CRD validation stricte, policies OPA/Kyverno si présentes) —
   la validation la plus proche d'un vrai déploiement sans en faire un.
3. `check_cluster_dependencies()` — interroge le cluster cible pour
   confirmer que les CRD dont dépendent les ressources générées (KEDA,
   Istio, Prometheus Operator, Argo Rollouts) sont bien installées.
"""

from __future__ import annotations

import json
import shutil
import subprocess


def _binary_available(name: str) -> bool:
    return shutil.which(name) is not None


def run_kubeconform(manifest_yaml: str, timeout: int = 30) -> dict:
    """
    Valide le YAML contre les schémas OpenAPI Kubernetes officiels (+ CRD
    tierces connues via le catalogue par défaut de kubeconform :
    https://github.com/yannh/kubeconform).

    Renvoie {"available": bool, "passed": bool, "errors": [...], "raw": str}.
    Si le binaire `kubeconform` n'est pas installé, renvoie
    `available=False` sans lever d'exception — c'est un enrichissement
    optionnel, pas un pré-requis.
    """
    if not _binary_available("kubeconform"):
        return {
            "available": False,
            "passed": None,
            "errors": [],
            "raw": "kubeconform non installé (voir https://github.com/yannh/kubeconform "
                   "pour l'installer — optionnel mais fortement recommandé avant "
                   "tout déploiement réel).",
        }

    try:
        result = subprocess.run(
            ["kubeconform", "-summary", "-output", "json",
             "-schema-location", "default",
             # Catalogue communautaire de schémas CRD (KEDA, Istio, Prometheus
             # Operator, Argo Rollouts...) : sans ça, ces CRD seraient
             # "skipped" (non validées) plutôt que réellement vérifiées.
             "-schema-location",
             "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/"
             "{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json",
             "-ignore-missing-schemas",  # CRD vraiment inconnues : signalées, pas bloquantes
             "-"],
            input=manifest_yaml, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"available": True, "passed": False, "errors": ["kubeconform: timeout"], "raw": ""}

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "available": True, "passed": result.returncode == 0,
            "errors": [] if result.returncode == 0 else [result.stdout or result.stderr],
            "raw": result.stdout,
        }

    errors = []
    for res in parsed.get("resources", []):
        status = res.get("status", "")
        if status in ("statusInvalid", "statusError"):
            errors.append(
                f"{res.get('kind', '?')}/{res.get('name', '?')} : "
                f"{res.get('msg', 'invalide selon le schéma OpenAPI Kubernetes')}"
            )

    return {
        "available": True,
        "passed": len(errors) == 0,
        "errors": errors,
        "raw": result.stdout,
    }


def run_dry_run_apply(manifest_yaml: str, kube_context: str | None = None,
                       timeout: int = 60) -> dict:
    """
    `kubectl apply --dry-run=server -f -` contre le cluster actuellement
    configuré (kubeconfig courant). Nécessite un accès réseau à un vrai
    cluster (ex: kind/k3d local) — c'est le check le plus proche d'un
    déploiement réel sans en faire un : il déclenche aussi les admission
    webhooks (donc les policies OPA/Kyverno/Gatekeeper si le cluster en a).

    Renvoie {"available": bool, "passed": bool, "errors": [...], "raw": str}.
    """
    if not _binary_available("kubectl"):
        return {
            "available": False, "passed": None, "errors": [],
            "raw": "kubectl non installé — dry-run-apply ignoré.",
        }

    cmd = ["kubectl", "apply", "--dry-run=server", "-f", "-"]
    if kube_context:
        cmd += ["--context", kube_context]

    try:
        result = subprocess.run(cmd, input=manifest_yaml, capture_output=True,
                                 text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"available": True, "passed": False,
                "errors": ["kubectl: timeout (cluster injoignable ?)"], "raw": ""}
    except FileNotFoundError:
        return {"available": False, "passed": None, "errors": [], "raw": "kubectl introuvable."}

    if result.returncode != 0:
        errors = [line for line in (result.stderr or "").splitlines() if line.strip()]
        return {"available": True, "passed": False,
                "errors": errors or ["kubectl apply --dry-run=server a échoué (voir raw)."],
                "raw": result.stderr}

    return {"available": True, "passed": True, "errors": [], "raw": result.stdout}


# CRD (Custom Resource Definition) requises par kind générable par ce
# pipeline, quand la fonctionnalité correspondante est utilisée.
DEPENDENCY_CRDS = {
    "ScaledObject": "scaledobjects.keda.sh",
    "VirtualService": "virtualservices.networking.istio.io",
    "DestinationRule": "destinationrules.networking.istio.io",
    "ServiceMonitor": "servicemonitors.monitoring.coreos.com",
    "Rollout": "rollouts.argoproj.io",
    "HTTPRoute": "httproutes.gateway.networking.k8s.io",
    "Gateway": "gateways.gateway.networking.k8s.io",
    "Certificate": "certificates.cert-manager.io",
    "ApplicationSet": "applicationsets.argoproj.io",
}


def check_cluster_dependencies(kinds_used: set[str], kube_context: str | None = None,
                                timeout: int = 20) -> dict:
    """
    Interroge le cluster cible (`kubectl get crd`) pour confirmer que les
    CRD requises par les `kinds_used` (ex: {"ScaledObject", "Ingress"})
    sont bien installées. Ne fait AUCUNE régénération automatique en cas
    de manque (ce pipeline reste une chaîne stricte, sans retour en
    arrière) — se contente de le signaler clairement, avec le fallback
    déjà documenté par l'Agent 4/l'Agent 2 dans leurs `warnings`.
    """
    needed = {kind: crd for kind, crd in DEPENDENCY_CRDS.items() if kind in kinds_used}
    if not needed:
        return {"available": True, "checked": True, "missing": [], "raw": ""}

    if not _binary_available("kubectl"):
        return {"available": False, "checked": False, "missing": [],
                "raw": "kubectl non installé — vérification des CRD ignorée."}

    cmd = ["kubectl", "get", "crd", "-o", "name"]
    if kube_context:
        cmd += ["--context", kube_context]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"available": True, "checked": False, "missing": [],
                "raw": "Cluster injoignable — vérification des CRD ignorée."}

    if result.returncode != 0:
        return {"available": True, "checked": False, "missing": [],
                "raw": f"kubectl get crd a échoué : {result.stderr}"}

    installed_crds = result.stdout
    missing = [
        f"{kind} nécessite la CRD '{crd}', absente du cluster cible."
        for kind, crd in needed.items() if crd not in installed_crds
    ]
    return {"available": True, "checked": True, "missing": missing, "raw": result.stdout}
