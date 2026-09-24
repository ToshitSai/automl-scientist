"""Tests for the Postgres (Neon) store backend and its integration with
ResearchStore.

Hermetic: no real database or network. A fake backend/table stands in for Neon
so we can prove the two properties that matter for cross-session memory:
  1. Session writes are persisted per-row (namespace='sessions', key=session_id).
  2. A *second* store instance (a cold serverless instance) reading the same
     table sees the first instance's messages — i.e. memory survives restarts.
"""
import pytest

from database.db import PostgresBackend, rows_from_data, data_from_rows


@pytest.fixture(autouse=True)
def _no_real_db(monkeypatch):
    """Construct stores without a real DATABASE_URL so __init__ never attempts a
    live connection; tests inject a fake backend explicitly."""
    monkeypatch.delenv("DATABASE_URL", raising=False)


# --------------------------------------------------------------------------- #
# Pure serialization helpers
# --------------------------------------------------------------------------- #
def test_rows_from_data_splits_id_keyed_namespaces_and_reserves_settings():
    data = {
        "projects": {"p1": {"id": "p1"}, "p2": {"id": "p2"}},
        "sessions": {"s1": {"messages": []}},
        "baselines": {"p1": [{"acc": 0.9}]},       # value is a list
        "reports": {"p1": "# markdown string"},     # value is a string
        "settings": {"llmProvider": "x", "apiKeySet": True},  # flat dict
    }
    rows = dict(((ns, k), v) for (ns, k, v) in rows_from_data(data))

    assert rows[("projects", "p1")] == {"id": "p1"}
    assert rows[("projects", "p2")] == {"id": "p2"}
    assert rows[("sessions", "s1")] == {"messages": []}
    assert rows[("baselines", "p1")] == [{"acc": 0.9}]
    assert rows[("reports", "p1")] == "# markdown string"
    # settings is stored whole under the reserved key, not split per-field.
    assert rows[("settings", "_")] == {"llmProvider": "x", "apiKeySet": True}


def test_data_from_rows_round_trips():
    original = {
        "projects": {"p1": {"id": "p1", "status": "DONE"}},
        "sessions": {"s1": {"messages": [{"role": "user", "content": "hi"}]}},
        "settings": {"llmProvider": "Mistral"},
        "reports": {},
    }
    base = {"projects": {}, "sessions": {}, "settings": {}, "reports": {}, "datasets": {}}
    rebuilt = data_from_rows(rows_from_data(original), base)
    assert rebuilt["projects"] == original["projects"]
    assert rebuilt["sessions"] == original["sessions"]
    assert rebuilt["settings"] == original["settings"]
    assert rebuilt["reports"] == {}


# --------------------------------------------------------------------------- #
# PostgresBackend against a fake connection (verifies SQL + JSONB wrapping)
# --------------------------------------------------------------------------- #
class _FakeCursor:
    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many

    def executemany(self, sql, seq):
        for params in seq:
            self._conn._insert(params)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    """Mimics the slice of the psycopg connection API the backend uses, backed
    by an in-memory {(namespace, key): value} table."""
    closed = False

    def __init__(self):
        self.table = {}

    def _insert(self, params):
        ns, key, wrapped = params
        # The backend wraps values in psycopg's Json adapter; unwrap via .obj.
        self.table[(ns, key)] = getattr(wrapped, "obj", wrapped)

    def execute(self, sql, params=None):
        s = sql.strip()
        if s.startswith("SELECT value"):
            val = self.table.get((params[0], params[1]))
            return _FakeCursor(one=(val,) if val is not None else None)
        if s.startswith("SELECT namespace"):
            return _FakeCursor(many=[(ns, k, v) for (ns, k), v in self.table.items()])
        if "INSERT INTO kv_store" in s:
            self._insert(params)
            return _FakeCursor()
        return _FakeCursor()  # CREATE TABLE etc.

    def cursor(self):
        cur = _FakeCursor()
        cur._conn = self
        return cur

    def commit(self):
        pass


def test_backend_save_get_load_round_trip(monkeypatch):
    pytest.importorskip("psycopg")
    backend = PostgresBackend("postgresql://unused")
    fake = _FakeConn()
    monkeypatch.setattr(backend, "_ready", lambda: fake)

    backend.save_row("sessions", "s1", {"messages": [{"content": "hello"}]})
    assert backend.get_row("sessions", "s1") == {"messages": [{"content": "hello"}]}
    assert backend.get_row("sessions", "missing") is None

    loaded = backend.load_all({"sessions": {}, "projects": {}})
    assert loaded["sessions"]["s1"]["messages"][0]["content"] == "hello"


def test_backend_load_all_returns_none_on_empty_table(monkeypatch):
    pytest.importorskip("psycopg")
    backend = PostgresBackend("postgresql://unused")
    monkeypatch.setattr(backend, "_ready", lambda: _FakeConn())
    assert backend.load_all({"sessions": {}}) is None


# --------------------------------------------------------------------------- #
# ResearchStore integration: cross-instance (cold-start) memory persistence
# --------------------------------------------------------------------------- #
class _SharedFakeBackend:
    """Stands in for PostgresBackend but shares one table across instances, so
    two ResearchStore objects behave like two serverless instances over one DB."""
    def __init__(self, table):
        self.table = table

    def load_all(self, base):
        if not self.table:
            return None
        return data_from_rows([(ns, k, v) for (ns, k), v in self.table.items()], base)

    def get_row(self, ns, key):
        return self.table.get((ns, key))

    def save_row(self, ns, key, value):
        self.table[(ns, key)] = value

    def save_all(self, data):
        for ns, k, v in rows_from_data(data):
            self.table[(ns, k)] = v

    def reset(self):
        pass


def _make_store(tmp_path, table, name):
    import database.store as store_mod
    s = store_mod.ResearchStore(filepath=str(tmp_path / f"{name}.json"))
    s.backend = _SharedFakeBackend(table)
    return s


def test_memory_persists_across_cold_instances(tmp_path):
    table = {}
    # Instance A handles turn 1 and records a message.
    a = _make_store(tmp_path, table, "a")
    a.update_session("conv-1", {"last_topic": "gradient descent"})
    a.record_message("conv-1", "user", "Tell me about gradient descent")

    # A brand-new instance (cold start) reads the same table and must see it.
    b = _make_store(tmp_path, table, "b")
    msgs = b.get_messages("conv-1")
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Tell me about gradient descent"
    assert b.get_session("conv-1")["last_topic"] == "gradient descent"


def test_session_row_is_written_under_sessions_namespace(tmp_path):
    table = {}
    s = _make_store(tmp_path, table, "s")
    s.record_message("conv-9", "assistant", "hi there")
    # Exactly one row, keyed to the session — not a single global blob.
    assert ("sessions", "conv-9") in table
    assert table[("sessions", "conv-9")]["messages"][0]["content"] == "hi there"


def test_warm_instance_rereads_session_written_by_another_instance(tmp_path):
    table = {}
    a = _make_store(tmp_path, table, "a")
    b = _make_store(tmp_path, table, "b")
    # A records first; B (already constructed, warm) must still see it because
    # get_session re-reads the row from the backend on every access.
    a.record_message("conv-x", "user", "first")
    b.record_message("conv-x", "assistant", "second")
    contents = [m["content"] for m in b.get_messages("conv-x")]
    assert contents == ["first", "second"]


def test_file_backend_used_when_no_database_url(tmp_path, monkeypatch):
    """No DATABASE_URL -> backend is None -> the JSON file path still works."""
    import database.store as store_mod
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = store_mod.ResearchStore(filepath=str(tmp_path / "file.json"))
    assert s.backend is None
    s.record_message("conv-file", "user", "persisted to disk")
    # Reload from the file with a fresh instance.
    s2 = store_mod.ResearchStore(filepath=str(tmp_path / "file.json"))
    assert s2.get_messages("conv-file")[0]["content"] == "persisted to disk"
