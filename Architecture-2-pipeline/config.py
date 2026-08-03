"""
config.py — chargement de la configuration depuis l'environnement / .env
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    # `LLM_MODEL` est le nom à privilégier désormais (le pipeline n'est plus
    # figé sur la famille Gemma : n'importe quel modèle Google AI Studio
    # convient, via le même SDK `google-genai`). `GEMMA_MODEL` reste lu en
    # repli pour ne pas casser les `.env` existants qui définissent encore
    # cette variable. Défaut : un modèle du tier gratuit AI Studio (les
    # modèles "Pro" ne sont plus disponibles gratuitement depuis avril 2026 —
    # voir README pour le détail des modèles Flash/Flash-Lite éligibles).
    GEMMA_MODEL: str = os.getenv("LLM_MODEL", os.getenv("GEMMA_MODEL", "gemini-3.6-flash"))
    AGENT1_MAX_REPAIR_ATTEMPTS: int = int(
        os.getenv("AGENT1_MAX_REPAIR_ATTEMPTS", "2")
    )
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    LLM_MAX_OUTPUT_TOKENS: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "8192"))
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "output")

    @classmethod
    def validate(cls) -> None:
        if not cls.GOOGLE_API_KEY:
            raise RuntimeError(
                "GOOGLE_API_KEY manquant. Copiez .env.example vers .env et "
                "renseignez votre clé obtenue sur https://aistudio.google.com/app/apikey"
            )
        # Le SDK `google-genai` accepte indifféremment GOOGLE_API_KEY et
        # GEMINI_API_KEY, et choisit GOOGLE_API_KEY si les deux sont
        # présentes dans l'environnement (variable d'env système, pas
        # forcément dans .env) — silencieusement, hormis un message
        # d'information imprimé par le SDK lui-même. Si ces deux variables
        # ne correspondent PAS à la même clé/au même projet AI Studio
        # (ex: une ancienne clé encore présente dans l'environnement
        # Windows), la clé effectivement utilisée peut être différente de
        # celle attendue, avec des erreurs peu explicites (quota, modèle
        # non disponible, clé invalide...). On avertit explicitement ici
        # plutôt que de laisser l'utilisateur découvrir ça par un
        # ClientError/ServerError obscur.
        if os.getenv("GEMINI_API_KEY") and os.getenv("GOOGLE_API_KEY"):
            print(
                "⚠️  GOOGLE_API_KEY et GEMINI_API_KEY sont TOUTES LES DEUX "
                "définies dans l'environnement. Le SDK utilisera GOOGLE_API_KEY "
                "— si ce n'est pas la clé/le projet AI Studio voulu (ex: une "
                "ancienne variable système encore présente), désactivez "
                "GEMINI_API_KEY (`Remove-Item Env:GEMINI_API_KEY` sous "
                "PowerShell pour la session courante) ou vérifiez que les "
                "deux clés proviennent bien du même projet AI Studio."
            )


settings = Settings()
