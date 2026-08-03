"""
llm_client.py
==============

Wrapper autour de l'API Google AI Studio pour appeler un modèle Gemma OU
Gemini avec une clé API (aistudio.google.com), via le SDK **`google-genai`**
(le package `google-generativeai` est déprécié et n'est plus maintenu). Le
modèle exact est piloté par `LLM_MODEL` (voir `config.py`) — ce client ne
fait aucune hypothèse sur la famille de modèle utilisée.

Deux garde-fous contre le problème observé en pratique — le modèle
"raisonne" en texte libre avant/au lieu de produire du JSON, et se fait
couper par la limite de tokens avant d'y arriver :

1. `response_mime_type="application/json"` est demandé à chaque appel :
   cela force l'API à contraindre la sortie du modèle à du JSON valide (et
   supprime les traces de raisonnement en texte libre qui, sinon,
   consomment le budget de tokens avant que le JSON n'arrive). Si le
   modèle configuré ne supporte pas ce mode, on retente automatiquement
   sans cette contrainte (voir `_generate`).
2. `max_output_tokens` est configurable (`LLM_MAX_OUTPUT_TOKENS`,
   8192 par défaut) et volontairement généreux, car les réponses des
   Agents 2 à 5 contiennent un YAML complet en plus du JSON englobant.

Fournit aussi un mode "offline" (STUB) sans appel réseau, utile pour
tester le câblage du graphe sans consommer de quota. Activer avec la
variable d'env PIPELINE_OFFLINE=1.
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from utils.llm_metrics import get_collector

_OFFLINE = os.getenv("PIPELINE_OFFLINE", "0") == "1"

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    from google import genai

    settings.validate()
    _client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    return _client


def _extract_token_usage(response) -> tuple[Optional[int], Optional[int]]:
    """
    Extraction DÉFENSIVE des tokens consommés depuis `response.usage_metadata`
    (SDK `google-genai`). Le champ peut être absent selon la version d'API/
    de modèle — dans ce cas on renvoie (None, None) plutôt que de deviner
    ou de planter : les métriques distinguent explicitement "0 token" de
    "inconnu" (voir `utils/llm_metrics.py`).
    """
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None, None
    prompt_tokens = getattr(usage, "prompt_token_count", None)
    completion_tokens = getattr(usage, "candidates_token_count", None)
    return prompt_tokens, completion_tokens


def _generate(full_prompt: str, temperature: float, force_json: bool, agent_name: str) -> str:
    from google.genai import types

    client = _get_client()

    config_kwargs = {
        "temperature": temperature,
        "max_output_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
    }
    if force_json:
        config_kwargs["response_mime_type"] = "application/json"

    started = time.perf_counter()
    succeeded = True
    prompt_tokens = completion_tokens = None
    try:
        response = client.models.generate_content(
            model=settings.GEMMA_MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        text = response.text or ""
        prompt_tokens, completion_tokens = _extract_token_usage(response)

        # Certains modèles/versions renvoient une réponse vide si le mode JSON
        # strict n'est pas supporté pour ce modèle. On le détecte ici pour
        # déclencher un retry sans contrainte JSON côté appelant.
        if force_json and not text.strip():
            succeeded = False
            raise ValueError("Réponse vide en mode JSON forcé (probablement non supporté par ce modèle).")

        return text
    except Exception:
        succeeded = False
        raise
    finally:
        latency = time.perf_counter() - started
        get_collector().record(
            agent=agent_name, latency_seconds=latency,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            succeeded=succeeded,
        )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def call_llm(system_prompt: str, user_prompt: str,
             temperature: Optional[float] = None, agent_name: str = "unknown") -> str:
    """
    Appelle le modèle configuré (Gemma ou Gemini, via Google AI Studio) avec
    un prompt système + un prompt utilisateur, et renvoie le texte brut de
    la réponse (du JSON, en mode normal).

    `agent_name` sert UNIQUEMENT à l'étiquetage des métriques d'exécution
    (latence/tokens par agent, voir `utils/llm_metrics.py`) — n'affecte en
    rien le comportement de l'appel. Chaque appel réel (y compris les
    tentatives de retry et le repli sans `force_json`) est enregistré
    séparément : ce sont des appels réseau distincts, avec leur propre
    latence et leur propre consommation de tokens.

    En mode offline, renvoie une réponse factice pour permettre de tester
    le pipeline sans clé API. Un appel factice est quand même enregistré
    dans les métriques (latence proche de zéro, tokens inconnus) pour que
    le nombre d'appels reste représentatif du nombre d'invocations réelles
    du pipeline, même sans coût associé.
    """
    if _OFFLINE:
        started = time.perf_counter()
        stub = "[OFFLINE_STUB] Aucun appel réseau effectué (PIPELINE_OFFLINE=1)."
        get_collector().record(
            agent=agent_name, latency_seconds=time.perf_counter() - started,
            prompt_tokens=None, completion_tokens=None, succeeded=True,
        )
        return stub

    temp = settings.LLM_TEMPERATURE if temperature is None else temperature
    # On renforce l'instruction anti-raisonnement directement dans le
    # prompt, en plus du response_mime_type : certains modèles ignorent
    # partiellement le mode JSON si le prompt système ne le rappelle pas.
    full_prompt = (
        f"{system_prompt}\n\n"
        "RAPPEL STRICT : réponds UNIQUEMENT avec du JSON valide. Aucun "
        "raisonnement, aucune explication, aucun texte avant ou après. Le "
        "premier caractère de ta réponse doit être '{' et le dernier '}'.\n\n"
        f"---\n\n{user_prompt}"
    )

    try:
        return _generate(full_prompt, temp, force_json=True, agent_name=agent_name)
    except Exception:
        # Repli : certains modèles (Gemma ou Gemini, selon version) ne
        # supportent pas encore response_mime_type=application/json sur
        # toutes les versions d'API. On retente sans cette contrainte
        # plutôt que d'échouer.
        return _generate(full_prompt, temp, force_json=False, agent_name=agent_name)


def extract_json(raw_text: str) -> dict:
    """
    Extrait le premier objet/array JSON valide et complet d'une réponse LLM,
    même s'il est entouré de texte parasite (raisonnement, fences markdown,
    texte après le JSON...).

    Stratégie robuste : on scanne le texte à la recherche de chaque '{' ou
    '[' et on tente un `json.JSONDecoder().raw_decode` à cette position.
    Le premier succès qui produit un objet/array (pas juste un nombre isolé,
    etc.) est retenu. Ça gère à la fois le cas "JSON valide suivi de texte
    parasite" (l'erreur 'Extra data' d'un simple json.loads) et le cas
    "JSON entouré de fences markdown".
    """
    text = raw_text.strip()
    decoder = json.JSONDecoder()

    candidates_positions = [i for i, c in enumerate(text) if c in "{["]

    last_error: Optional[Exception] = None
    for pos in candidates_positions:
        try:
            obj, _end = decoder.raw_decode(text, pos)
        except json.JSONDecodeError as e:
            last_error = e
            continue
        if isinstance(obj, (dict, list)):
            return obj

    raise ValueError(
        "Impossible de trouver un objet JSON valide dans la réponse du "
        f"LLM (dernière erreur : {last_error}).\n"
        f"Texte reçu (tronqué) :\n{raw_text[:2000]}"
    )
