"""
utils/global_constraints.py — le mécanisme de filtrage central du
blackboard (Architecture C).

Logique UNIQUE, partagée par tous les agents qui doivent voir les
contraintes transversales (Agent 2, Agent 4, et la boucle de réparation) :
mieux vaut un seul endroit à corriger si le filtrage doit évoluer, plutôt
que N copies qui divergent silencieusement avec le temps.

Voir schemas.GlobalConstraint pour le raisonnement complet sur pourquoi ce
mécanisme existe (bug PCI-DSS/PostgresCluster observé sur l'Architecture B
en production : une contrainte "chiffrement au repos pour tous les
volumes" posée sur un composant n'était jamais visible par le composant
voisin qui avait effectivement un volume).
"""
from __future__ import annotations


def filter_constraints(component_name: str | None, global_constraints: list) -> list:
    """
    Filtre les GlobalConstraint pertinentes pour UNE ressource donnée.

    `component_name=None` pour une ressource sans nom de composant au sens
    du schéma (ex: un fragment best-effort d'unmapped_requirements) : dans
    ce cas on inclut PRUDEMMENT toutes les contraintes non-'specific' —
    une ressource hors schéma peut très bien être concernée par "tous les
    volumes"/"tous les conteneurs" sans qu'on puisse le vérifier
    autrement, et c'est précisément le cas qui a été manqué en production.
    """
    relevant = []
    for c in global_constraints:
        if c.scope != "specific":
            relevant.append(c)
        elif component_name and component_name in c.applies_to:
            relevant.append(c)
    return relevant


def constraints_block(constraints: list) -> str:
    """Formate un bloc de prompt prêt à injecter, ou une chaîne vide si
    rien n'est applicable (ne pas gonfler le prompt inutilement)."""
    if not constraints:
        return ""
    lines = "\n".join(f"- [{c.scope}/{c.category}] {c.text}" for c in constraints)
    return (
        "\n\nContraintes globales applicables (définies au niveau de la "
        "demande entière, pas spécifiques à ce composant, mais qui "
        "s'appliquent ici d'après leur scope) :\n" + lines +
        "\n\nCes contraintes ont la même priorité que les champs "
        "structurés ci-dessus : ne les ignore pas au prétexte qu'elles "
        "ne figurent pas explicitement dans les champs du composant."
    )
