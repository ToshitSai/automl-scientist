"""PostgreSQL data access layer (psycopg3) for the AI Scientist.

Repository owns connections and SQL; database/store.py stays the facade the
rest of the app already imports. Design points:

  * Parameterized SQL everywhere (security §21); no string interpolation of
    user data.
  * One thread-local connection per worker thread (the research pipeline runs
    in background threads). Connections are validated with a 1s SELECT 1 and
    transparently reopened after serverless connection drops.
  * Row shapes mirror the legacy store payloads (camelCase keys such as
    ``maxExperiments`` / ``bestMetric``) so backend routes, the orchestrator
    and the frontend keep working unchanged.
  * List- or dict-valued per-project payload collections (agent logs, events,
    tree nodes, baselines, dataset reports, error analyses) are stored as
    JSONB rows keyed by project id — the app reads/writes them whole, which is
    exactly one row upsert.
  * Errors propagate to the facade, which decides fallback behavior; nothing
    here swallows errors silently.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from typing import Any, Dict, List, Optional

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000"
DEFAULT_USER_EXTERNAL_ID = "system"


# ---------------------------------------------------------------------------
# pgvector helpers
# ---------------------------------------------------------------------------

def _vec_literal(vec: Optional[List[float]]) -> Optional[str]:
    """Format a float sequence as a pgvector text literal ('[1,2,3]')."""
    if vec is None:
        return None
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class Repository:
    """SQL access layer: typed columns for what we query, JSONB for payloads."""

    def __init__(self, database_url: Optional[str] = None):
        self.url = (database_url
                    or os.environ.get("DATABASE_URL")
                    or "").strip()
        self._local = threading.local()
        self._pgvector_cache: Optional[bool] = None

    def _has_pgvector(self) -> bool:
        """True when the `vector` extension is installed on the connected
        server. When absent (e.g. the default EDB Windows build), memory/chunk
        writes store content without embeddings and semantic searches return
        empty results instead of failing — everything else keeps working."""
        if self._pgvector_cache is None:
            try:
                row = self._query_one(
                    "SELECT count(*) FROM pg_extension WHERE extname='vector'")
                self._pgvector_cache = bool(row and int(row[0]) > 0)
            except Exception:
                self._pgvector_cache = False
        return self._pgvector_cache

    # ------------------------------------------------------------- connections
    def _conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.execute("SELECT 1")
                return conn
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                self._local.conn = None
        import psycopg
        conn = psycopg.connect(self.url, connect_timeout=10)
        conn.autocommit = False
        self._local.conn = conn
        return conn

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None

    # ------------------------------------------------------------- SQL helpers
    def _execute(self, sql: str, params: tuple = ()) -> List[tuple]:
        conn = self._conn()
        try:
            cur = conn.execute(sql, params)
            rows = cur.fetchall() if cur.description else []
            conn.commit()
            return rows
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def _executemany(self, sql: str, seq):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.executemany(sql, seq)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def _query_one(self, sql: str, params: tuple = ()):
        rows = self._execute(sql, params)
        return rows[0] if rows else None

    @staticmethod
    def _iso(dt) -> Optional[str]:
        return dt.isoformat() if dt is not None else None

    # ------------------------------------------------------------- migrations
    # Session-level advisory lock key guarding schema migrations. Multiple
    # serverless instances cold-starting at once must not apply the same
    # migration concurrently: the loser would hit the schema_migrations UNIQUE
    # constraint, raise, and (via the facade) silently degrade that instance to
    # the ephemeral JSON file. The lock serializes them instead.
    _SCHEMA_LOCK_KEY = 724180553  # arbitrary fixed bigint

    def ensure_schema(self) -> List[str]:
        """Apply migrations/*.sql in filename order once each. Returns names."""
        migration_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations")
        if not os.path.isdir(migration_dir):
            return []
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
        conn.commit()
        # Block until no other instance is migrating, then re-check each name
        # inside the lock (a peer may have applied it while we waited).
        conn.execute("SELECT pg_advisory_lock(%s)", (self._SCHEMA_LOCK_KEY,))
        applied: List[str] = []
        try:
            for name in sorted(os.listdir(migration_dir)):
                if not name.endswith(".sql"):
                    continue
                exists = self._query_one(
                    "SELECT 1 FROM schema_migrations WHERE migration=%s", (name,))
                if exists:
                    continue
                with open(os.path.join(migration_dir, name), "r", encoding="utf-8") as f:
                    sql = f.read()
                try:
                    conn.execute(sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (migration) VALUES (%s)", (name,))
                    conn.commit()
                    applied.append(name)
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    raise
        finally:
            try:
                conn.execute("SELECT pg_advisory_unlock(%s)", (self._SCHEMA_LOCK_KEY,))
                conn.commit()
            except Exception:
                pass
        return applied

    def applied_migrations(self) -> List[str]:
        return [r[0] for r in self._execute(
            "SELECT migration FROM schema_migrations ORDER BY id")]

    def reset_schema(self):
        """Drop every application table (migrations re-apply cleanly)."""
        tables = [
            "document_chunks", "documents", "jobs", "tool_calls", "reports",
            "artifacts", "experiment_relationships", "hypotheses",
            "experiment_metrics", "experiments", "citations", "papers",
            "research_sources", "research_events", "research_sessions",
            "dataset_files", "dataset_versions", "datasets",
            "research_projects", "conversation_context", "messages",
            "conversations", "memories", "files", "settings", "users",
            "kv_store", "schema_migrations",
        ]
        conn = self._conn()
        for t in tables:
            conn.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
        conn.commit()

    # --------------------------------------------------------------- settings
    def get_all_settings(self) -> Dict[str, Any]:
        return {r[0]: r[1] for r in self._execute("SELECT key, value FROM settings")}

    def set_settings(self, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        from psycopg.types.json import Json
        self._executemany(
            """INSERT INTO settings (key, value) VALUES (%s, %s)
               ON CONFLICT (key) DO UPDATE
               SET value = EXCLUDED.value, updated_at = now()""",
            [(k, Json(v)) for k, v in updates.items()],
        )

    # ------------------------------------------------------------------ users
    def ensure_system_user(self) -> None:
        self._execute(
            """INSERT INTO users (id, external_id, display_name)
               VALUES (%s, %s, 'Local User')
               ON CONFLICT (id) DO NOTHING""",
            (DEFAULT_USER_ID, DEFAULT_USER_EXTERNAL_ID),
        )

    def get_or_create_user(self, external_id: str,
                           display_name: Optional[str] = None) -> str:
        row = self._query_one(
            "SELECT id FROM users WHERE external_id=%s", (external_id,))
        if row:
            return row[0]
        user_id = str(uuid.uuid4())
        self._execute(
            "INSERT INTO users (id, external_id, display_name) VALUES (%s, %s, %s)",
            (user_id, external_id, display_name),
        )
        return user_id

    # ------------------------------------------------------------------- jobs
    def enqueue_job(self, job_type: str, payload: Dict[str, Any],
                    priority: int = 5,
                    project_id: Optional[str] = None) -> str:
        from psycopg.types.json import Json
        job_id = str(uuid.uuid4())
        self._execute(
            """INSERT INTO jobs (id, job_type, payload, priority, project_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (job_id, job_type, Json(payload or {}), priority, project_id),
        )
        return job_id

    def claim_next_job(self,
                       job_types: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Atomically claim one queued job (FOR UPDATE SKIP LOCKED)."""
        conn = self._conn()
        try:
            filter_sql = ""
            params: List[Any] = []
            if job_types:
                filter_sql = "AND job_type = ANY(%s)"
                params.append(job_types)
            cur = conn.execute(
                f"""SELECT id, job_type, payload FROM jobs
                    WHERE status='QUEUED' AND scheduled_at <= now() {filter_sql}
                    ORDER BY priority, scheduled_at
                    FOR UPDATE SKIP LOCKED LIMIT 1""",
                tuple(params),
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return None
            from psycopg.types.json import Json
            conn.execute(
                """UPDATE jobs SET status='RUNNING', started_at=now(),
                          attempts=attempts+1, updated_at=now() WHERE id=%s""",
                (row[0],),
            )
            conn.commit()
            return {"id": row[0], "type": row[1], "payload": row[2]}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def finish_job(self, job_id: str, success: bool,
                   error: Optional[str] = None) -> None:
        status = "COMPLETED" if success else "FAILED"
        self._execute(
            """UPDATE jobs SET status=%s, finished_at=now(), last_error=%s,
                      updated_at=now() WHERE id=%s""",
            (status, error, job_id),
        )

    def list_jobs(self, status: Optional[str] = None,
                  limit: int = 50) -> List[Dict[str, Any]]:
        where, params = "", []
        if status:
            where, params = "WHERE status=%s", [status]
        params.append(limit)
        rows = self._execute(
            f"""SELECT id, job_type, payload, status, priority, attempts,
                       last_error, created_at, started_at, finished_at
                FROM jobs {where} ORDER BY created_at DESC LIMIT %s""",
            tuple(params),
        )
        return [{
            "id": r[0], "jobType": r[1], "payload": r[2], "status": r[3],
            "priority": r[4], "attempts": r[5], "lastError": r[6],
            "createdAt": self._iso(r[7]), "startedAt": self._iso(r[8]),
            "finishedAt": self._iso(r[9]),
        } for r in rows]

    # --------------------------------------------------------------- memories
    def add_memory(self, user_id: str, memory_type: str, content: str,
                   conversation_id: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None,
                   embedding: Optional[List[float]] = None) -> str:
        from psycopg.types.json import Json
        memory_id = str(uuid.uuid4())
        if embedding is not None and self._has_pgvector():
            self._execute(
                """INSERT INTO memories
                       (id, user_id, conversation_id, memory_type, content, metadata, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s::vector)""",
                (memory_id, user_id, conversation_id, memory_type, content,
                 Json(metadata or {}), _vec_literal(embedding)),
            )
        else:
            self._execute(
                """INSERT INTO memories
                       (id, user_id, conversation_id, memory_type, content, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (memory_id, user_id, conversation_id, memory_type, content,
                 Json(metadata or {})),
            )
        return memory_id

    def list_memories(self, user_id: str, memory_type: Optional[str] = None,
                      limit: int = 50) -> List[Dict[str, Any]]:
        where, params = "WHERE user_id=%s", [user_id]
        if memory_type:
            where += " AND memory_type=%s"
            params.append(memory_type)
        params.append(limit)
        rows = self._execute(
            f"""SELECT id, memory_type, content, metadata, created_at
                FROM memories {where} ORDER BY created_at DESC LIMIT %s""",
            tuple(params),
        )
        return [{"id": r[0], "memoryType": r[1], "content": r[2],
                 "metadata": r[3], "createdAt": self._iso(r[4])} for r in rows]

    def search_memories_semantic(self, user_id: str,
                                 query_embedding: List[float],
                                 limit: int = 5) -> List[Dict[str, Any]]:
        if not self._has_pgvector():
            return []
        rows = self._execute(
            """SELECT id, memory_type, content,
                      1 - (embedding <=> %s::vector) AS score
               FROM memories
               WHERE user_id=%s AND embedding IS NOT NULL
               ORDER BY embedding <=> %s::vector LIMIT %s""",
            (_vec_literal(query_embedding), user_id,
             _vec_literal(query_embedding), limit),
        )
        return [{"id": r[0], "memoryType": r[1], "content": r[2],
                 "score": float(r[3])} for r in rows]

    # ---------------------------------------------------------- documents/RAG
    def add_document(self, project_id: Optional[str], user_id: Optional[str],
                     title: str, source: Optional[str] = None,
                     doc_type: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        from psycopg.types.json import Json
        doc_id = str(uuid.uuid4())
        self._execute(
            """INSERT INTO documents
                   (id, project_id, user_id, title, source, doc_type, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (doc_id, project_id, user_id, title, source, doc_type,
             Json(metadata or {})),
        )
        return doc_id

    def add_chunk(self, document_id: str, chunk_index: int, content: str,
                  page: Optional[int] = None, section: Optional[str] = None,
                  embedding: Optional[List[float]] = None,
                  metadata: Optional[Dict[str, Any]] = None) -> str:
        from psycopg.types.json import Json
        chunk_id = str(uuid.uuid4())
        if embedding is not None and self._has_pgvector():
            self._execute(
                """INSERT INTO document_chunks
                       (id, document_id, chunk_index, content, page, section,
                        embedding, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s)""",
                (chunk_id, document_id, chunk_index, content, page, section,
                 _vec_literal(embedding), Json(metadata or {})),
            )
        else:
            self._execute(
                """INSERT INTO document_chunks
                       (id, document_id, chunk_index, content, page, section, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (chunk_id, document_id, chunk_index, content, page, section,
                 Json(metadata or {})),
            )
        return chunk_id

    def search_chunks_semantic(self, query_embedding: List[float],
                               project_id: Optional[str] = None,
                               limit: int = 5) -> List[Dict[str, Any]]:
        if not self._has_pgvector():
            return []
        join_sql, params = "", [_vec_literal(query_embedding)]
        if project_id:
            join_sql = "JOIN documents d ON d.id = c.document_id AND d.project_id = %s"
            params.append(project_id)
        params += [_vec_literal(query_embedding), limit]
        rows = self._execute(
            f"""SELECT c.id, c.content, c.page, c.section,
                       d.id, d.title, d.source,
                       1 - (c.embedding <=> %s::vector) AS score
                FROM document_chunks c {join_sql}
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> %s::vector LIMIT %s""",
            tuple(params),
        )
        return [{"chunkId": r[0], "content": r[1], "page": r[2],
                 "section": r[3], "documentId": r[4], "documentTitle": r[5],
                 "documentSource": r[6], "score": float(r[7])} for r in rows]

    def chunk_count(self, document_id: str) -> int:
        row = self._query_one(
            "SELECT count(*) FROM document_chunks WHERE document_id=%s",
            (document_id,))
        return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# Research + conversation operations (mixin, applied to Repository below)
# ---------------------------------------------------------------------------
from database.research_ops import ResearchOpsMixin  # noqa: E402

# Copy the mixin's methods onto Repository (plain __bases__ assignment is
# rejected on newer CPython builds; a method copy is equivalent here because
# the mixin is stateless and never overrides core Repository methods).
for _name, _value in vars(ResearchOpsMixin).items():
    if not _name.startswith("__"):
        setattr(Repository, _name, _value)
