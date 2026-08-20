"""
graph.py — point d'entrée de compatibilité pour la construction du
pipeline (Architecture D).

Depuis l'introduction de `orchestrator.py`, ce fichier ne fait plus QUE
déléguer : toute la logique de câblage (noeuds, arêtes, cycles bornés) et
de décision de routage vit maintenant dans `Orchestrator`
(voir orchestrator.py pour le détail). `build_pipeline()` est conservé
ici tel quel pour ne pas casser le code existant qui fait
`from graph import build_pipeline` (main.py, tests/) -- un seul point
d'entrée fonctionnel, une seule implémentation, pas de duplication.

    START -> agent1 -> agent2 -> agent3 <-> [fix]* -> agent4_debate -> agent5 <-> [repair]* -> END

`agent4_debate` est, au niveau du GRAPHE, un noeud unique comme
`agent4_energie` l'était en Architecture C : le fan-out parallèle des
3 stratégies + le débat + le Juge sont entièrement internes à ce noeud
(voir agents/agent4_debate.py). Les deux cycles du graphe (bornés
indépendamment par MAX_ITERATIONS et MAX_REPAIR_ATTEMPTS) sont
documentés en détail dans orchestrator.py, et inchangés par rapport à C.
"""

from __future__ import annotations

from orchestrator import Orchestrator

# Une seule instance module-level : le graphe est mis en cache après la
# première construction (voir Orchestrator.build()), donc appeler
# build_pipeline() plusieurs fois ne reconstruit pas le graphe à chaque
# fois -- comportement identique à l'ancienne fonction module-level.
_orchestrator = Orchestrator()


def build_pipeline():
    """Compatibilité : construit (ou récupère depuis le cache) le graphe
    LangGraph compilé. Voir Orchestrator.build() pour l'implémentation
    réelle."""
    return _orchestrator.build()


def get_orchestrator() -> Orchestrator:
    """Accès direct à l'Orchestrateur, si vous avez besoin d'appeler
    `.run(user_request)` directement ou d'inspecter ses décisions de
    routage sans repasser par build_pipeline()."""
    return _orchestrator
