"""Cross-instance persistence tests (the reason the Postgres layer exists).

The legacy kv_store mirror tests were retired with the KV backend; these are
the equivalent guarantees against the new architecture: two ResearchStore
facades sharing one repository behave like two serverless instances over one
database — session writes from one are visible to the other, including a cold
instance constructed *after* the writes and a warm instance constructed before.
"""
import pytest

import database.store as store_mod


@pytest.fixture(autouse=True)
def _no_real_db(monkeypatch):
    """Construct stores without a real DATABASE_URL; the fake is injected."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(store_mod, "DB_DISABLED", False)
    monkeypatch.setattr(store_mod.ResearchStore, "_make_repo",
                        staticmethod(lambda: None))


class SharedRepo:
    """Minimal repository standing in for Postgres: one shared 'table' across
    every ResearchStore that receives this same instance (or a clone sharing
    the same dicts), like two serverless instances over one database."""

    def __init__(self, tables=None):
        self.tables = tables if tables is not None else {
            "sessions": {},   # sid -> context dict
            "messages": {},   # sid -> [message dicts]
            "conversations": set(),
        }

    # -- conversations / messages -------------------------------------------
    def ensure_conversation(self, conversation_id, user_id=None):
        self.tables["conversations"].add(conversation_id)
        self.tables["messages"].setdefault(conversation_id, [])

    def record_message(self, conversation_id, role, content, intent=None,
                       topic=None, research_id=None, pending_action=None,
                       message_id=None, created_at=None):
        self.ensure_conversation(conversation_id)
        message = {"id": message_id or f"m{len(self.tables['messages'][conversation_id])}",
                   "conversation_id": conversation_id, "role": role,
                   "content": content, "timestamp": created_at or "now",
                   "intent": intent, "topic": topic,
                   "research_id": research_id, "pending_action": pending_action}
        self.tables["messages"][conversation_id].append(message)
        return message

    def get_messages(self, conversation_id, limit=200):
        return list(self.tables["messages"].get(conversation_id, []))[:limit]

    # -- session context ------------------------------------------------------
    def get_session(self, session_id):
        session = {"session_id": session_id, "last_user_message": None,
                   "last_assistant_message": None, "last_topic": None,
                   "last_reasoning_subjects": [], "recent_topics": [],
                   "pending_action": None, "active_project_id": None}
        session.update(self.tables["sessions"].get(session_id, {}))
        session["messages"] = self.get_messages(session_id)
        return session

    def update_session(self, session_id, updates):
        if not updates:
            return
        updates = {k: v for k, v in updates.items()
                   if k not in ("messages", "session_id")}
        self.ensure_conversation(session_id)
        self.tables["sessions"].setdefault(session_id, {}).update(updates)


def _make_store(tmp_path, repo, name):
    s = store_mod.ResearchStore(filepath=str(tmp_path / f"{name}.json"))
    s.repo = repo
    s.backend = repo
    s._db_healthy = True
    return s


def test_memory_persists_across_cold_instances(tmp_path):
    repo = SharedRepo()
    # Instance A handles turn 1 and records a message.
    a = _make_store(tmp_path, repo, "a")
    a.update_session("conv-1", {"last_topic": "gradient descent"})
    a.record_message("conv-1", "user", "Tell me about gradient descent")

    # A brand-new instance (cold start) over the same DB must see it.
    b = _make_store(tmp_path, repo, "b")
    msgs = b.get_messages("conv-1")
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Tell me about gradient descent"
    assert b.get_session("conv-1")["last_topic"] == "gradient descent"


def test_warm_instance_sees_messages_written_by_another_instance(tmp_path):
    repo = SharedRepo()
    a = _make_store(tmp_path, repo, "a")
    b = _make_store(tmp_path, repo, "b")
    # A records first; B (already constructed, warm) must still see it because
    # get_messages reads through to the repository on every access.
    a.record_message("conv-x", "user", "first")
    b.record_message("conv-x", "assistant", "second")
    contents = [m["content"] for m in b.get_messages("conv-x")]
    assert contents == ["first", "second"]


def test_message_rows_are_keyed_to_their_conversation(tmp_path):
    repo = SharedRepo()
    s = _make_store(tmp_path, repo, "s")
    s.record_message("conv-9", "assistant", "hi there")
    assert "conv-9" in repo.tables["conversations"]
    assert repo.tables["messages"]["conv-9"][0]["content"] == "hi there"


def test_file_backend_still_works_when_no_repo(tmp_path, monkeypatch):
    """No DATABASE_URL -> repo is None -> the JSON file path is the store."""
    import database.store as store_mod
    monkeypatch.setattr(store_mod, "DB_DISABLED", True)
    s = store_mod.ResearchStore(filepath=str(tmp_path / "file.json"))
    assert s.repo is None
    s.record_message("conv-file", "user", "persisted to disk")
    s2 = store_mod.ResearchStore(filepath=str(tmp_path / "file.json"))
    assert s2.get_messages("conv-file")[0]["content"] == "persisted to disk"
