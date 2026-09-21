"""Unit tests for conversation-state storage (section 3) and pending actions."""
from database.store import store


def test_record_message_appends_separately(isolate_store):
    sid = "conv-1"
    isolate_store.record_message(sid, "user", "What is recall?")
    isolate_store.record_message(sid, "assistant", "Recall measures ...", intent="EXPLANATION", topic="recall")
    isolate_store.record_message(sid, "user", "Hi")

    msgs = isolate_store.get_messages(sid)
    assert len(msgs) == 3
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    # Each message carries its own identity + metadata.
    first = msgs[0]
    for key in ("id", "conversation_id", "role", "content", "timestamp"):
        assert key in first
    assert msgs[1]["intent"] == "EXPLANATION"
    assert msgs[1]["topic"] == "recall"
    # ids are unique
    assert len({m["id"] for m in msgs}) == 3


def test_history_is_capped(isolate_store):
    sid = "conv-cap"
    for i in range(250):
        isolate_store.record_message(sid, "user", f"m{i}", max_history=200)
    msgs = isolate_store.get_messages(sid)
    assert len(msgs) == 200
    # Oldest trimmed, newest retained.
    assert msgs[-1]["content"] == "m249"
    assert msgs[0]["content"] == "m50"


def test_pending_action_roundtrip(isolate_store):
    sid = "conv-pend"
    assert isolate_store.get_session(sid)["pending_action"] is None
    isolate_store.set_pending_action(sid, "NEXT_EXPERIMENT", project_id="p1")
    pend = isolate_store.get_session(sid)["pending_action"]
    assert pend["type"] == "NEXT_EXPERIMENT" and pend["projectId"] == "p1"
    isolate_store.clear_pending_action(sid)
    assert isolate_store.get_session(sid)["pending_action"] is None


def test_sessions_are_isolated(isolate_store):
    isolate_store.record_message("a", "user", "hello A")
    isolate_store.record_message("b", "user", "hello B")
    assert isolate_store.get_messages("a")[0]["content"] == "hello A"
    assert isolate_store.get_messages("b")[0]["content"] == "hello B"
    assert len(isolate_store.get_messages("a")) == 1
