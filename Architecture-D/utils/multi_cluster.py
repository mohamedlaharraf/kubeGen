"""
utils/multi_cluster.py

`target_clusters` (NormalizedSpec) capture l'intention "je veux déployer
sur plusieurs clusters/régions", mais ce pipeline reste conçu pour générer
le CONTENU d'un déploiement pour un cluster type — il ne peut pas connaître
les adresses API réelles des clusters cibles, ni l'URL du dépôt GitOps de
l'utilisateur. Plutôt que d'halluciner ces informations (via un LLM), on
génère un squelette **ArgoCD ApplicationSet** déterministe (générateur
`list`), avec des placeholders explicites à remplacer, accompagné d'un
avertissement clair.

Ce n'est PAS une orchestration multi-cluster fonctionnelle out-of-the-box
(impossible sans les vraies informations d'accès aux clusters) — c'est un
point de départ structurellement correct que l'utilisateur doit compléter.
"""

from __future__ import annotations


def generate_applicationset_skeleton(
    app_name: str, target_clusters: list[str], namespace: str,
    git_repo_placeholder: str = "https://REMPLACER-PAR-VOTRE-DEPOT-GIT.git",
    git_path_placeholder: str = "REMPLACER-PAR-LE-CHEMIN-DU-MANIFESTE",
) -> str:
    """
    Génère un `ApplicationSet` (`argoproj.io/v1alpha1`) avec un générateur
    `list` : une entrée par cluster dans `target_clusters`. Chaque entrée a
    une `url` PLACEHOLDER (l'adresse API du cluster cible n'est pas connue
    du pipeline) — à remplacer avant tout `kubectl apply` réel.
    """
    if not target_clusters:
        return ""

    cluster_entries = "\n".join(
        f"        - cluster: \"{name}\"\n"
        f"          url: \"REMPLACER-PAR-URL-API-DU-CLUSTER-{name}\"\n"
        for name in target_clusters
    )

    return f"""apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: {app_name}-multicluster
  namespace: argocd
spec:
  generators:
    - list:
        elements:
{cluster_entries}
  template:
    metadata:
      name: '{{{{cluster}}}}-{app_name}'
    spec:
      project: default
      source:
        repoURL: {git_repo_placeholder}
        targetRevision: HEAD
        path: {git_path_placeholder}
      destination:
        server: '{{{{url}}}}'
        namespace: {namespace}
      syncPolicy:
        syncOptions:
          - CreateNamespace=true
"""
