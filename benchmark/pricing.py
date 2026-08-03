"""
benchmark/pricing.py

Table de prix par token, utilisée pour extrapoler un coût monétaire à
partir des tokens d'entrée/sortie mesurés.

⚠️ les valeurs ci-dessous proviennent d'agrégateurs tiers (pricepertoken.com
et recoupements croisés, consultés fin juillet 2026) et NON de la page
officielle https://ai.google.dev/gemini-api/docs/pricing. Les sources
consultées pour gemini-2.5-flash ne s'accordent d'ailleurs pas
parfaitement entre elles ($0.15/$1.25 chez pricepertoken.com vs des
estimations plus hautes ailleurs) -- confirmez vous-même sur la page
officielle (ou via Google AI Studio -> Billing) avant de citer un coût
en $ dans un livrable final. Notez aussi que Google a annoncé le retrait
de la famille Gemini 2.5 pour le 16 octobre 2026 : si votre benchmark
tourne après cette date, `gemini-2.5-flash` risque de ne plus être
disponible et il faudra migrer vers `gemini-3.5-flash` (ou équivalent).

Le nom du modèle réellement utilisé (`config.py` / variable d'env
GEMINI_MODEL) doit correspondre exactement à une clé de
PRICING_TABLE_USD_PER_1M_TOKENS ci-dessous, sinon le coût est calculé
comme `None` plutôt que silencieusement faux.

Prix en USD par 1 000 000 de tokens, (input, output).
"""
from __future__ import annotations

PRICING_TABLE_USD_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    # Modèles Gemini (sources croisées : OpenRouter, Requesty, CometAPI,
    # VentureBeat, BenchLM -- juillet 2026, forte convergence)
    "gemini-3.6-flash": (1.50, 7.50),      # sorti le 21 juillet 2026
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-pro": (2.00, 12.00),       # tarif <=200K tokens de prompt ; 4.00/18.00 au-delà
    # Modèles Gemini (source : pricepertoken.com, juillet 2026 -- à revérifier)
    "gemini-2.5-flash": (0.15, 1.25),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),  # tarif <=200K tokens de prompt ; passe à 2.50/15.00 au-delà
    # Anciens modèles Gemma (conservés au cas où une des architectures 
    # utiliserait encore un modèle Gemma plutôt que Gemini) :
    "gemma-4-31b-it": (0.10, 0.35),
    "gemma-4-26b-a4b-it": (0.07, 0.30),
    "gemma-3-4b-it": (0.05, 0.10),
    # Ajoutez ici tout autre modèle utilisé par les architectures 
    # (elles peuvent très bien tourner sur un modèle différent).
}


class UnknownModelPricingError(Exception):
    pass


def estimate_cost_usd(
    model: str, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    """Retourne None (plutôt qu'un chiffre trompeur) si les tokens ou le
    prix du modèle sont inconnus -- mieux vaut un trou visible dans le
    rapport qu'un coût silencieusement sous-estimé."""
    if input_tokens is None or output_tokens is None:
        return None
    if model not in PRICING_TABLE_USD_PER_1M_TOKENS:
        return None
    price_in, price_out = PRICING_TABLE_USD_PER_1M_TOKENS[model]
    return round((input_tokens * price_in + output_tokens * price_out) / 1_000_000, 6)
