"""Regression tests for bugs found and fixed during the full QA pass.

Each test maps to a real defect reproduced against the running app:
  1. query_llm had no per-call wall-time cap when no request budget was active
     (REASONING hung past the 8s socket timeout because as_completed got None).
  2. lookup_known_answer returned canned definitions for messages that merely
     MENTIONED a term ("analyze this problem: our model misses fraud").
  3. "Why is it useful?" ignored last_topic and answered generically.
  4. "Compare the two." was hijacked into DEEP_RESEARCH by the "compare the"
     trigger instead of reasoning about the recent conversation topics.
  5. "What are the latest developments in AI models?" was hijacked into
     RESEARCH_START (dataset search) instead of WEB_SEARCH.
  6. "Which model performed best and why?" with an active project fell into
     EXPLANATION and returned an unrelated canned "model" definition.
  7. Frontend contract: the first chat message and workspace follow-ups must
     share one conversation id (memory split bug).
"""
import time

import pytest

import backend.intent_router as ir
import backend.llm as llm

REAL_QUERY_LLM = llm.query_llm  # conftest stubs llm.query_llm; keep the real one


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    for name in ("call_openai_api", "call_gemini_api", "call_anthropic_api", "call_mistral_api"):
        monkeypatch.setattr(llm, name, lambda *a, **k: None)
    yield


# --------------------------------------------------------------------------- #
# Bug 1: query_llm must never wait longer than its explicit timeout even when
# no request budget is active.
# --------------------------------------------------------------------------- #
def test_query_llm_explicit_timeout_caps_wait_without_budget(monkeypatch):
    def slow(*a, **k):
        time.sleep(30)
        return "too late"

    monkeypatch.setattr(llm, "call_mistral_api", slow)
    t0 = time.monotonic()
    res = REAL_QUERY_LLM("long prompt", "system", timeout=2)
    elapsed = time.monotonic() - t0
    assert res is None
    assert elapsed < 6, f"query_llm waited {elapsed:.2f}s despite timeout=2"


# --------------------------------------------------------------------------- #
# Bug 2: mention-only messages must not get canned knowledge answers.
# --------------------------------------------------------------------------- #
def test_mention_only_message_does_not_get_canned_definition():
    res = ir.lookup_known_answer(
        "Analyze this problem and break it into smaller steps: our model misses rare fraud cases"
    )
    assert res is None


@pytest.mark.parametrize("msg,expected_fragment", [
    ("What is Python?", "high-level, open-source programming language"),
    ("What about JavaScript?", "JavaScript is a high-level programming language"),
    ("What is overfitting?", "Overfitting occurs"),
    ("Tell me about recall", "Recall measures"),
    ("python?", "high-level, open-source programming language"),
])
def test_real_subject_questions_still_get_knowledge_answers(msg, expected_fragment):
    ans = ir.lookup_known_answer(msg)
    assert ans and expected_fragment in ans


# --------------------------------------------------------------------------- #
# Bug 3: pronoun follow-ups resolve against the conversation topic.
# --------------------------------------------------------------------------- #
def test_pronoun_followup_resolves_last_topic():
    assert ir._resolve_pronoun_topic("Why is it useful?", "python") == "python"
    assert ir._resolve_pronoun_topic("How does it handle missing data?", "xgboost") == "xgboost"


def test_explicit_subject_is_not_resolved_to_last_topic():
    # "What about JavaScript?" carries its own subject.
    assert ir._resolve_pronoun_topic("What about JavaScript?", "python") is None
    assert ir._resolve_pronoun_topic("What is recursion?", "python") is None


def test_full_conversation_memory_flow():
    sid = "qa-regression-memory"
    r1 = ir.handle_intent_message("What is Python?", session_id=sid)
    assert "Python" in r1["response"]
    r2 = ir.handle_intent_message("Why is it useful?", session_id=sid)
    # The follow-up must be about Python (resolved via last_topic), not a
    # generic "what does 'it' refer to" question.
    low = r2["response"].lower()
    assert "python" in low, f"follow-up lost the topic: {low[:120]}"


# --------------------------------------------------------------------------- #
# Bug 4: pronoun comparisons route to REASONING and reuse recent topics.
# --------------------------------------------------------------------------- #
def test_pronoun_comparison_routes_to_reasoning_not_deep_research():
    intent = ir.classify_intent("Compare the two.")
    assert intent == "REASONING"


def test_pronoun_comparison_uses_recent_topics(monkeypatch):
    sid = "qa-regression-cmp"
    ir.handle_intent_message("What is Python?", session_id=sid)
    ir.handle_intent_message("What about JavaScript?", session_id=sid)
    r = ir.handle_intent_message("Compare the two.", session_id=sid)
    low = r["response"].lower()
    assert "python" in low and "javascript" in low, f"comparison lost topics: {low[:160]}"


def test_explicit_topic_comparison_is_not_swapped_for_stale_topics():
    # A comparison naming real subjects must use THEM, not stale recent topics.
    sid = "qa-regression-cmp2"
    ir.handle_intent_message("What is quantum computing?", session_id=sid)
    r = ir.handle_intent_message("Compare REST APIs and GraphQL.", session_id=sid)
    assert r["intent"] == "REASONING"


# --------------------------------------------------------------------------- #
# Bug 5: current-information questions route to WEB_SEARCH, not the ML flow;
# explicit research verbs still win.
# --------------------------------------------------------------------------- #
def test_current_info_routes_to_web_search_not_research_start():
    assert ir.classify_intent("What are the latest developments in AI models?") == "WEB_SEARCH"


def test_research_verb_beats_currency_signal():
    assert ir.classify_intent("Research the latest developments in quantum computing.") == "DEEP_RESEARCH"


def test_web_search_query_strips_lead_in():
    from backend.intent_router import handle_intent_message
    sid = "qa-regression-web"
    r = handle_intent_message("What are the latest developments in AI models?", session_id=sid)
    assert r["intent"] == "WEB_SEARCH"
    assert "ai models" in (r.get("lastTopic") or "")


# --------------------------------------------------------------------------- #
# Bug 6: project-evaluation questions about the active study are follow-ups.
# --------------------------------------------------------------------------- #
def test_project_evaluation_question_routes_to_research_followup():
    intent = ir.classify_intent(
        "Which model performed best and why?", active_project_id="proj-x", session_id="qa-regression-proj"
    )
    assert intent == "RESEARCH_FOLLOWUP"


def test_general_question_with_active_project_stays_general():
    intent = ir.classify_intent(
        "What is overfitting?", active_project_id="proj-x", session_id="qa-regression-proj2"
    )
    assert intent == "EXPLANATION"


# --------------------------------------------------------------------------- #
# Bug 7: the frontend contract — App.jsx and the workspace must share one
# conversation id per project.
# --------------------------------------------------------------------------- #
def test_frontend_uses_shared_conversation_id():
    import re
    with open("src/App.jsx", encoding="utf-8") as f:
        app = f.read()
    with open("src/components/ResearchChatWorkspace.jsx", encoding="utf-8") as f:
        ws = f.read()
    # The start screen must send an explicit conversationId...
    assert re.search(r"sendChatMessage\(userText,\s*activeProject\?\.id,\s*convId", app)
    # ...and the workspace must prefer the app-level conversation.
    assert "propsConversationId || localConversationId" in ws
    # The old always-new-random-id bug must stay gone.
    assert "useState(() => 'conv-' + Math.random()" not in app
