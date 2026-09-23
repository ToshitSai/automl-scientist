"""Tests for the general-assistant tool modes: calculator, web search,
summarizer, deep research pipeline, and the router's new intents."""
import pytest

import backend.calculator as calc
import backend.summarizer as summ
import backend.web_search as ws
import backend.deep_research as dr
from backend.intent_router import classify_intent, handle_intent_message

# ---------------------------------------------------------------------------
# Calculator tool: computes correctly, refuses to guess
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("msg,expected", [
    ("what is 2+2", "4"),
    ("15% of 240", "36"),
    ("2^10", "1024"),
    ("sqrt(144)", "12"),
    ("15 percent of 240", "36"),
    ("2 plus 3", "5"),
    ("12 divided by 4", "3"),
    ("(3+5)*2", "16"),
    ("what is 100/8", "12.5"),
])
def test_calculator_evaluates(msg, expected):
    res = calc.try_evaluate(msg)
    assert res is not None, msg
    assert res["formatted"] == expected


@pytest.mark.parametrize("msg", [
    "what is JavaScript",           # knowledge question
    "what is 3x+5=20",              # equation, not arithmetic
    "If a train travels 60 mph for 2 hours what is the distance",  # word problem
    "what is pi",                   # bare constant, not a calculation request
    "explain the theory of relativity",
    "hello",
])
def test_calculator_refuses_non_arithmetic(msg):
    assert calc.try_evaluate(msg) is None, msg


def test_calculator_guards_dangerous_expressions():
    assert calc.try_evaluate("9**9**9**9") is None  # must not hang/overflow


def test_calculator_rejects_code_injection():
    assert calc.try_evaluate('__import__("os").system("dir")') is None
    assert calc.try_evaluate("(lambda: 1)()") is None


# ---------------------------------------------------------------------------
# Router: new intents
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("msg,expected", [
    ("what is 15% of 240", "MATHEMATICS"),
    ("calculate 2^10", "MATHEMATICS"),
    ("2 plus 3", "MATHEMATICS"),
    ("compare JavaScript and Python for backend development", "REASONING"),
    ("what are the pros and cons of microservices", "REASONING"),
    ("summarize the following text", "WRITING"),
    ("translate this to French", "WRITING"),
])
def test_new_intent_routing(msg, expected):
    assert classify_intent(msg, session_id="ga-" + msg) == expected


def test_explicit_web_search_routing():
    assert classify_intent("search the web for rust vs go", session_id="ws-1") == "WEB_SEARCH"


def test_currency_signal_routes_to_web_search():
    assert classify_intent("find the latest JavaScript features", session_id="ws-2") == "WEB_SEARCH"


def test_definitional_question_not_hijacked_by_currency_word():
    # A definitional question containing a currency word still asks for current
    # information -> WEB_SEARCH (the currency signal wins over the question shape).
    assert classify_intent("what is the latest news about nothing specific", session_id="ws-3") == "WEB_SEARCH"


def test_stable_definition_not_hijacked_by_currency_word():
    # A purely definitional question with no real currency need stays general.
    assert classify_intent("what is machine learning", session_id="ws-3b") == "EXPLANATION"


def test_document_still_beats_writing():
    assert classify_intent("summarize this pdf", session_id="wr-1") == "DOCUMENT_ANALYSIS"


def test_coding_still_beats_math():
    assert classify_intent("write a python program to add 2 and 3", session_id="cm-1") == "CODING"


def test_compare_papers_stays_deep_research():
    assert classify_intent("compare these research papers", session_id="cm-2") == "DEEP_RESEARCH"


# ---------------------------------------------------------------------------
# Handlers: MATHEMATICS computes, WRITING summarizes offline
# ---------------------------------------------------------------------------
def test_math_handler_returns_computed_result(isolate_store):
    res = handle_intent_message("what is 12*12", session_id="m-1")
    assert res["intent"] == "MATHEMATICS"
    assert "144" in res["response"]


def test_math_handler_word_problem_does_not_fabricate(isolate_store):
    # A word problem is NOT plain arithmetic: it must never be answered with a
    # guessed number. With the LLM disabled it gets the honest fallback (either
    # via the MATHEMATICS handler's general-answer fallback or EXPLANATION).
    res = handle_intent_message("If a train travels 60 mph for 2 hours what is the distance?", session_id="m-2")
    assert res["intent"] in ("MATHEMATICS", "EXPLANATION")
    assert res["response"].strip()
    assert "120" not in res["response"], "must not compute/invent a numeric answer"
    assert "don't want to guess" in res["response"].lower()


def test_writing_handler_summarizes_offline(isolate_store):
    text = ("Machine learning is a branch of artificial intelligence. " * 30
            + "Neural networks learn hierarchical representations. " * 30)
    res = handle_intent_message(f"summarize: {text}", session_id="w-1")
    assert res["intent"] == "WRITING"
    assert len(res["response"]) < len(text)
    assert "extractive" in res["response"].lower()


def test_writing_handler_honest_without_llm(isolate_store):
    res = handle_intent_message("translate this to French: hello world", session_id="w-2")
    assert "couldn" in res["response"].lower() or "provider" in res["response"].lower()


# ---------------------------------------------------------------------------
# Summarizer
# ---------------------------------------------------------------------------
def test_summarizer_shortens_and_preserves_order():
    sentences = [f"Sentence number {i} discusses topic {i % 3} in depth." for i in range(12)]
    text = " ".join(sentences)
    out = summ.summarize_text(text, max_sentences=3)
    assert out.count("Sentence number") == 3
    idxs = [int(out.split("number ")[1].split(" discusses")[0]),
            int(out.split("number ")[2].split(" discusses")[0]),
            int(out.split("number ")[3].split(" discusses")[0])]
    assert idxs == sorted(idxs), "summary sentences must stay in original order"


def test_summarizer_passthrough_short_text():
    assert summ.summarize_text("Short already.") == "Short already."


# ---------------------------------------------------------------------------
# Web search tool (stubbed providers; no network in unit tests)
# ---------------------------------------------------------------------------
def test_search_web_uses_first_provider_with_results(monkeypatch):
    monkeypatch.setattr(ws, "_search_tavily", lambda q, limit: [])
    monkeypatch.setattr(ws, "_search_serper", lambda q, limit: [
        {"title": "Rust", "url": "https://rust-lang.org", "snippet": "A language", "source": "Google (Serper)"}])
    monkeypatch.setattr(ws, "_search_brave", lambda q, limit: [
        {"title": "SHOULD NOT APPEAR", "url": "https://x", "snippet": "", "source": "Brave"}])
    monkeypatch.setattr(ws, "_search_duckduckgo", lambda q, limit: [])

    res = ws.search_web("rust programming", limit=3)
    assert len(res) == 1 and res[0]["title"] == "Rust"


def test_search_web_empty_when_all_providers_fail(monkeypatch):
    for p in ("_search_tavily", "_search_serper", "_search_brave", "_search_duckduckgo"):
        monkeypatch.setattr(ws, p, lambda q, limit: [])
    assert ws.search_web("anything") == []


def test_web_search_handler_honest_when_no_results(isolate_store):
    res = handle_intent_message("search the web for obscurity", session_id="ws-4")
    assert "couldn't reach any" in res["response"].lower() or "won't invent" in res["response"].lower()


# ---------------------------------------------------------------------------
# Deep research pipeline (all tools stubbed)
# ---------------------------------------------------------------------------
def test_deep_research_full_pipeline(monkeypatch):
    monkeypatch.setattr(dr, "query_llm", lambda *a, **k: None)  # deterministic planning
    monkeypatch.setattr(dr, "search_web", lambda q, limit=3: [
        {"title": f"Result for {q}", "url": f"https://example.com/{q.replace(' ', '-')}",
         "snippet": f"Evidence about {q}", "source": "DuckDuckGo"}])
    monkeypatch.setattr(dr, "search_literature", lambda q, limit=2: [])

    res = dr.run_deep_research("how did JavaScript evolve")
    assert res["status"] == "ok"
    assert res["sourceCount"] >= 2
    report = res["report"]
    assert report.startswith("# Deep Research Report")
    assert "## Research Plan" in report and "## Findings" in report
    assert "## Verification" in report and "## Sources" in report
    assert "https://example.com/" in report


def test_deep_research_reports_no_sources_honestly(monkeypatch):
    monkeypatch.setattr(dr, "query_llm", lambda *a, **k: None)
    monkeypatch.setattr(dr, "search_web", lambda *a, **k: [])
    monkeypatch.setattr(dr, "search_literature", lambda *a, **k: [])

    res = dr.run_deep_research("obscure topic")
    assert res["status"] == "no_sources" and res["sourceCount"] == 0


def test_deep_research_deduplicates_sources(monkeypatch):
    monkeypatch.setattr(dr, "query_llm", lambda *a, **k: None)
    monkeypatch.setattr(dr, "search_web", lambda q, limit=3: [
        {"title": "Same page", "url": "https://example.com/same", "snippet": f"{q}", "source": "DDG"}])
    monkeypatch.setattr(dr, "search_literature", lambda q, limit=2: [])

    res = dr.run_deep_research("topic with duplicated results")
    assert res["sourceCount"] == 1


def test_deep_research_drops_fabricated_filler_abstracts(monkeypatch):
    monkeypatch.setattr(dr, "query_llm", lambda *a, **k: None)
    monkeypatch.setattr(dr, "search_web", lambda q, limit=3: [])
    monkeypatch.setattr(dr, "search_literature", lambda q, limit=2: [
        {"title": "A paper", "url": "https://s2.org/p1", "abstract": "Research paper on " + q[:40] + "...", "source": "Semantic Scholar"}])

    res = dr.run_deep_research("niche academic topic")
    assert res["sourceCount"] == 0  # filler abstract must not masquerade as evidence


def test_deep_research_handler_reports_failure_honestly(isolate_store, monkeypatch):
    monkeypatch.setattr(dr, "query_llm", lambda *a, **k: None)
    monkeypatch.setattr(dr, "search_web", lambda *a, **k: [])
    monkeypatch.setattr(dr, "search_literature", lambda *a, **k: [])
    res = handle_intent_message("research the latest developments in quantum computing", session_id="dr-h")
    assert res["intent"] == "DEEP_RESEARCH"
    assert "couldn't reach any" in res["response"].lower()


def test_deep_research_handler_returns_report(isolate_store, monkeypatch):
    monkeypatch.setattr(dr, "query_llm", lambda *a, **k: None)
    monkeypatch.setattr(dr, "search_web", lambda q, limit=3: [
        {"title": f"About {q}", "url": f"https://e.com/{abs(hash(q))}", "snippet": f"Evidence: {q}", "source": "DDG"}])
    monkeypatch.setattr(dr, "search_literature", lambda q, limit=2: [])
    res = handle_intent_message("research how JavaScript evolved", session_id="dr-r")
    assert res["intent"] == "DEEP_RESEARCH"
    assert "Deep Research Report" in res["response"]
    assert res["research"]["sourceCount"] >= 1


def test_plan_subqueries_fallback_without_llm():
    subs = dr.plan_subqueries("quantum computing advances")
    assert 1 <= len(subs) <= 3
    assert subs[0] == "quantum computing advances"
