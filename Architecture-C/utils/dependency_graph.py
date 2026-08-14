"""
utils/dependency_graph.py — détection de cycles dans les dépendances
`ServiceComponent.depends_on` d'une architecture microservices.

`depends_on` est documentaire (il n'affecte pas l'ordre de génération : le
pipeline reste une chaîne stricte, chaque composant est généré
indépendamment). Mais une dépendance circulaire (A dépend de B qui dépend
de A) est presque toujours le signe d'une erreur de conception à signaler
à l'utilisateur, même si le pipeline lui-même n'en souffre pas.
"""

from __future__ import annotations


def find_circular_dependencies(components: list) -> list[list[str]]:
    """
    Détecte les cycles dans le graphe `component_name -> depends_on`.
    Renvoie la liste des cycles trouvés (chaque cycle est une liste de
    noms de composants, ex: ["a", "b", "c", "a"]).

    `components` : liste d'objets avec `.component_name` et `.depends_on`
    (fonctionne avec des `ServiceComponent` Pydantic ou de simples objets
    similaires, pour rester facilement testable sans dépendance au schéma).
    """
    graph = {c.component_name: list(c.depends_on) for c in components}
    cycles: list[list[str]] = []

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in graph}
    path: list[str] = []

    def visit(node: str) -> None:
        if node not in graph:
            return  # dépendance vers un composant inexistant : hors périmètre ici
        color[node] = GRAY
        path.append(node)
        for neighbor in graph[node]:
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:] + [neighbor])
            elif color[neighbor] == WHITE:
                visit(neighbor)
        path.pop()
        color[node] = BLACK

    for name in graph:
        if color[name] == WHITE:
            visit(name)

    return cycles


def find_dangling_dependencies(components: list) -> list[str]:
    """Signale les `depends_on` qui référencent un composant inexistant
    (faute de frappe probable dans `component_name`)."""
    names = {c.component_name for c in components}
    errors = []
    for c in components:
        for dep in c.depends_on:
            if dep not in names:
                errors.append(
                    f"'{c.component_name}' dépend de '{dep}', qui n'existe pas "
                    f"parmi les composants générés."
                )
    return errors
