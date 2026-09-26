"""Tests for the current-information capability (repair directive §2–§17).

All network layers are stubbed: Wikipedia page/search fetchers are patched and
web-search backup is exercised through an explicit `search_fn`, so no test
touches the network. Fixtures prove the GENERIC behaviour (fictional leagues,
teams and companies — no hard-coded entity knowledge anywhere).
"""
import pytest

import backend.current_info as ci
from backend.current_info import (
    extract_current_fact_request,
    answer_current_fact,
    format_current_fact,
)


@pytest.fixture(autouse=True)
def _reset_ci_cache():
    """Tests stub the network layer; a pre-populated TTL cache would leak one
    test's fake pages into another."""
    ci._CACHE.clear()
    yield
    ci._CACHE.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _page(title: str, extract: str, modified: str = "2026-09-19") -> dict:
    return {
        "title": title,
        "extract": extract,
        "url": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_"),
        "modified": modified,
    }


@pytest.fixture
def wiki(monkeypatch):
    """Replace the Wikipedia fetch layer with a programmable fake.

    Usage: wiki({"Page Title": "extract text", ...}) — search returns exactly
    those titles in order; page fetch returns the matching extract.
    """
    def _install(pages: dict):
        titles = list(pages.keys())
        monkeypatch.setattr(ci, "_ranked_search_titles", lambda terms, year: list(titles))
        monkeypatch.setattr(
            ci, "_fetch_page",
            lambda title: _page(title, pages[title]) if title in pages else None)
        monkeypatch.setattr(ci, "_http_json",
                            lambda url: (_ for _ in ()).throw(AssertionError("network")))
    return _install


def _no_search(*a, **k):
    """Simulates an unconfigured search environment: providers exist but return
    nothing. The pipeline must then answer honestly-unavailable (never paste
    background) — exactly what these tests assert."""
    return []


# ---------------------------------------------------------------------------
# 1. Time-sensitivity detection + parsing (generic patterns)
# ---------------------------------------------------------------------------

def test_detects_champion_question_with_year():
    req = extract_current_fact_request("Who won 2026 IPL?")
    assert req is not None
    assert req.aspect == "champion"
    assert req.year == 2026
    assert "IPL" in req.entity


def test_detects_champion_question_year_after_entity():
    req = extract_current_fact_request("Who won IPL 2026?")
    assert req is not None
    assert req.aspect == "champion"
    assert req.year == 2026


def test_detects_runner_up_question():
    req = extract_current_fact_request("Who was runner-up in IPL 2026?")
    assert req is not None
    assert req.aspect == "runner_up"
    assert req.year == 2026


def test_detects_future_year_question():
    req = extract_current_fact_request("Who won IPL 2027?")
    assert req is not None
    assert req.year == 2027


def test_detects_price_question():
    req = extract_current_fact_request("What is the current Bitcoin price?")
    assert req is not None
    assert req.aspect == "price"
    assert "Bitcoin" in req.entity


def test_detects_latest_product_question_with_punctuation():
    req = extract_current_fact_request("What is the latest NVIDIA GPU?")
    assert req is not None
    assert req.aspect == "latest"
    assert "NVIDIA" in req.entity


def test_detects_holder_question():
    req = extract_current_fact_request("Who is the current CEO of Microsoft?")
    assert req is not None
    assert req.aspect == "holder"
    assert req.entity == "Microsoft"


def test_detects_recurring_event_without_year():
    req = extract_current_fact_request("Who won the latest Cricket World Cup?")
    assert req is not None
    assert req.aspect == "champion"
    assert req.year is None


def test_weather_question_is_cleaned():
    req = extract_current_fact_request("What is today's weather in Hyderabad?")
    assert req is not None
    assert "'" not in req.entity
    assert "Hyderabad" in req.entity


def test_news_listing_defers_to_web_search():
    assert extract_current_fact_request("What is the latest IPL news?") is None
    assert extract_current_fact_request("What happened in AI this week?") is None


def test_general_knowledge_does_not_match():
    assert extract_current_fact_request("What is cricket?") is None
    assert extract_current_fact_request("Research IPL history.") is None


# ---------------------------------------------------------------------------
# 2. Verified answering pipeline (stubbed sources)
# ---------------------------------------------------------------------------

def test_champion_answered_directly_with_source(wiki):
    wiki({"Nova League 2026": (
        "The 2026 Nova League season was the fourth edition of the tournament. "
        "Delta Lions defeated Alpha Kings by 20 runs in the final to secure "
        "their first title."
    )})
    req = extract_current_fact_request("Who won 2026 Nova League?")
    res = answer_current_fact(req, search_fn=_no_search)
    assert res["status"] == "ok"
    assert res["verified"] is True
    assert "Delta Lions" in res["answer"]
    assert res["sources"] and "Nova League 2026" in res["sources"][0]["title"]
    text = format_current_fact(res)
    assert text.startswith(res["answer"])          # direct answer FIRST (§9)
    assert "Source:" in text and "wikipedia.org" in text


def test_runner_up_derived_from_final_result(wiki):
    wiki({"Nova League 2026": (
        "In the final, Delta Lions defeated Alpha Kings by 5 wickets to win "
        "the 2026 title."
    )})
    req = extract_current_fact_request("Who was runner-up in Nova League 2026?")
    res = answer_current_fact(req, search_fn=_no_search)
    assert res["status"] == "ok"
    assert "Alpha Kings" in res["answer"]
    assert "runners-up" in res["answer"]
    assert "Delta Lions" in res["answer"]


def test_pronoun_resolved_to_named_entity(wiki):
    wiki({"2026 Kestrels League": (
        "Kestrels United were the defending champions, having won the 2025 "
        "edition. They defended their title by defeating Merlins FC by 96 runs "
        "in the final."
    )})
    req = extract_current_fact_request("Who won the latest Kestrels League?")
    req.entity = "Kestrels League"                 # normalise parsed entity
    res = answer_current_fact(req, search_fn=_no_search)
    assert res["status"] == "ok"
    assert "Kestrels United" in res["answer"]      # not "They ..."
    assert "Merlins" in res["answer"]


def test_wrong_year_edition_never_answers(wiki):
    wiki({"Nova League 2025": (
        "The 2025 Nova League was won by Delta Lions, who defeated Alpha Kings "
        "in the final."
    )})
    req = extract_current_fact_request("Who won Nova League 2026?")
    res = answer_current_fact(req, search_fn=_no_search)
    assert res["status"] == "unavailable"
    assert res["verified"] is False


def test_page_without_the_fact_is_skipped_not_pasted(wiki):
    wiki({"Nova League 2026": (
        "The 2026 Nova League was the fourth edition of the tournament, "
        "featuring eight teams across two venues."
    )})
    req = extract_current_fact_request("Who won Nova League 2026?")
    res = answer_current_fact(req, search_fn=_no_search)
    assert res["status"] == "unavailable"
    assert "can't reliably verify" in res["answer"]
    assert res["sources"] == []


def test_future_event_is_never_answered(wiki):
    # Any network access would be a bug: the future guard must short-circuit.
    monkey_calls = []
    wiki({})
    req = extract_current_fact_request("Who won Nova League 2027?")
    res = answer_current_fact(req, search_fn=lambda *a, **k: monkey_calls.append(1) or [])
    assert res["status"] == "unavailable"
    assert res["verified"] is False
    assert "2027" in res["answer"]
    assert monkey_calls == []                      # no search even attempted


def test_holder_answered_from_role_sentence(wiki):
    wiki({"Zephyr Systems": (
        "Zephyr Systems is a software company founded in 1998. Dana Whitfield "
        "became CEO in 2019 after leading the platform group. In 2010 a "
        "spokesperson said the company planned to expand."
    )})
    req = extract_current_fact_request("Who is the current CEO of Zephyr Systems?")
    res = answer_current_fact(req, search_fn=_no_search)
    assert res["status"] == "ok"
    assert "Dana Whitfield" in res["answer"]


def test_holder_not_answered_from_anecdote(wiki):
    wiki({"Zephyr Systems": (
        "Zephyr Systems is a software company. In 2010 a spokesperson said the "
        "company planned to expand, and analysts stated the CEO role would be "
        "reviewed."
    )})
    req = extract_current_fact_request("Who is the current CEO of Zephyr Systems?")
    res = answer_current_fact(req, search_fn=_no_search)
    assert res["status"] == "unavailable"


def test_price_never_answered_from_static_article(wiki):
    wiki({"Bitcoin": (
        "As the market valuation of the total stock of bitcoins approached "
        "US$1 billion, some commentators called bitcoin prices a bubble."
    )})
    req = extract_current_fact_request("What is the current Bitcoin price?")
    res = answer_current_fact(req, search_fn=_no_search)
    assert res["status"] == "unavailable"
    assert "US$1 billion" not in res["answer"]
    assert "live market data" in res["answer"]


def test_price_answered_from_fresh_search_result(wiki):
    wiki({})
    req = extract_current_fact_request("What is the current Bitcoin price?")
    res = answer_current_fact(req, search_fn=lambda q, limit=5: [
        {"title": "Markets Today", "url": "https://markets.example/btc",
         "snippet": "Bitcoin trades at $114,250 today after a 2% gain."}])
    assert res["status"] == "ok"
    assert res["verified"] is False                # snippet-level confidence
    assert "114,250" in res["answer"]


def test_champion_backed_by_search_snippet_when_no_page(wiki):
    wiki({})
    req = extract_current_fact_request("Who won Nova League 2026?")
    res = answer_current_fact(req, search_fn=lambda q, limit=5: [
        {"title": "Sports Desk", "url": "https://news.example/nova",
         "snippet": "Delta Lions won the 2026 Nova League final, defeating "
                    "Alpha Kings by 20 runs."}])
    assert res["status"] == "ok"
    assert res["verified"] is False                # snippets are not verified
    assert "Delta Lions" in res["answer"]


def test_format_unavailable_has_no_fake_source():
    res = {"status": "unavailable", "question": "q", "answer": "nope",
           "sources": [], "verified": False, "reason": "x"}
    assert format_current_fact(res) == "nope"
    assert "Source:" not in format_current_fact(res)


def test_search_titles_drop_wrong_year_and_future_editions(monkeypatch):
    def fake_json(url):
        return {"query": {"search": [
            {"title": "2025 Kestrels League"},   # wrong edition -> dropped
            {"title": "2027 Kestrels League"},   # future edition -> dropped
            {"title": "Kestrels League"},        # generic page -> kept
        ]}}

    monkeypatch.setattr(ci, "_http_json", fake_json)
    titles = ci._ranked_search_titles("Kestrels League 2026", 2026)
    assert titles == ["Kestrels League"]


# ---------------------------------------------------------------------------
# 3. Intent routing (§17 regression trio)
# ---------------------------------------------------------------------------

def test_routing_current_information():
    from backend.intent_router import classify_intent
    assert classify_intent("Who won 2026 IPL?") == "CURRENT_INFORMATION"
    assert classify_intent("Who won IPL 2027?") == "CURRENT_INFORMATION"
    assert classify_intent("Who is the current CEO of Microsoft?") == "CURRENT_INFORMATION"
    assert classify_intent("What is the latest NVIDIA GPU?") == "CURRENT_INFORMATION"
    assert classify_intent("What is the current Bitcoin price?") == "CURRENT_INFORMATION"


def test_routing_regression_trio():
    from backend.intent_router import classify_intent
    # Three DIFFERENT tasks — the current-info fix must not capture the others.
    assert classify_intent("What is cricket?") == "EXPLANATION"
    assert classify_intent("Research IPL history.") == "DEEP_RESEARCH"
    assert classify_intent("Who won 2026 IPL?") == "CURRENT_INFORMATION"


def test_routing_news_stays_web_search():
    from backend.intent_router import classify_intent
    assert classify_intent("What is the latest IPL news?") == "WEB_SEARCH"
    assert classify_intent("What happened in AI this week?") == "WEB_SEARCH"
