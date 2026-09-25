"""Database-layer tests.

Hermetic by default: real-Postgres tests are SKIPPED unless
``AI_SCIENTIST_DB_TEST_URL`` is set (e.g. to the docker-compose Postgres, Neon,
or Supabase). Everything else runs on fakes so the unit suite never needs a
live database.

Covers (task §26): connection/migrations, CRUD, conversation persistence,
memory retrieval, research persistence, payload collections, jobs, failure
modes (§29), vector retrieval (§28), file metadata (§16).
"""
import os
import threading

import pytest

import database.store as store_mod
from database.repository import Repository, DEFAULT_USER_ID
from database import vector_memory as vm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LIVE_URL = os.environ.get("AI_SCIENTIST_DB_TEST_URL", "")


@pytest.fixture()
def repo():
    """Real Repository against live Postgres, or skip."""
    if not LIVE_URL:
        pytest.skip("AI_SCIENTIST_DB_TEST_URL not set — live-DB tests skipped")
    r = Repository(LIVE_URL)
    r.ensure_schema()
    r.reset_schema()
    r.ensure_schema()
    r.ensure_system_user()
    yield r
    r.close()


@pytest.fixture()
def fake_repo(monkeypatch):
    """Repository with all SQL-backed operations faked to in-memory dicts.

    Mirrors the real row shapes (camelCase payloads, context defaults) so the
    facade and vector-memory layers are exercised exactly as in production.
    """
    class FakeRepo(Repository):
        def __init__(self):
            self.tables = {
                "settings": {}, "jobs": [], "memories": [], "chunks": [],
                "documents": {}, "files": [], "projects": {},
                "payloads": {}, "events": {}, "reports": {},
                "conversations": set(), "messages": {}, "contexts": {},
                "papers": [],
            }
            self.migrations = []

        # ------------------------------------------------------ schema (fake)
        def ensure_schema(self):
            self.migrations = ["001_initial_schema.sql", "002_indexes.sql"]
            return list(self.migrations)

        def applied_migrations(self):
            return list(self.migrations)

        def reset_schema(self):
            self.__init__()

        # ------------------------------------------------------ projects (fake)
        def project_exists(self, project_id):
            return project_id in self.tables["projects"]

        def save_project(self, project_id, data, user_id=None):
            project = self.tables["projects"].setdefault(
                project_id, {"id": project_id, "agentLogs": [], "events": [],
                             "stageStates": {}})
            project.update(data)
            project.setdefault("stageStates", {}).update(data.get("stageStates") or {})

        def get_project(self, project_id):
            return self.tables["projects"].get(project_id)

        def list_projects(self, user_id=None, limit=200):
            return list(self.tables["projects"].values())[:limit]

        def delete_project(self, project_id):
            self.tables["projects"].pop(project_id, None)

        # ------------------------------------------------------ payloads (fake)
        def save_payload(self, project_id, kind, payload):
            self.tables["payloads"][(project_id, kind)] = payload

        def get_payload(self, project_id, kind, default=None):
            return self.tables["payloads"].get((project_id, kind), default)

        def append_agent_log(self, project_id, agent, message, status="IN_PROGRESS"):
            project = self.tables["projects"].setdefault(
                project_id, {"id": project_id, "agentLogs": [], "events": []})
            project["activeAgent"] = agent
            project.setdefault("agentLogs", []).append(
                {"timestamp": "now", "agent": agent, "message": message,
                 "status": status})

        def append_project_event(self, project_id, event_type, details=None):
            project = self.tables["projects"].setdefault(
                project_id, {"id": project_id, "agentLogs": [], "events": []})
            project.setdefault("events", []).append(
                {"type": event_type, "timestamp": "now", "details": details or {}})

        def list_project_events(self, project_id, limit=200):
            project = self.tables["projects"].get(project_id) or {}
            return project.get("events", [])

        # ------------------------------------------------------- reports (fake)
        def save_report(self, project_id, report_md, title=None):
            self.tables["reports"][project_id] = report_md

        def get_report(self, project_id):
            return self.tables["reports"].get(project_id)

        # -------------------------------------------------- conversations (fake)
        def ensure_conversation(self, conversation_id, user_id=None):
            self.tables["conversations"].add(conversation_id)
            self.tables["messages"].setdefault(conversation_id, [])

        def record_message(self, conversation_id, role, content, intent=None,
                           topic=None, research_id=None, pending_action=None,
                           message_id=None, created_at=None):
            self.ensure_conversation(conversation_id)
            message = {"id": message_id or f"msg-{len(self.tables['messages'][conversation_id])}",
                       "conversation_id": conversation_id, "role": role,
                       "content": content, "timestamp": created_at or "now",
                       "intent": intent, "topic": topic,
                       "research_id": research_id, "pending_action": pending_action}
            self.tables["messages"][conversation_id].append(message)
            return message

        def get_messages(self, conversation_id, limit=200):
            return list(self.tables["messages"].get(conversation_id, []))[:limit]

        def get_session(self, session_id):
            context = self.tables["contexts"].get(session_id, {})
            session = {"session_id": session_id, "last_user_message": None,
                       "last_assistant_message": None, "last_topic": None,
                       "last_reasoning_subjects": [], "recent_topics": [],
                       "pending_action": None, "active_project_id": None}
            session.update(context)
            session["messages"] = self.get_messages(session_id)
            return session

        def update_session(self, session_id, updates):
            if not updates:
                return
            updates = {k: v for k, v in updates.items()
                       if k not in ("messages", "session_id")}
            self.ensure_conversation(session_id)
            self.tables["contexts"].setdefault(session_id, {}).update(updates)

        def reconcile_stale_runs(self):
            stale = [pid for pid, p in self.tables["projects"].items()
                     if p.get("status") in ("QUEUED", "IN_PROGRESS", "RUNNING")]
            for pid in stale:
                self.tables["projects"][pid]["status"] = "FAILED"
            return stale

        # ------------------------------------------------------ settings (fake)
        def get_all_settings(self):
            return dict(self.tables["settings"])

        def set_settings(self, updates):
            self.tables["settings"].update(updates)

        # ---------------------------------------------------------- jobs (fake)
        def enqueue_job(self, job_type, payload, priority=5, project_id=None):
            job = {"id": f"job-{len(self.tables['jobs'])}", "type": job_type,
                   "payload": payload, "priority": priority, "status": "QUEUED"}
            self.tables["jobs"].append(job)
            return job["id"]

        def claim_next_job(self, job_types=None):
            for job in sorted(self.tables["jobs"], key=lambda j: j["priority"]):
                if job["status"] == "QUEUED" and (not job_types or job["type"] in job_types):
                    job["status"] = "RUNNING"
                    return {"id": job["id"], "type": job["type"],
                            "payload": job["payload"]}
            return None

        def finish_job(self, job_id, success, error=None):
            for job in self.tables["jobs"]:
                if job["id"] == job_id:
                    job["status"] = "COMPLETED" if success else "FAILED"
                    job["error"] = error

        # ------------------------------------------------------- memories (fake)
        def add_memory(self, user_id, memory_type, content, conversation_id=None,
                       metadata=None, embedding=None):
            mid = f"mem-{len(self.tables['memories'])}"
            self.tables["memories"].append({"id": mid, "user_id": user_id,
                                            "memory_type": memory_type,
                                            "content": content,
                                            "embedding": embedding})
            return mid

        def search_memories_semantic(self, user_id, query_embedding, limit=5):
            from database.vector_memory import cosine_similarity
            scored = [(m, cosine_similarity(query_embedding, m["embedding"]))
                      for m in self.tables["memories"]
                      if m["user_id"] == user_id and m["embedding"]]
            scored.sort(key=lambda pair: pair[1], reverse=True)
            return [{"id": m["id"], "memoryType": m["memory_type"],
                     "content": m["content"], "score": score}
                    for m, score in scored[:limit]]

        # ---------------------------------------------------- documents (fake)
        def add_document(self, project_id, user_id, title, source=None,
                         doc_type=None, metadata=None):
            did = f"doc-{len(self.tables['documents'])}"
            self.tables["documents"][did] = {"id": did, "project_id": project_id,
                                             "title": title, "source": source}
            return did

        def add_chunk(self, document_id, chunk_index, content, page=None,
                      section=None, embedding=None, metadata=None):
            cid = f"chunk-{len(self.tables['chunks'])}"
            self.tables["chunks"].append({"id": cid, "document_id": document_id,
                                          "chunk_index": chunk_index,
                                          "content": content,
                                          "embedding": embedding})
            return cid

        def search_chunks_semantic(self, query_embedding, project_id=None, limit=5):
            from database.vector_memory import cosine_similarity
            docs = self.tables["documents"]
            scored = [(c, cosine_similarity(query_embedding, c["embedding"]))
                      for c in self.tables["chunks"] if c["embedding"]]
            scored.sort(key=lambda pair: pair[1], reverse=True)
            results = []
            for c, score in scored[:limit]:
                doc = docs.get(c["document_id"], {})
                results.append({"chunkId": c["id"], "content": c["content"],
                                "documentId": c["document_id"],
                                "documentTitle": doc.get("title"),
                                "documentSource": doc.get("source"),
                                "score": score})
            return results

        def chunk_count(self, document_id):
            return len([c for c in self.tables["chunks"]
                        if c["document_id"] == document_id])

    return FakeRepo()


@pytest.fixture()
def db_store(monkeypatch, fake_repo):
    """ResearchStore wired to the fake repo (DB mode, no live Postgres)."""
    # Never attempt a real connection: _make_repo returns None, the fake is
    # injected afterwards.
    monkeypatch.setattr(store_mod, "DB_DISABLED", False)
    monkeypatch.setattr(store_mod.ResearchStore, "_make_repo",
                        staticmethod(lambda: None))
    s = store_mod.ResearchStore(filepath=str(_tmp_store(monkeypatch)))
    s.repo = fake_repo
    s.backend = fake_repo
    s._db_healthy = True
    return s


def _tmp_store(monkeypatch):
    import tempfile
    return os.path.join(tempfile.mkdtemp(), "store.json")


# ---------------------------------------------------------------------------
# Connection / migrations (live only)
# ---------------------------------------------------------------------------

def test_migrations_apply_idempotently(repo):
    first = repo.ensure_schema()
    second = repo.ensure_schema()
    assert first == []
    assert second == []
    applied = repo.applied_migrations()
    assert "001_initial_schema.sql" in applied
    assert "002_indexes.sql" in applied


def test_project_crud_round_trip(repo):
    repo.save_project("proj-test1", {
        "id": "proj-test1", "name": "Test Project", "objective": "Test objective",
        "status": "QUEUED", "maxExperiments": 7, "budgetMins": 42,
        "datasetName": "ds.csv", "llmProvider": "Mistral",
        "stageStates": {"research_question": "COMPLETED"},
        "customFutureField": {"kept": True},
    })
    project = repo.get_project("proj-test1")
    assert project["name"] == "Test Project"
    assert project["maxExperiments"] == 7
    assert project["budgetMins"] == 42
    assert project["stageStates"] == {"research_question": "COMPLETED"}
    assert project["customFutureField"] == {"kept": True}

    repo.save_project("proj-test1", {"status": "COMPLETED", "bestMetric": "ACCURACY: 0.9"})
    project = repo.get_project("proj-test1")
    assert project["status"] == "COMPLETED"
    assert project["bestMetric"] == "ACCURACY: 0.9"
    assert project["maxExperiments"] == 7  # unchanged by patch

    assert any(p["id"] == "proj-test1" for p in repo.list_projects())
    repo.delete_project("proj-test1")
    assert repo.get_project("proj-test1") is None


def test_invalid_status_coerced_not_rejected(repo):
    repo.save_project("proj-test2", {"id": "proj-test2", "name": "X",
                                     "objective": "Y", "status": "WEIRD-STATUS"})
    assert repo.get_project("proj-test2")["status"] == "FAILED"


def test_payload_collections_round_trip(repo):
    repo.save_baselines("proj-test3", [{"name": "Logistic Regression",
                                        "metrics": {"accuracy": 0.9}}])
    repo.save_tree_nodes("proj-test3", [{"id": "node-root", "children": []}])
    repo.save_dataset_report("proj-test3", {"rowCount": 1500,
                                            "targetCandidate": "is_fraud"})
    repo.save_error_analysis("proj-test3", {"falseNegativesCount": 17})
    assert repo.get_baselines("proj-test3")[0]["metrics"]["accuracy"] == 0.9
    assert repo.get_tree_nodes("proj-test3")[0]["id"] == "node-root"
    assert repo.get_dataset_report("proj-test3")["rowCount"] == 1500
    assert repo.get_error_analysis("proj-test3")["falseNegativesCount"] == 17


def test_agent_logs_and_events_append(repo):
    repo.save_project("proj-test4", {"id": "proj-test4", "name": "N", "objective": "O"})
    repo.append_agent_log("proj-test4", "BASELINE_AGENT", "training...", "IN_PROGRESS")
    repo.append_agent_log("proj-test4", "REPORT_AGENT", "done", "COMPLETED")
    repo.append_project_event("proj-test4", "research.started", {"objective": "O"})
    logs = repo.get_agent_logs("proj-test4")
    assert [log["agent"] for log in logs] == ["BASELINE_AGENT", "REPORT_AGENT"]
    events = repo.list_project_events("proj-test4")
    assert events[0]["type"] == "research.started"
    project = repo.get_project("proj-test4")
    assert project["activeAgent"] == "REPORT_AGENT"
    assert project["agentLogs"] == logs


def test_conversation_persistence_and_reconciliation(repo):
    repo.record_message("conv-live", "user", "hello world")
    repo.record_message("conv-live", "assistant", "greetings")
    messages = repo.get_messages("conv-live")
    assert [m["role"] for m in messages] == ["user", "assistant"]
    session = repo.get_session("conv-live")
    assert session["last_topic"] is None

    repo.save_project("proj-test5", {"id": "proj-test5", "name": "N", "objective": "O",
                                     "status": "RUNNING"})
    stale = repo.reconcile_stale_runs()
    assert "proj-test5" in stale
    assert repo.get_project("proj-test5")["status"] == "FAILED"
    repo.delete_project("proj-test5")


# ---------------------------------------------------------------------------
# Facade + sessions (fake repo — runs everywhere)
# ---------------------------------------------------------------------------

def test_store_facade_delegates_to_repo(db_store, fake_repo):
    project = db_store.create_project(
        "proj-facade", "Facade Test", "objective text", "ds.csv", 15, "Mistral",
        max_experiments=3, dataset_path="/tmp/ds.csv", dataset_meta={"rows": 10})
    assert project["status"] == "QUEUED"
    stored = fake_repo.get_project("proj-facade")
    assert stored is not None
    assert stored["maxExperiments"] == 3

    db_store.update_project("proj-facade", {"status": "RUNNING"})
    assert db_store.get_project("proj-facade")["status"] == "RUNNING"


def test_store_messages_persist_through_facade(db_store):
    db_store.record_message("conv-facade", "user", "what is pgvector?",
                            intent="EXPLANATION", topic="pgvector")
    db_store.record_message("conv-facade", "assistant", "a vector extension for postgres")
    messages = db_store.get_messages("conv-facade")
    assert [m["content"] for m in messages] == [
        "what is pgvector?", "a vector extension for postgres"]
    session = db_store.get_session("conv-facade")
    assert session["session_id"] == "conv-facade"


def test_store_degrades_to_file_when_db_fails(db_store, monkeypatch):
    assert db_store.using_postgres()
    # Force the next DB write to fail.
    def boom(*args, **kwargs):
        raise RuntimeError("connection reset")
    monkeypatch.setattr(db_store.repo, "save_project", boom)
    db_store.create_project("proj-degrade", "Degrade", "objective", "ds.csv", 10, "P")
    assert not db_store.using_postgres()
    # The project must exist in the JSON fallback.
    assert "proj-degrade" in db_store.data["projects"]


def test_session_pending_action_flow(db_store):
    db_store.set_pending_action("conv-pa", "START_RESEARCH", topic="quantum computing")
    session = db_store.get_session("conv-pa")
    assert session["pending_action"]["type"] == "START_RESEARCH"
    db_store.clear_pending_action("conv-pa")
    assert db_store.get_session("conv-pa")["pending_action"] is None


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def test_job_queue_claim_order(fake_repo):
    fake_repo.enqueue_job("research_pipeline", {"projectId": "p1"}, priority=9)
    fake_repo.enqueue_job("research_pipeline", {"projectId": "p2"}, priority=1)
    job = fake_repo.claim_next_job()
    assert job["payload"]["projectId"] == "p2"  # lower priority number first
    fake_repo.finish_job(job["id"], success=True)
    statuses = [j["status"] for j in fake_repo.tables["jobs"]]
    assert "COMPLETED" in statuses


# ---------------------------------------------------------------------------
# Vector memory (§9, §28)
# ---------------------------------------------------------------------------

def test_hash_embedding_deterministic_and_normalized():
    a = vm._hash_embedding("gradient descent optimization")
    b = vm._hash_embedding("gradient descent optimization")
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-9
    assert len(a) == vm.EMBEDDING_DIM


def test_related_text_scores_higher_than_unrelated():
    query = vm._hash_embedding("neural network training")
    related = vm._hash_embedding("training deep neural networks with backpropagation")
    unrelated = vm._hash_embedding("recipe for chocolate chip cookies")
    assert vm.cosine_similarity(query, related) > vm.cosine_similarity(query, unrelated)


def test_semantic_memory_retrieval(fake_repo):
    vm.add_memory(fake_repo, DEFAULT_USER_ID, "FACT",
                  "The user prefers concise answers about gradient descent")
    vm.add_memory(fake_repo, DEFAULT_USER_ID, "PREFERENCE",
                  "The user likes chocolate cake recipes")
    results = vm.search_memories(fake_repo, DEFAULT_USER_ID, "how does gradient descent work?")
    assert results
    assert "gradient descent" in results[0]["content"].lower()


def test_document_chunks_semantic_retrieval_with_sources(fake_repo):
    doc_id = vm.add_document_chunks(
        fake_repo, None, DEFAULT_USER_ID, "ML Notes",
        "XGBoost is a gradient boosted decision tree library. " * 10
        + "Banana bread requires ripe bananas and flour. " * 10,
        source="notes.md")
    assert fake_repo.chunk_count(doc_id) > 1
    results = vm.search_chunks(fake_repo, "gradient boosted trees xgboost")
    assert results
    top = results[0]
    assert "xgboost" in top["content"].lower()
    assert top["documentTitle"] == "ML Notes"
    assert top["documentSource"] == "notes.md"


# ---------------------------------------------------------------------------
# File store (§16)
# ---------------------------------------------------------------------------

def test_file_store_local_round_trip(tmp_path):
    from database.file_store import FileStore
    store = FileStore({"root": str(tmp_path)})
    key, size, digest = store.put("datasets/p1/train.csv", b"a,b\n1,2\n",
                                  content_type="text/csv")
    assert key == "datasets/p1/train.csv"
    assert size == len(b"a,b\n1,2\n")
    assert len(digest) == 64
    assert store.get(key) == b"a,b\n1,2\n"
    assert store.local_path(key).endswith("train.csv")
    assert store.delete(key) is True
    assert store.get(key) is None


def test_file_store_rejects_path_traversal(tmp_path):
    from database.file_store import FileStore
    store = FileStore({"root": str(tmp_path)})
    with pytest.raises(ValueError):
        store.put("../escape.csv", b"x")


# ---------------------------------------------------------------------------
# Failure modes (§29) — pure-logic checks that run everywhere
# ---------------------------------------------------------------------------

def test_pgvector_literal_format():
    from database.repository import _vec_literal
    assert _vec_literal([1.0, 2.5]) == "[1.0,2.5]"
    assert _vec_literal(None) is None


def test_thread_isolated_connections():
    """threading.local storage: values set in one worker are invisible in
    another, so per-thread connections can never be shared across threads."""
    repo = Repository("postgresql://unused")
    sentinel = object()
    seen = {}

    def setter():
        repo._local.conn = sentinel

    def reader():
        seen["other"] = getattr(repo._local, "conn", None)

    t1 = threading.Thread(target=setter)
    t2 = threading.Thread(target=reader)
    t1.start(); t1.join()
    t2.start(); t2.join()
    assert seen["other"] is None  # no cross-thread leakage
