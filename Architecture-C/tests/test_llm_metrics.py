"""
tests/test_llm_metrics.py

Deux niveaux de test, volontairement séparés :
1. `LLMMetricsCollector` seul (agrégation, cas 0 appel, tokens inconnus).
2. L'instrumentation réelle dans `llm_client.py`, avec le client Google
   GenAI mocké au niveau `_get_client()` — un cran plus bas que les tests
   du pipeline (qui mockent `call_llm` directement au niveau de chaque
   agent et ne passent donc jamais par ce code réel). C'est ici, et
   seulement ici, que la latence/l'extraction de tokens sont vraiment
   exercées.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.llm_metrics import LLMMetricsCollector, get_collector  # noqa: E402


# ---------------------------------------------------------------------------
# Collecteur seul
# ---------------------------------------------------------------------------

def test_empty_collector_summary_has_zero_calls():
    c = LLMMetricsCollector()
    s = c.summary()
    assert s["total_calls"] == 0
    assert s["total_latency_seconds"] == 0.0
    assert s["tokens_known"] is False
    assert s["by_agent"] == {}


def test_reset_clears_previous_calls():
    c = LLMMetricsCollector()
    c.record("Agent 1", 0.5, 100, 50)
    assert c.summary()["total_calls"] == 1
    c.reset()
    assert c.summary()["total_calls"] == 0


def test_aggregation_across_multiple_agents():
    c = LLMMetricsCollector()
    c.record("Agent 1", 0.5, 100, 50)
    c.record("Agent 1", 0.3, 80, 20)
    c.record("Agent 2", 1.0, 200, 100)
    s = c.summary()

    assert s["total_calls"] == 3
    assert s["total_latency_seconds"] == 1.8
    assert s["total_prompt_tokens"] == 380
    assert s["total_completion_tokens"] == 170
    assert s["by_agent"]["Agent 1"]["calls"] == 2
    assert s["by_agent"]["Agent 2"]["calls"] == 1


def test_failed_calls_are_counted_separately():
    c = LLMMetricsCollector()
    c.record("Agent 1", 0.5, 100, 50, succeeded=True)
    c.record("Agent 1", 0.2, None, None, succeeded=False)
    s = c.summary()
    assert s["total_calls"] == 2
    assert s["failed_calls"] == 1
    assert s["by_agent"]["Agent 1"]["failed_calls"] == 1


def test_unknown_tokens_not_confused_with_zero_tokens():
    """Un appel offline (tokens=None) ne doit jamais gonfler artificiellement
    total_prompt_tokens à 0 de façon indiscernable d'un vrai 0 token."""
    c = LLMMetricsCollector()
    c.record("Agent 1", 0.1, None, None)  # offline stub
    s = c.summary()
    assert s["tokens_known"] is False
    assert s["total_prompt_tokens"] == 0
    assert s["by_agent"]["Agent 1"]["tokens_known"] is False


def test_mixed_known_and_unknown_tokens():
    c = LLMMetricsCollector()
    c.record("Agent 1", 0.1, None, None)       # offline / inconnu
    c.record("Agent 1", 0.5, 100, 50)           # connu
    s = c.summary()
    assert s["tokens_known"] is True
    assert s["total_prompt_tokens"] == 100  # seul l'appel connu compte
    assert s["by_agent"]["Agent 1"]["tokens_known"] is True


# ---------------------------------------------------------------------------
# Instrumentation réelle de llm_client.py (client mocké, pas d'appel réseau)
# ---------------------------------------------------------------------------

def _fake_response(text, prompt_tokens, completion_tokens):
    resp = MagicMock()
    resp.text = text
    if prompt_tokens is None and completion_tokens is None:
        resp.usage_metadata = None
    else:
        resp.usage_metadata.prompt_token_count = prompt_tokens
        resp.usage_metadata.candidates_token_count = completion_tokens
    return resp


def test_call_llm_records_latency_and_tokens_on_success():
    import llm_client

    get_collector().reset()
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = _fake_response(
        '{"ok": true}', 300, 120,
    )

    with patch.object(llm_client, "_get_client", return_value=fake_client):
        result = llm_client.call_llm("sys", "user", agent_name="Agent Test")

    assert result == '{"ok": true}'
    s = get_collector().summary()
    assert s["total_calls"] == 1
    assert s["total_prompt_tokens"] == 300
    assert s["total_completion_tokens"] == 120
    assert s["by_agent"]["Agent Test"]["calls"] == 1
    assert s["total_latency_seconds"] >= 0.0


def test_call_llm_missing_usage_metadata_records_unknown_tokens():
    import llm_client

    get_collector().reset()
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = _fake_response(
        '{"ok": true}', None, None,
    )

    with patch.object(llm_client, "_get_client", return_value=fake_client):
        llm_client.call_llm("sys", "user", agent_name="Agent Test")

    s = get_collector().summary()
    assert s["tokens_known"] is False


def test_call_llm_fallback_path_records_two_calls():
    """Le repli sans force_json (quand le mode JSON strict échoue) déclenche
    un DEUXIÈME appel réseau réel -- les deux doivent être comptabilisés
    séparément, pas fusionnés en un seul."""
    import llm_client

    get_collector().reset()
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = [
        _fake_response("", 50, 0),
        _fake_response('{"ok": true}', 60, 80),
    ]

    with patch.object(llm_client, "_get_client", return_value=fake_client):
        result = llm_client.call_llm("sys", "user", agent_name="Agent Test")

    assert result == '{"ok": true}'
    s = get_collector().summary()
    assert s["total_calls"] == 2
    assert s["failed_calls"] == 1
    assert s["total_prompt_tokens"] == 110


def test_offline_mode_records_a_call_with_near_zero_latency(monkeypatch):
    import llm_client

    monkeypatch.setattr(llm_client, "_OFFLINE", True)
    get_collector().reset()

    result = llm_client.call_llm("sys", "user", agent_name="Agent Test")

    assert "OFFLINE_STUB" in result
    s = get_collector().summary()
    assert s["total_calls"] == 1
    assert s["tokens_known"] is False
    assert s["total_latency_seconds"] < 0.1
