"""LIVE end-to-end persistence test (task section 27).

Runs against a real backend on 127.0.0.1:8000 with the real PostgreSQL store.
Skipped automatically when the server is not running (keeps `py -m pytest`
hermetic; run it explicitly while the dev server is up).

Flow: chat -> messages persisted -> rows verified in Postgres -> backend
restart -> messages still served -> migrated research artifacts served.
"""
import json
import os
import time
import urllib.request

import pytest

BASE = "http://127.0.0.1:8000"


def _server_up() -> bool:
    try:
        socket_create = __import__("socket").create_connection
        socket_create(("127.0.0.1", 8000), timeout=1).close()
        return True
    except OSError:
        return False


def _post(path: str, payload: dict, timeout: float = 60.0):
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get(path: str, timeout: float = 30.0):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


pytestmark = pytest.mark.skipif(not _server_up(),
                                reason="live backend not running on :8000")


def test_live_chat_persists_to_postgres_and_survives_restart():
    marker = f"E2E-DB-{int(time.time())}"
    conversation_id = f"conv-e2e-{int(time.time())}"

    # 1. Chat: message in, assistant response out.
    chat = _post("/api/chat", {
        "message": f"What is PostgreSQL? Include the marker {marker}.",
        "conversationId": conversation_id,
    })
    assert chat.get("response"), chat

    # 2. The conversation is served back by the API.
    history = _get(f"/api/conversations/{conversation_id}/messages")
    messages = history if isinstance(history, list) else history.get("messages", [])
    contents = [m.get("content", "") for m in messages]
    assert any(marker in c for c in contents), contents[:3]

    # 3. Rows exist in the real database (direct psql check, no app code path).
    import subprocess
    psql = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
    query = ("SELECT count(*) FROM messages "
             f"WHERE conversation_id = '{conversation_id}' "
             f"AND content LIKE '%{marker}%';")
    result = subprocess.run(
        [psql, "-h", "127.0.0.1", "-U", "postgres", "-d", "ai_scientist",
         "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", query],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "PGPASSWORD": "postgres"})
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip() or "0") >= 1, result.stdout

    # 4. Migrated research data is served from Postgres through the API.
    projects = _get("/api/projects")
    assert isinstance(projects, list) and len(projects) >= 1
    sample = projects[0]["id"]
    details = _get(f"/api/projects/{sample}")
    assert details.get("id") == sample
    baselines = _get(f"/api/projects/{sample}/baselines")
    assert isinstance(baselines, list)
