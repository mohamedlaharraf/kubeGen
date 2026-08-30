"""
benchmark/adapters/__init__.py

Registre central des architectures benchmarkees.

Les quatre architectures (A, B, C, D) sont enregistrees. Pour en ajouter
une cinquieme :
  1. Creer benchmark/adapters/architecture_x_....py avec une classe
     heritant de `ArchitectureAdapter` (voir base.py).
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
from .architecture_c_blackboard import BlackboardAdapter
from .architecture_d_debate import DebateAdapter

ARCHITECTURE_REGISTRY = {
    "A": SingleAgentAdapter,
    "B": PipelineAdapter,
    "C": BlackboardAdapter,
    "D": DebateAdapter,
}
