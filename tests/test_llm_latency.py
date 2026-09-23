"""Latency/timeout regression tests for the LLM chat pipeline.

Covers: 8s per-provider socket timeout, parallel provider race with
first-success-wins, hard ~10s request budget, and the no-double-LLM rule for
unclassifiable messages. No real network access is needed: the provider
functions are stubbed.
"""
import time

import pytest

import backend.llm as llm
import backend.intent_router as ir

# The conftest `no_llm` autouse fixture stubs llm.query_llm during tests; keep a
# reference to the REAL implementation (captured at import, before patching) so
# the race/budget tests can exercise it directly.
REAL_QUERY_LLM = llm.query_llm


@pytest.fixture(autouse=True)
def _hermetic_router(monkeypatch):
    """Keep network/store/chat side effects out of these tests."""
    for name in ("call_openai_api", "call_gemini_api", "call_anthropic_api", "call_mistral_api"):
        monkeypatch.setattr(llm, name, lambda *a, **k: None)
    yield


def test_provider_timeout_default_is_8s():
    assert llm._DEFAULT_TIMEOUT == 8


def test_query_llm_returns_first_success_regardless_of_role_order(monkeypatch):
    def slow_main(*a, **k):
        time.sleep(0.5)
        return "slow main answer"

    def fast_fallback(*a, **k):
        return "fast fallback answer"

    monkeypatch.setattr(llm, "call_openai_api", slow_main)
    monkeypatch.setattr(llm, "call_gemini_api", fast_fallback)
    assert REAL_QUERY_LLM("hi") == "fast fallback answer"


def test_query_llm_role_tiebreak_when_all_equally_fast(monkeypatch):
    # critic preference is Anthropic first. Stagger completions slightly so the
    # race is deterministic: the role-preferred (first-listed) provider wins
    # when it is also the first to complete.
    monkeypatch.setattr(llm, "call_anthropic_api", lambda *a, **k: "critic answer")
    monkeypatch.setattr(llm, "call_gemini_api", lambda *a, **k: (time.sleep(0.2), "gemini answer")[1])
    monkeypatch.setattr(llm, "call_openai_api", lambda *a, **k: (time.sleep(0.3), "main answer")[1])
    monkeypatch.setattr(llm, "call_mistral_api", lambda *a, **k: (time.sleep(0.4), "mistral answer")[1])
    assert REAL_QUERY_LLM("hi", role="critic") == "critic answer"


def test_query_llm_first_completed_wins_even_if_not_role_preferred(monkeypatch):
    # main prefers OpenAI, but Gemini finishing first must win (first-success).
    monkeypatch.setattr(llm, "call_openai_api", lambda *a, **k: (time.sleep(0.5), "slow main answer")[1])
    monkeypatch.setattr(llm, "call_gemini_api", lambda *a, **k: "fast fallback answer")
    assert REAL_QUERY_LLM("hi") == "fast fallback answer"


def test_query_llm_budget_cap_limits_wait(monkeypatch):
    # Remaining budget 1s: a 5s provider must not be awaited to completion.
    def never_in_time(*a, **k):
        time.sleep(5)
        return "too late"

    monkeypatch.setattr(llm, "call_openai_api", never_in_time)
    llm.set_llm_budget(1.0)
    try:
        t0 = time.monotonic()
        res = REAL_QUERY_LLM("hi")
        elapsed = time.monotonic() - t0
    finally:
        llm.clear_llm_budget()
    assert res is None
    assert elapsed < 2.5


def test_query_llm_skips_entirely_when_budget_already_spent(monkeypatch):
    called = {"n": 0}

    def spy(*a, **k):
        called["n"] += 1
        return "answer"

    monkeypatch.setattr(llm, "call_openai_api", spy)
    llm.set_llm_budget(-1)  # already exhausted
    try:
        assert REAL_QUERY_LLM("hi") is None
    finally:
        llm.clear_llm_budget()
    assert called["n"] == 0


def test_handle_intent_message_clears_budget_after_run(monkeypatch):
    monkeypatch.setattr(ir, "classify_intent", lambda *a, **k: "CASUAL_CHAT")
    try:
        ir.handle_intent_message("hello there", session_id="budget-clear-test")
    finally:
        assert llm.remaining_llm_budget() is None


def test_unmatched_message_skips_second_llm_call(monkeypatch):
    """When the LLM classification fallback produced nothing, the answer path
    must NOT call the LLM again — it goes straight to the honest fallback."""
    calls = {"llm": 0}

    def failing_classify(*a, **k):
        ir.classify_intent._last_fallback_attempted = True  # LLM fallback ran, no match
        return "EXPLANATION"

    monkeypatch.setattr(ir, "classify_intent", failing_classify)
    monkeypatch.setattr(llm, "call_openai_api", lambda *a, **k: calls.__setitem__("llm", calls["llm"] + 1) or "unused answer")
    res = ir.handle_intent_message("qqzz unmatchable message", session_id="no-double-call-test")
    assert res["intent"] == "EXPLANATION"
    assert calls["llm"] == 0  # no re-derivation call was made


def test_classify_intent_fallback_flag_resets_per_call():
    ir.classify_intent._last_fallback_attempted = True
    # Any rule-matched message resets the flag at the top of classify_intent.
    ir.classify_intent("hello", session_id="flag-reset-test")
    assert ir.classify_intent._last_fallback_attempted is False
