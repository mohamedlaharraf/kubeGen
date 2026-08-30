"""
config.py — chargement de la configuration depuis l'environnement / .env
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    # Aligné sur Architecture-2-pipeline pour une comparaison de benchmark
    # à modèle égal (E6 - instrumentation homogène) : sans ça, Architecture
    # C serait comparée à B sur un modèle différent, ce qui biaiserait
    # latence/coût sans rapport avec le mérite architectural lui-même.
    GEMMA_MODEL: str = os.getenv("LLM_MODEL", os.getenv("GEMMA_MODEL", "gemma-4-31b-it"))
    AGENT1_MAX_REPAIR_ATTEMPTS: int = int(
        os.getenv("AGENT1_MAX_REPAIR_ATTEMPTS", "2")
    )
    # Architecture C : borne de la boucle de réparation post-Agent 5 (voir
    # agents/agent_repair.py, graph.py::_route_after_agent5). Même valeur
    # par défaut que AGENT1_MAX_REPAIR_ATTEMPTS par cohérence de conception,
    # mais un mécanisme distinct — pas de raison de forcer la même valeur
    # si vous voulez les régler séparément.
    MAX_REPAIR_ATTEMPTS: int = int(os.getenv("MAX_REPAIR_ATTEMPTS", "2"))
    # Boucle Generator <-> Validator (distincte de MAX_REPAIR_ATTEMPTS
    # ci-dessus, qui borne la réparation post-Agent 5). Voir
    # agents/agent3_validation.py, agents/agent2_template.py::regenerate_with_feedback,
    # graph.py::_route_after_agent3.
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "3"))
    # Architecture D : borne du débat multi-agents (Strategy A/B/C) à
    # l'étape d'optimisation énergétique. 1 = une seule passe de critique
    # après les propositions initiales (défaut, cf. cahier des charges
    # "1 to 2 turns max") ; 2 = une seconde passe de critique sur les
    # propositions déjà révisées. Volontairement PLAFONNÉ à 2 dans le code
    # (voir agents/agent4_debate.py) : au-delà, le coût en appels LLM
    # croît sans gain de convergence observé (cf. patron Group Chat, dont
    # la littérature documente justement ce risque de non-convergence).
    DEBATE_MAX_TURNS: int = int(os.getenv("DEBATE_MAX_TURNS", "1"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    LLM_MAX_OUTPUT_TOKENS: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "24576"))
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "output")

    @classmethod
    def validate(cls) -> None:
        if not cls.GOOGLE_API_KEY:
            raise RuntimeError(
                "GOOGLE_API_KEY manquant. Copiez .env.example vers .env et "
                "renseignez votre clé obtenue sur https://aistudio.google.com/app/apikey"
            )


settings = Settings()
