"""Postgres (Neon) key-value backend for the research store.

The default store persists to a local JSON file. On Vercel's serverless
filesystem that file is ephemeral, so every cold instance starts empty and all
cross-session memory is lost. When ``DATABASE_URL`` is set, ``ResearchStore``
mirrors its state into a Postgres table instead, so conversational memory
(sessions + messages) and run state survive restarts and are shared across
instances.

Layout: one row per ``(namespace, key)``. Namespaces map 1:1 to the store's
top-level dicts (``projects``, ``sessions``, ...); ``key`` is the inner id
(project_id, session_id). The flat ``settings`` dict is stored under a reserved
key. Row-granular writes mean two instances updating different keys never
clobber each other, and a save only rewrites the row that changed.

Every method is called by ``ResearchStore`` from inside its own lock, so the
cached connection is used by one caller at a time. Any DB error is raised to the
caller, which logs it and falls back to the file backend — the app must never
crash just because the database is briefly unreachable.
"""
from typing import Any, Dict, List, Optional, Tuple

# Reserved row key for namespaces whose value is a single object (settings)
# rather than a dict-of-id -> object.
RESERVED_KEY = "_"

_DDL = """
CREATE TABLE IF NOT EXISTS kv_store (
    namespace   TEXT        NOT NULL,
    key         TEXT        NOT NULL,
    value       JSONB       NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (namespace, key)
)
"""

_UPSERT = """
INSERT INTO kv_store (namespace, key, value)
VALUES (%s, %s, %s)
ON CONFLICT (namespace, key)
DO UPDATE SET value = EXCLUDED.value, updated_at = now()
"""


def rows_from_data(data: Dict[str, Any]) -> List[Tuple[str, str, Any]]:
    """Flatten the store's dict-of-dicts into (namespace, key, value) rows."""
    rows: List[Tuple[str, str, Any]] = []
    for ns, val in data.items():
        if ns == "settings" or not isinstance(val, dict):
            rows.append((ns, RESERVED_KEY, val))
        else:
            for k, v in val.items():
                rows.append((ns, str(k), v))
    return rows


def data_from_rows(rows: List[Tuple[str, str, Any]], base: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild the store's dict-of-dicts from rows, on top of a default state."""
    data = base
    for ns, k, v in rows:
        if k == RESERVED_KEY:
            data[ns] = v
        else:
            data.setdefault(ns, {})[k] = v
    return data


class PostgresBackend:
    """Thin row-level KV wrapper over a single cached psycopg connection."""

    def __init__(self, url: str):
        self.url = url
        self._conn = None

    def _ready(self):
        import psycopg
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self.url, connect_timeout=10)
            self._conn.execute(_DDL)
            self._conn.commit()
        return self._conn

    def reset(self):
        """Drop the cached connection so the next call reconnects (e.g. after a
        serverless freeze closed the socket)."""
        try:
            if self._conn is not None and not self._conn.closed:
                self._conn.close()
        except Exception:
            pass
        self._conn = None

    def load_all(self, base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return the full store state from the DB, or None when the table is
        empty (first run — caller then starts from the default state)."""
        conn = self._ready()
        cur = conn.execute("SELECT namespace, key, value FROM kv_store")
        rows = [(r[0], r[1], r[2]) for r in cur.fetchall()]
        if not rows:
            return None
        return data_from_rows(rows, base)

    def get_row(self, namespace: str, key: str) -> Optional[Any]:
        conn = self._ready()
        cur = conn.execute(
            "SELECT value FROM kv_store WHERE namespace=%s AND key=%s",
            (namespace, key),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def save_row(self, namespace: str, key: str, value: Any) -> None:
        from psycopg.types.json import Json
        conn = self._ready()
        conn.execute(_UPSERT, (namespace, key, Json(value)))
        conn.commit()

    def save_all(self, data: Dict[str, Any]) -> None:
        from psycopg.types.json import Json
        conn = self._ready()
        rows = [(ns, k, Json(v)) for (ns, k, v) in rows_from_data(data)]
        with conn.cursor() as cur:
            cur.executemany(_UPSERT, rows)
        conn.commit()
