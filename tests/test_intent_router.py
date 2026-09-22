"""Unit + conversation-regression tests for the intent router.

Covers MASTER QA sections 4 (intent routing), 5 (follow-up understanding),
6 (natural conversation), 7 (general knowledge), 16/2 (no invented answers),
and 33 (conversation regression tests A-K).

The LLM is disabled by conftest, so every assertion checks the deterministic
behaviour the bot must guarantee even with no provider reachable.
"""
import pytest

from backend.intent_router import (
    classify_intent,
    handle_intent_message,
    extract_topic,
    match_concept,
    _grounded_followup,
)


# ---------------------------------------------------------------------------
# Section 30: topic / concept detection
# ---------------------------------------------------------------------------
def test_match_concept_word_boundaries():
    # 'ai' must NOT match inside other words (the 'training' -> 'ai' trap).
    assert match_concept("what is training") == "training"
    assert match_concept("explain failure modes") is None
    assert match_concept("does email work") is None
    assert match_concept("what is ai") == "ai"


def test_match_concept_punctuated_keys():
    assert match_concept("What is C++?") == "c++"
    assert match_concept("What is PR-AUC?") == "pr-auc"
    assert match_concept("explain f1") == "f1"


def test_match_concept_longest_wins():
    # 'pr-auc' must beat 'auc'; 'machine learning' must beat 'ml'.
    assert match_concept("what is pr-auc") == "pr-auc"
    assert match_concept("what is machine learning") == "machine learning"


def test_extract_topic_known_and_unknown():
    assert extract_topic("What is recall?") == "recall"
    assert extract_topic("tell me about the confusion matrix") == "confusion matrix"
    # Unknown phrase still extracts the subject for the LLM/generic path.
    assert extract_topic("what is quantum entanglement") == "quantum entanglement"


# ---------------------------------------------------------------------------
# Section 4: intent routing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("msg,expected", [
    ("Hi", "CASUAL_CHAT"),
    ("hello", "CASUAL_CHAT"),
    ("what can you do", "CASUAL_CHAT"),
    ("What is AI?", "EXPLANATION"),
    ("What is Python?", "EXPLANATION"),
    ("What is recall?", "EXPLANATION"),
    ("Explain gradient boosting", "EXPLANATION"),
    ("Improve fraud detection", "RESEARCH_START"),
    ("predict customer churn", "RESEARCH_START"),
    ("show me the report", "REPORT_REQUEST"),
    ("show technical details", "TECHNICAL_DETAILS"),
])
def test_classify_basic_intents(msg, expected):
    assert classify_intent(msg, session_id="s-basic") == expected


def test_hf_url_is_research_start():
    url = "Improve fraud detection using https://huggingface.co/datasets/gusdelact/credit-card-fraud-curated"
    assert classify_intent(url, session_id="s-hf") == "RESEARCH_START"


# ---------------------------------------------------------------------------
# BUG A: explanations must work DURING active research
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("msg", ["What is recall?", "What is Python?", "What is PR-AUC?"])
def test_explanation_during_active_project(msg):
    assert classify_intent(msg, active_project_id="proj-x", session_id="s-a") == "EXPLANATION"


def test_project_specific_question_is_followup_not_explanation():
    msg = "why did the model perform poorly?"
    assert classify_intent(msg, active_project_id="proj-x", session_id="s-fu") == "RESEARCH_FOLLOWUP"


# ---------------------------------------------------------------------------
# BUG D: confirmation must not hijack a real question
# ---------------------------------------------------------------------------
def test_pure_confirmation_detected():
    for msg in ["yes", "yes do it", "go ahead", "sure", "ok", "proceed", "do it"]:
        assert classify_intent(msg, session_id="s-c") == "CONFIRM_PENDING_ACTION"


def test_confirmation_prefix_does_not_hijack_question():
    # 'ok what is python' previously launched research; it must EXPLAIN instead.
    assert classify_intent("ok what is python", session_id="s-d") == "EXPLANATION"
    assert classify_intent("yes but explain recall", session_id="s-d2") == "EXPLANATION"


# ---------------------------------------------------------------------------
# Section 33 TEST I / J: control verbs during active research
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("msg", ["Stop", "stop", "Continue", "Pause", "Resume"])
def test_control_verbs_during_active_project(msg):
    assert classify_intent(msg, active_project_id="proj-x", session_id="s-ctrl") == "RESEARCH_CONTROL"


def test_try_another_approach_is_control():
    assert classify_intent("try another approach", active_project_id="proj-x", session_id="s-h") == "RESEARCH_CONTROL"


# ---------------------------------------------------------------------------
# Section 5: pending-action resolution via handle_intent_message
# ---------------------------------------------------------------------------
def test_confirm_executes_pending_start_research(isolate_store):
    sid = "s-pending"
    isolate_store.set_pending_action(sid, "START_RESEARCH", topic="fraud detection", query="Improve fraud detection")
    res = handle_intent_message("yes do it", session_id=sid)
    assert res["intent"] == "CONFIRM_PENDING_ACTION"
    assert res["action"] == "START_RESEARCH"
    assert res["researchQuery"] == "Improve fraud detection"
    # Pending action consumed.
    assert isolate_store.get_session(sid)["pending_action"] is None


def test_confirm_executes_pending_next_experiment(isolate_store):
    sid = "s-pending2"
    isolate_store.set_pending_action(sid, "NEXT_EXPERIMENT", project_id="proj-1")
    res = handle_intent_message("go ahead", session_id=sid)
    assert res["action"] == "NEXT_EXPERIMENT"
    assert res["projectId"] == "proj-1"


def test_confirm_without_pending_asks_clarification(isolate_store):
    res = handle_intent_message("yes", session_id="s-nopending")
    assert res["action"] == "NONE"
    # Must NOT repeat the greeting and must NOT assume research (§11): it asks
    # what the user actually wants done.
    assert "what would you like me to do" in res["response"].lower()
    assert "autonomous research assistant" not in res["response"]


# ---------------------------------------------------------------------------
# Section 6: natural conversation (Hi -> Python -> Yes do it)
# ---------------------------------------------------------------------------
def test_natural_conversation_flow(isolate_store):
    sid = "s-flow"
    r1 = handle_intent_message("Hi", session_id=sid)
    assert r1["intent"] == "CASUAL_CHAT"

    r2 = handle_intent_message("What is Python?", session_id=sid)
    assert r2["intent"] == "EXPLANATION"
    assert "programming language" in r2["response"].lower()
    # A general answer must NOT silently create a research offer (§3/§12), and
    # must not mention datasets/training.
    assert isolate_store.get_session(sid)["pending_action"] is None
    assert "dataset" not in r2["response"].lower()

    # With nothing pending, a bare confirmation asks what to do (§11) instead of
    # launching research.
    r3 = handle_intent_message("Yes, do it.", session_id=sid)
    assert r3["intent"] == "CONFIRM_PENDING_ACTION"
    assert r3["action"] == "NONE"
    assert "what would you like me to do" in r3["response"].lower()


# ---------------------------------------------------------------------------
# Section 7: general knowledge answers are correct & on-topic (no stale answers)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("msg,must_contain,must_not", [
    ("What is AI?", "artificial intelligence", "recall measures"),
    ("What is Python?", "programming language", "artificial intelligence (ai) is technology"),
    ("What is recall?", "recall", "python is a high-level"),
    ("What is training?", "training", "artificial intelligence (ai) is technology"),
    ("What is PR-AUC?", "precision-recall", "area under the roc"),
    ("What is C++?", "c++", "sql"),
    ("What is SQL?", "sql", "c++ is"),
    ("What is a dataset?", "dataset", "recall measures"),
    ("What is a model?", "model", "python is a high-level"),
])
def test_general_knowledge_correct_and_not_stale(msg, must_contain, must_not):
    res = handle_intent_message(msg, session_id="gk-" + msg)
    text = res["response"].lower()
    assert must_contain in text
    assert must_not not in text


# ---------------------------------------------------------------------------
# Section 2 / 16: grounded follow-up never invents results
# ---------------------------------------------------------------------------
def test_grounded_followup_no_results_is_honest():
    ans = _grounded_followup("why did it fail?", "N/A", [], None)
    assert "don't have finished model results" in ans.lower()


def test_grounded_followup_uses_real_metrics_only():
    completed = [
        {"name": "XGBoost", "status": "COMPLETED", "metrics": {"pr_auc": 0.9051, "recall": 0.9251, "precision": 0.4791}},
        {"name": "Logistic Regression", "status": "COMPLETED", "metrics": {"pr_auc": 0.1596, "recall": 0.7723, "precision": 0.0357}},
    ]
    err = {"falseNegativesCount": 26, "falsePositivesCount": 349}
    ans = _grounded_followup("why did the model perform poorly?", "PR_AUC 0.9051", completed, err)
    # Quotes the REAL error counts, never a fabricated narrative.
    assert "26" in ans and "349" in ans
    assert "0.9051" in ans


def test_grounded_followup_single_baseline_no_false_comparison():
    completed = [{"name": "XGBoost", "status": "COMPLETED", "metrics": {"pr_auc": 0.9, "recall": 0.92, "precision": 0.5}}]
    ans = _grounded_followup("why is this the best?", "PR_AUC 0.9", completed, None)
    # With one model it must not claim a "second approach performed better".
    assert "second approach" not in ans.lower()
    assert "XGBoost" in ans


def test_research_followup_response_is_grounded_when_llm_down(isolate_store):
    sid = "s-grounded"
    pid = "proj-real"
    isolate_store.create_project(pid, "fraud study", "Improve fraud detection", "train.parquet", 60, None)
    isolate_store.save_baselines(pid, [
        {"name": "XGBoost", "status": "COMPLETED", "metrics": {"pr_auc": 0.9051, "recall": 0.9251, "precision": 0.4791}},
    ])
    isolate_store.save_error_analysis(pid, {"falseNegativesCount": 26, "falsePositivesCount": 349})
    res = handle_intent_message("why did the model miss fraud cases?", active_project_id=pid, session_id=sid)
    assert res["intent"] == "RESEARCH_FOLLOWUP"
    assert "0.934" not in res["response"]  # the old fake metric must be gone
    assert "26" in res["response"] or "0.9051" in res["response"]


# ---------------------------------------------------------------------------
# Section 34: edge cases — non-informative input must be deterministic casual
# chat, never routed to the LLM classifier (which once returned
# TECHNICAL_DETAILS for "🎉🚀").
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("msg", ["🎉🚀", "!!! ??? ***", "👍", "...", "—–—", "🙂"])
def test_non_informative_input_is_casual_chat(msg):
    assert classify_intent(msg, session_id="edge-" + msg) == "CASUAL_CHAT"


def test_non_informative_input_does_not_call_llm(monkeypatch):
    # The guard must short-circuit before the LLM fallback; prove no provider
    # call is attempted for emoji-only input.
    import backend.intent_router as ir

    def _boom(*a, **k):  # pragma: no cover - must never be called
        raise AssertionError("query_llm should not be called for non-informative input")

    monkeypatch.setattr(ir, "query_llm", _boom)
    assert classify_intent("🎉🚀", session_id="edge-nollm") == "CASUAL_CHAT"


# ---------------------------------------------------------------------------
# Owner directive §20/§21: general questions get general answers — never forced
# into the research workflow, never the "core concept in AI" template.
# The LLM is disabled (conftest), so these exercise the built-in knowledge base
# the production deployment (no API key) relies on.
# ---------------------------------------------------------------------------
FORBIDDEN_RESEARCH_PHRASES = [
    "core concept in artificial intelligence",
    "investigate a dataset",
    "train predictive models",
    "research study",
    "hypothesis",
    "i can launch an autonomous",
]


@pytest.mark.parametrize("msg,must_contain", [
    ("what is javascript and why it is used", "javascript"),
    ("What is JavaScript and why is it used?", "interactive"),
    ("What is Python?", "programming language"),
    ("Why is Python popular?", "python"),
    ("What is SQL?", "sql"),
    ("Explain recursion.", "base case"),
    ("What is machine learning?", "patterns"),
    ("What is gravity?", "mass"),
    ("Who invented the telephone?", "bell"),
    ("How does the internet work?", "packets"),
    ("Explain photosynthesis.", "glucose"),
])
def test_general_questions_get_general_answers(isolate_store, msg, must_contain):
    res = handle_intent_message(msg, session_id="gk2-" + msg)
    assert res["intent"] == "EXPLANATION"
    text = res["response"].lower()
    assert must_contain in text
    for bad in FORBIDDEN_RESEARCH_PHRASES:
        assert bad not in text
    # No fake research offer / pending action is created (§12).
    assert res["pendingAction"] is None
    assert isolate_store.get_session("gk2-" + msg)["pending_action"] is None


def test_most_important_javascript_no_research(isolate_store):
    # §21 — the exact reported failing case.
    res = handle_intent_message("what is javascript and why it is used", session_id="js-21")
    text = res["response"].lower()
    assert res["intent"] == "EXPLANATION"
    assert "javascript" in text and "interactive" in text
    for bad in ["dataset", "training", "fraud", "research study", "hypothesis",
                "core concept in artificial intelligence"]:
        assert bad not in text


# ---------------------------------------------------------------------------
# §20: task-type routing — coding / research / ML research
# ---------------------------------------------------------------------------
def test_coding_request_routes_to_coding(isolate_store):
    res = handle_intent_message("Write a Python program to reverse a string.", session_id="code-1")
    assert res["intent"] == "CODING"
    text = res["response"].lower()
    for bad in FORBIDDEN_RESEARCH_PHRASES:
        assert bad not in text


def test_explicit_research_routes_to_deep_research(isolate_store):
    assert classify_intent("research why JavaScript became popular and how its ecosystem evolved",
                           session_id="r-1") == "DEEP_RESEARCH"
    assert classify_intent("Research the latest developments in AI.", session_id="r-2") == "DEEP_RESEARCH"
    assert classify_intent("Compare these research papers.", session_id="r-3") == "DEEP_RESEARCH"


def test_deep_research_is_honest_not_fabricated(isolate_store):
    res = handle_intent_message("research the latest developments in quantum computing", session_id="r-4")
    assert res["intent"] == "DEEP_RESEARCH"
    text = res["response"].lower()
    # Must NOT pretend to have browsed or produced sources.
    assert "isn't wired" in text or "not wired" in text or "won't pretend" in text


def test_ml_research_request_routes_to_research_start(isolate_store):
    assert classify_intent("Improve this ML model using my dataset.", session_id="ml-1") == "RESEARCH_START"
    assert classify_intent("Improve fraud detection", session_id="ml-2") == "RESEARCH_START"


# ---------------------------------------------------------------------------
# §23: natural multi-turn — definition then "show me a simple example"
# ---------------------------------------------------------------------------
def test_followup_example_uses_topic_context(isolate_store):
    sid = "flow-23"
    r1 = handle_intent_message("what is JavaScript?", session_id=sid)
    assert r1["intent"] == "EXPLANATION"
    assert "javascript" in r1["response"].lower()

    r2 = handle_intent_message("show me a simple example", session_id=sid)
    # Resolves against the current topic (JavaScript) as a coding request.
    assert r2["intent"] == "CODING"
    assert r2["lastTopic"] == "javascript"
    for bad in FORBIDDEN_RESEARCH_PHRASES:
        assert bad not in r2["response"].lower()


# ---------------------------------------------------------------------------
# §13: current user intent has priority over an active research project
# ---------------------------------------------------------------------------
def test_general_question_during_active_research_stays_general(isolate_store):
    res = handle_intent_message("What is recursion?", active_project_id="proj-fraud", session_id="ctx-13")
    assert res["intent"] == "EXPLANATION"
    assert "base case" in res["response"].lower()


def test_bare_why_is_not_hijacked_by_stale_topic(isolate_store):
    # A stale last_topic must not turn an unrelated general question into a
    # research follow-up (§13).
    sid = "ctx-stale"
    isolate_store.update_session(sid, {"last_topic": "fraud detection"})
    assert classify_intent("why is the sky blue", session_id=sid) == "EXPLANATION"

