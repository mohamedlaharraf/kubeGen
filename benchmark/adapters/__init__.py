"""
benchmark/adapters/__init__.py

Registre central des architectures benchmarkees.

POUR AJOUTER L'ARCHITECTURE B (pipeline multi-agents), C (blackboard) ou
D (debat) plus tard :
  1. Creer benchmark/adapters/architecture_b_pipeline.py (etc.) avec une
     classe heritant de `ArchitectureAdapter` (voir base.py).
  2. L'importer et l'ajouter a ARCHITECTURE_REGISTRY ci-dessous.
  3. C'est tout -- `run_benchmark.py`, les validateurs, le scoring energie
     et le rapport n'ont rien a changer.

Le registre est un dict {id: classe (pas d'instance)} pour que
`run_benchmark.py` puisse choisir de n'instancier (et donc de ne
demander une cle API) que pour les architectures effectivement
selectionnees via --architectures.
"""
from .architecture_a_single_agent import SingleAgentAdapter
from .architecture_b_pipeline import PipelineAdapter

ARCHITECTURE_REGISTRY = {
    "A": SingleAgentAdapter,
    "B": PipelineAdapter,
    # "C": ArchitectureCBlackboardAdapter, # TODO
    # "D": ArchitectureDDebateAdapter,     # TODO
}
