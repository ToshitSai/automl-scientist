"""Live integration tests (section 31). These hit a RUNNING backend.

Run the server first:
    py -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
then:
    py -m pytest tests/test_live_integration.py -q

If the backend is not reachable the whole module is skipped (not failed), so the
hermetic unit suite stays green in CI without a live server.
"""
import json
import os
import urllib.request
import urllib.error

import pytest

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")


def _server_up():
    try:
        with urllib.request.urlopen(BASE + "/api/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _server_up(), reason="backend not running on " + BASE)


def _post(path, payload, timeout=300):
    # Live tests hit real external services (HF Hub search can try several query
    # variants at up to 40s each, plus a best-effort preview download), so the
    # ceiling is generous. Conversational calls still return in ~0.1s; this only
    # prevents false failures on slow networks for the network-bound paths.
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _chat(msg, conv, proj=None, timeout=300):
    return _post("/api/chat", {"message": msg, "conversationId": conv, "projectId": proj}, timeout=timeout)


# ---------------------------------------------------------------------------
# Chat -> Intent -> Response (section 23/31)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("msg,conv,intent", [
    ("Hi", "it-1", "CASUAL_CHAT"),
    ("What is AI?", "it-2", "EXPLANATION"),
    ("What is Python?", "it-3", "EXPLANATION"),
    ("What is recall?", "it-4", "EXPLANATION"),
    ("Improve fraud detection", "it-5", "RESEARCH_START"),
])
def test_chat_intent_pipeline(msg, conv, intent):
    res = _chat(msg, conv)
    assert res["intent"] == intent
    assert isinstance(res.get("response"), str) and res["response"].strip()


def test_message_survives_pipeline_unchanged():
    # Section 23: the exact user text must drive the answer (no demo/stale text).
    res = _chat("What is SQL?", "it-sql")
    assert "sql" in res["response"].lower()


def test_no_stale_answer_across_messages():
    # Two different questions in one conversation must get different answers.
    a = _chat("What is precision?", "it-stale")["response"].lower()
    b = _chat("What is recall?", "it-stale")["response"].lower()
    assert "precision" in a and "recall" in b
    assert a != b


# ---------------------------------------------------------------------------
# Dataset URL -> inspect (real Hugging Face metadata, sections 11/12)
# ---------------------------------------------------------------------------
def test_inspect_real_hf_dataset():
    res = _post("/api/datasets/inspect",
                {"url": "https://huggingface.co/datasets/gusdelact/credit-card-fraud-curated"})
    info = res.get("info") or res
    assert info.get("repoId") == "gusdelact/credit-card-fraud-curated"
    assert info.get("targetColumn") == "is_fraud"
    assert (info.get("featureCount") or 0) > 0
    assert info.get("license")  # real declared license


def test_inspect_rejects_non_hf_and_general_urls():
    # Section 34 edge case: a non-HF URL or the bare /datasets discovery page is
    # a client error (400), NOT an upstream 502 from trying to fetch it.
    for bad in ["https://example.com/foo", "https://huggingface.co/datasets", "just some text"]:
        req = urllib.request.Request(
            BASE + "/api/datasets/inspect", data=json.dumps({"url": bad}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=30)
            code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        assert code == 400, f"expected 400 for {bad!r}, got {code}"


def test_search_returns_real_candidates():
    with urllib.request.urlopen(BASE + "/api/datasets/search?q=fraud%20detection&limit=5", timeout=150) as r:
        data = json.loads(r.read().decode("utf-8"))
    cands = data.get("candidates") or data.get("results") or data
    assert isinstance(cands, list)


# ---------------------------------------------------------------------------
# Conversation regression A-K against the live server (section 33)
# ---------------------------------------------------------------------------
def _any_project():
    with urllib.request.urlopen(BASE + "/api/projects", timeout=10) as r:
        projects = json.loads(r.read().decode("utf-8"))
    completed = [p for p in projects if p.get("status") == "COMPLETED"]
    return (completed or projects or [{}])[0].get("id")


def test_regression_matrix_live():
    pid = _any_project()
    assert _chat("Hi", "rg-a")["intent"] == "CASUAL_CHAT"
    assert _chat("What is AI?", "rg-b")["intent"] == "EXPLANATION"
    assert _chat("What is Python?", "rg-c")["intent"] == "EXPLANATION"
    assert _chat("What is recall?", "rg-d")["intent"] == "EXPLANATION"
    assert _chat("Improve fraud detection", "rg-e")["intent"] == "RESEARCH_START"
    if pid:
        assert _chat("Why did the model perform poorly?", "rg-f", pid)["intent"] == "RESEARCH_FOLLOWUP"
        assert _chat("Try another approach", "rg-h", pid)["action"] == "NEXT_EXPERIMENT"
        assert _chat("Stop", "rg-i", pid)["action"] == "STOP_RESEARCH"
        assert _chat("Continue", "rg-j", pid)["action"] == "RESUME_RESEARCH"
        assert _chat("Show me the report", "rg-k", pid)["action"] == "SHOW_REPORT"


def test_conversation_history_endpoint():
    conv = "it-hist"
    _chat("What is a dataset?", conv)
    with urllib.request.urlopen(BASE + f"/api/conversations/{conv}/messages", timeout=10) as r:
        msgs = json.loads(r.read().decode("utf-8"))
    roles = [m["role"] for m in msgs]
    assert "user" in roles and "assistant" in roles
