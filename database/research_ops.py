"""Research + conversation SQL operations for the Repository.

Mixed into ``database.repository.Repository`` at import time (see the bottom of
repository.py). Payload collections (agent logs, events, tree nodes, baselines,
dataset reports, error analyses, literature views) live in a small
``project_payloads`` table — one JSONB row per (project, kind) — because the app
always reads/writes them whole per project. Structured, queryable data goes to
its typed tables instead: research_projects, papers, reports, messages,
conversation_context, research_events.

Field preservation rule (no data loss, migration §17): unknown/future keys of a
project payload land in ``research_projects.extra_json``; legacy session keys
land in ``conversation_context.metadata``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from database.repository import DEFAULT_USER_ID, _vec_literal

# Payload kinds stored in project_payloads.
PAYLOAD_KINDS = ("agent_logs", "events", "tree_nodes", "baselines",
                 "dataset_report", "error_analysis", "literature")

_PROJECT_ALLOWED_STATUS = ("QUEUED", "IN_PROGRESS", "RUNNING", "PAUSED",
                           "COMPLETED", "FAILED", "STOPPED")
_CONTROL_SIGNALS = ("RUN", "PAUSE", "STOP")

# Legacy camelCase project keys -> typed columns (hybrid schema §6).
_PROJECT_COLUMNS = {
    "name": "name",
    "objective": "objective",
    "researchQuestion": "research_question",
    "status": "status",
    "controlSignal": "control_signal",
    "datasetName": "dataset_name",
    "datasetPath": "dataset_path",
    "testPath": "test_path",
    "datasetId": "dataset_id",
    "datasetMeta": "dataset_meta",
    "llmProvider": "llm_provider",
    "engineState": "engine_state",
    "budgetMins": "budget_mins",
    "maxExperiments": "max_experiments",
    "experimentsCount": "experiments_count",
    "bestMetric": "best_metric",
    "bestModel": "best_model",
    "computeUsed": "compute_used",
    "activeAgent": "active_agent",
    "errorDetail": "error_detail",
    "stageStates": "stage_states",
}

# Columns written as JSONB (camelCase payload keys and their SQL columns).
_PROJECT_JSONB = {"datasetMeta", "stageStates"}
_PROJECT_JSONB_COLS = {"dataset_meta", "stage_states"}

# Keys that never persist (computed/stale/deprecated, exactly as the legacy
# reconcile + orchestrator semantics treat them).
_PROJECT_TRANSIENT = {"agentLogs", "events", "id", "createdAt", "updatedAt"}

# Unknown keys preserved verbatim in extra_json.
_PROJECT_KNOWN = set(_PROJECT_COLUMNS) | _PROJECT_TRANSIENT


def _status_value(value: Any, allowed, default: Any) -> Any:
    """Coerce a value to the CHECK-constraint domain (None passes through)."""
    if value is None:
        return None
    value = str(value)
    return value if value in allowed else default


def _clamp_int(value: Any, default: int = 5) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class ResearchOpsMixin:
    # ================================================================= projects
    def project_exists(self, project_id: str) -> bool:
        return self._query_one(
            "SELECT 1 FROM research_projects WHERE id=%s", (project_id,)) is not None

    def save_project(self, project_id: str, data: Dict[str, Any],
                     user_id: Optional[str] = None) -> None:
        """Insert or update a project from a legacy-shape dict.

        Partial ``data`` (orchestrator updates) performs a PATCH of the given
        keys only. Returns the stored dict-shape via ``get_project`` when needed.
        """
        from psycopg.types.json import Json
        uid = user_id or getattr(self, "default_user_id", None) or DEFAULT_USER_ID
        exists = self.project_exists(project_id)
        data = data or {}

        known: Dict[str, Any] = {}
        for camel, col in _PROJECT_COLUMNS.items():
            if camel not in data:
                continue
            value = data[camel]
            if camel == "status":
                value = _status_value(value, _PROJECT_ALLOWED_STATUS, "FAILED")
            elif camel == "controlSignal":
                value = _status_value(value, _CONTROL_SIGNALS, "RUN")
            elif camel in ("budgetMins",):
                value = int(value) if value is not None else None
            elif camel in ("maxExperiments", "experimentsCount"):
                value = _clamp_int(value, 5 if camel == "maxExperiments" else 0)
            if value is not None and camel in _PROJECT_JSONB:
                value = Json(value)
            known[col] = value
        extra = {k: v for k, v in data.items() if k not in _PROJECT_KNOWN}

        if not exists:
            self._execute(
                """INSERT INTO research_projects
                       (id, user_id, name, objective, created_at)
                   VALUES (%s, %s, %s, %s, COALESCE(%s::timestamptz, now()))""",
                (project_id, uid,
                 known.get("name") or (data.get("objective") or "Research")[:80],
                 data.get("objective") or known.get("name") or "Research objective",
                 data.get("createdAt")))
            known.pop("name", None)  # already set above; avoid overwriting

        sets: List[str] = []
        params: List[Any] = []
        for col, value in known.items():
            if value is None and not exists:
                continue  # let insert defaults stand
            if col in ("name", "objective") and exists:
                # name/objective only change when explicitly provided non-null
                if value is None:
                    continue
            if col in _PROJECT_JSONB_COLS:
                sets.append(f"{col} = COALESCE(%s::jsonb, {col})")
            else:
                sets.append(f"{col} = COALESCE(%s, {col})")
            params.append(value)
        if extra:
            sets.append("extra_json = extra_json || %s::jsonb")
            params.append(_dumps_extra(extra))
        if not sets:
            return
        params.append(project_id)
        self._execute(
            f"UPDATE research_projects SET {', '.join(sets)} WHERE id=%s",
            tuple(params))

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Return the legacy-shape project dict (agentLogs/events merged in)."""
        row = self._query_one(
            """SELECT id, user_id, name, objective, research_question, status,
                      control_signal, dataset_id, dataset_name, dataset_path,
                      test_path, dataset_meta, llm_provider, engine_state,
                      budget_mins, max_experiments, experiments_count,
                      best_metric, best_model, compute_used, active_agent,
                      error_detail, stage_states, extra_json, created_at, updated_at
               FROM research_projects WHERE id=%s""",
            (project_id,))
        if row is None:
            return None
        logs = self.get_agent_logs(project_id) or []
        events = self.list_project_events(project_id, limit=1000) or []
        extra = row[23] or {}
        project = {
            "id": row[0],
            "name": row[2],
            "objective": row[3],
            "researchQuestion": row[4],
            "status": row[5],
            "controlSignal": row[6],
            "datasetId": row[7],
            "datasetName": row[8],
            "datasetPath": row[9],
            "testPath": row[10],
            "datasetMeta": row[11],
            "llmProvider": row[12],
            "engineState": row[13],
            "budgetMins": row[14],
            "maxExperiments": row[15],
            "experimentsCount": row[16],
            "bestMetric": row[17],
            "bestModel": row[18],
            "computeUsed": row[19],
            "activeAgent": row[20],
            "errorDetail": row[21],
            "stageStates": row[22] or {},
            "agentLogs": logs,
            "events": events,
            "createdAt": self._iso(row[24]),
            "updatedAt": self._iso(row[25]),
        }
        project.update(extra)
        return project

    def list_projects(self, user_id: Optional[str] = None,
                      limit: int = 200) -> List[Dict[str, Any]]:
        where, params = "", [limit]
        if user_id:
            where = "WHERE user_id=%s"
            params = [user_id, limit]
        rows = self._execute(
            f"""SELECT id FROM research_projects {where}
                ORDER BY created_at DESC LIMIT %s""",
            tuple(params))
        projects = []
        for (pid,) in rows:
            project = self.get_project(pid)
            if project is not None:
                projects.append(project)
        return projects

    def delete_project(self, project_id: str) -> None:
        self._execute("DELETE FROM research_projects WHERE id=%s", (project_id,))

    # ================================================================= payloads
    def save_payload(self, project_id: str, kind: str, payload: Any) -> None:
        from psycopg.types.json import Json
        self._execute(
            """INSERT INTO project_payloads (project_id, kind, payload)
               VALUES (%s, %s, %s)
               ON CONFLICT (project_id, kind)
               DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()""",
            (project_id, kind, Json(payload)))

    def get_payload(self, project_id: str, kind: str,
                    default: Any = None) -> Any:
        row = self._query_one(
            "SELECT payload FROM project_payloads WHERE project_id=%s AND kind=%s",
            (project_id, kind))
        return row[0] if row else default

    def get_agent_logs(self, project_id: str) -> List[Dict[str, Any]]:
        return self.get_payload(project_id, "agent_logs", []) or []

    def append_agent_log(self, project_id: str, agent: str, message: str,
                         status: str = "IN_PROGRESS") -> None:
        logs = self.get_agent_logs(project_id)
        logs.append({
            "timestamp": self._utcnow_iso(),
            "agent": agent,
            "message": message,
            "status": status,
        })
        self.save_payload(project_id, "agent_logs", logs)
        self._execute(
            "UPDATE research_projects SET active_agent=%s WHERE id=%s",
            (agent, project_id))

    def append_project_event(self, project_id: str, event_type: str,
                             details: Optional[Dict[str, Any]] = None) -> None:
        """Write to the typed, append-only event log (queryable + auditable)."""
        from psycopg.types.json import Json
        self._execute(
            """INSERT INTO research_events (project_id, event_type, agent, message, details)
               VALUES (%s, %s, %s, %s, %s)""",
            (project_id, event_type, None, None, Json(details or {})))
        # Keep the legacy in-payload view in sync (frontend reads proj.events).
        events = self.get_payload(project_id, "events", []) or []
        events.append({
            "type": event_type,
            "timestamp": self._utcnow_iso(),
            "details": details or {},
        })
        self.save_payload(project_id, "events", events)

    def list_project_events(self, project_id: str,
                            limit: int = 200) -> List[Dict[str, Any]]:
        rows = self._execute(
            """SELECT event_type, agent, message, status, details, created_at
               FROM research_events WHERE project_id=%s
               ORDER BY created_at ASC LIMIT %s""",
            (project_id, limit))
        return [{
            "type": r[0], "agent": r[1], "message": r[2], "status": r[3],
            "details": r[4] or {}, "timestamp": self._iso(r[5]),
        } for r in rows]

    # ================================================== legacy collection getters
    def save_baselines(self, project_id: str, baselines: List[Dict[str, Any]]) -> None:
        self.save_payload(project_id, "baselines", baselines)

    def get_baselines(self, project_id: str) -> List[Dict[str, Any]]:
        return self.get_payload(project_id, "baselines", []) or []

    def save_tree_nodes(self, project_id: str, nodes: List[Dict[str, Any]]) -> None:
        self.save_payload(project_id, "tree_nodes", nodes)

    def get_tree_nodes(self, project_id: str) -> List[Dict[str, Any]]:
        return self.get_payload(project_id, "tree_nodes", []) or []

    def save_dataset_report(self, project_id: str, report: Dict[str, Any]) -> None:
        self.save_payload(project_id, "dataset_report", report)

    def get_dataset_report(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.get_payload(project_id, "dataset_report")

    def save_error_analysis(self, project_id: str, analysis: Dict[str, Any]) -> None:
        self.save_payload(project_id, "error_analysis", analysis)

    def get_error_analysis(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.get_payload(project_id, "error_analysis")

    def save_literature(self, project_id: str, papers: List[Dict[str, Any]]) -> None:
        """Store both the legacy literature view AND normalized papers rows."""
        from psycopg.types.json import Json
        self.save_payload(project_id, "literature", papers)
        for p in papers or []:
            if not isinstance(p, dict) or not p.get("title"):
                continue
            authors = p.get("authors") or []
            if isinstance(authors, str):
                authors = [a.strip() for a in authors.split(",") if a.strip()]
            try:
                year = int(p.get("year")) if p.get("year") is not None else None
            except (TypeError, ValueError):
                year = None
            self._execute(
                """INSERT INTO papers (title, authors, url, year, abstract, source_type, external_id, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (p["title"], Json(authors), p.get("url"), year,
                 p.get("abstract"), "SEMANTIC_SCHOLAR",
                 p.get("paperId"), Json({"relevance": p.get("relevance")})))

    def get_literature(self, project_id: str) -> List[Dict[str, Any]]:
        return self.get_payload(project_id, "literature", []) or []

    # ================================================================== reports
    def save_report(self, project_id: str, report_md: str,
                    title: Optional[str] = None) -> None:
        self._execute(
            """INSERT INTO reports (project_id, title, content_md, report_type, status)
               VALUES (%s, %s, %s, 'RESEARCH', 'FINAL')""",
            (project_id, title, report_md))

    def get_report(self, project_id: str) -> Optional[str]:
        row = self._query_one(
            """SELECT content_md FROM reports
               WHERE project_id=%s AND report_type='RESEARCH'
               ORDER BY created_at DESC LIMIT 1""",
            (project_id,))
        return row[0] if row else None

    # ============================================================ conversations
    def ensure_conversation(self, conversation_id: str,
                            user_id: Optional[str] = None) -> None:
        self._execute(
            """INSERT INTO conversations (id, user_id)
               VALUES (%s, %s)
               ON CONFLICT (id) DO NOTHING""",
            (conversation_id, user_id or getattr(self, "default_user_id", None)
             or DEFAULT_USER_ID))

    def list_conversations(self, user_id: Optional[str] = None,
                           limit: int = 100) -> List[Dict[str, Any]]:
        where, params = "", [limit]
        if user_id:
            where, params = "WHERE c.user_id=%s", [user_id, limit]
        rows = self._execute(
            f"""SELECT c.id, c.title, c.status, c.created_at, c.updated_at,
                       count(m.id) AS message_count
                FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id
                {where} GROUP BY c.id ORDER BY c.updated_at DESC LIMIT %s""",
            tuple(params))
        return [{"id": r[0], "title": r[1], "status": r[2],
                 "createdAt": self._iso(r[3]), "updatedAt": self._iso(r[4]),
                 "messageCount": int(r[5])} for r in rows]

    def record_message(self, conversation_id: str, role: str, content: str,
                       intent: Optional[str] = None, topic: Optional[str] = None,
                       research_id: Optional[str] = None,
                       pending_action: Optional[Dict[str, Any]] = None,
                       message_id: Optional[str] = None,
                       created_at: Optional[str] = None) -> Dict[str, Any]:
        """Insert one chat message. ``created_at`` (ISO) preserves original
        timestamps during migration; new messages default to now()."""
        from psycopg.types.json import Json
        import uuid as _uuid
        mid = message_id or str(_uuid.uuid4())
        self.ensure_conversation(conversation_id)
        self._execute(
            """INSERT INTO messages
                   (id, conversation_id, role, content, intent, topic, research_id, metadata, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                       COALESCE(%s::timestamptz, now()))
               ON CONFLICT (id) DO NOTHING""",
            (mid, conversation_id, role, content, intent, topic, research_id,
             Json({"pending_action": pending_action} if pending_action else {}),
             created_at))
        return {"id": mid, "conversation_id": conversation_id, "role": role,
                "content": content, "intent": intent, "topic": topic,
                "research_id": research_id,
                "pending_action": pending_action}

    def get_messages(self, conversation_id: str,
                     limit: int = 200) -> List[Dict[str, Any]]:
        rows = self._execute(
            """SELECT id, conversation_id, role, content, intent, topic,
                      research_id, metadata, created_at
               FROM messages WHERE conversation_id=%s
               ORDER BY created_at ASC, id ASC LIMIT %s""",
            (conversation_id, limit))
        messages = []
        for r in rows:
            metadata = r[7] or {}
            messages.append({
                "id": r[0],
                "conversation_id": r[1],
                "role": r[2],
                "content": r[3],
                "timestamp": self._iso(r[8]),
                "intent": r[4],
                "topic": r[5],
                "research_id": r[6],
                "pending_action": metadata.get("pending_action"),
            })
        return messages

    # ===================================================== conversation context
    _CONTEXT_COLUMNS = {
        "last_user_message": "last_user_message",
        "lastUserMessage": "last_user_message",
        "last_assistant_message": "last_assistant_message",
        "lastAssistantMessage": "last_assistant_message",
        "last_topic": "last_topic",
        "lastTopic": "last_topic",
        "last_reasoning_subjects": "last_reasoning_subjects",
        "recent_topics": "recent_topics",
        "recentTopics": "recent_topics",
        "pending_action": "pending_action",
        "active_project_id": "active_project_id",
        "activeProjectId": "active_project_id",
    }

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Legacy-shape session dict (defaults included; row created lazily)."""
        row = self._query_one(
            """SELECT last_user_message, last_assistant_message, last_topic,
                      last_reasoning_subjects, recent_topics, pending_action,
                      active_project_id, metadata
               FROM conversation_context WHERE conversation_id=%s""",
            (session_id,))
        if row is None:
            return {
                "session_id": session_id,
                "last_user_message": None,
                "last_assistant_message": None,
                "last_topic": None,
                "last_reasoning_subjects": [],
                "recent_topics": [],
                "pending_action": None,
                "active_project_id": None,
                "messages": [],
            }
        messages = self.get_messages(session_id)
        return {
            "session_id": session_id,
            "last_user_message": row[0],
            "last_assistant_message": row[1],
            "last_topic": row[2],
            "last_reasoning_subjects": row[3] or [],
            "recent_topics": row[4] or [],
            "pending_action": row[5],
            "active_project_id": row[6],
            "messages": messages,
            **(row[7] or {}),
        }

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        """PATCH the conversation_context row. 'messages' key is accepted and
        ignored (messages are their own table). Unknown keys -> metadata JSONB."""
        from psycopg.types.json import Json
        if not updates:
            return
        updates = dict(updates)
        updates.pop("messages", None)
        updates.pop("session_id", None)

        typed: Dict[str, Any] = {}
        extra: Dict[str, Any] = {}
        for key, value in updates.items():
            col = self._CONTEXT_COLUMNS.get(key)
            if col is None:
                extra[key] = value
            else:
                if col == "last_topic" and isinstance(value, str):
                    value = value.lower()
                typed[col] = value
        self.ensure_conversation(session_id)

        sets, params = [], []
        for col, value in typed.items():
            if col in ("last_reasoning_subjects", "recent_topics"):
                # NOT NULL JSONB list columns: None (absent in legacy sessions)
                # coerces to an empty list rather than a constraint violation.
                sets.append(f"{col} = %s::jsonb")
                params.append(Json(value if value is not None else []))
            elif col == "pending_action":
                sets.append("pending_action = %s::jsonb")
                params.append(Json(value) if value is not None else None)
            else:
                sets.append(f"{col} = %s")
                params.append(value)
        if extra:
            sets.append("metadata = metadata || %s::jsonb")
            params.append(Json(extra))
        if not sets:
            return
        # Ensure the row exists, then patch it (INSERT ... ON CONFLICT DO UPDATE
        # would skip the SET branch on first insert and silently lose values).
        self._execute(
            """INSERT INTO conversation_context (conversation_id)
               VALUES (%s) ON CONFLICT (conversation_id) DO NOTHING""",
            (session_id,))
        params.append(session_id)
        self._execute(
            f"UPDATE conversation_context SET {', '.join(sets)} WHERE conversation_id=%s",
            tuple(params))

    def set_pending_action(self, session_id: str, action_type: str,
                           topic: Optional[str] = None,
                           query: Optional[str] = None,
                           project_id: Optional[str] = None) -> None:
        self.update_session(session_id, {"pending_action": {
            "type": action_type, "topic": topic, "query": query,
            "projectId": project_id}})

    def clear_pending_action(self, session_id: str) -> None:
        self.update_session(session_id, {"pending_action": None})

    # ============================================================ reconciliation
    def reconcile_stale_runs(self) -> List[str]:
        """Mark non-terminal projects FAILED after a restart (legacy semantics:
        PAUSED projects keep their intent). Also records log + event rows."""
        now_iso = self._utcnow_iso()
        rows = self._execute(
            """SELECT id FROM research_projects
               WHERE status IN ('QUEUED', 'IN_PROGRESS', 'RUNNING')""")
        stale = [r[0] for r in rows]
        for pid in stale:
            self._execute(
                """UPDATE research_projects
                   SET status='FAILED',
                       error_detail = COALESCE(
                           error_detail,
                           'Research interrupted: the server restarted while the pipeline was running.')
                   WHERE id=%s""",
                (pid,))
            self.append_agent_log(
                pid, "RESEARCH_ORCHESTRATOR",
                "Server restart detected: the interrupted run was marked FAILED. "
                "Resume to relaunch the research pipeline.", "FAILED")
            self.append_project_event(pid, "research.interrupted", {})
        if stale:
            print(f"[REPO RECONCILE] marked {len(stale)} stale run(s) FAILED at {now_iso}")
        return stale

    # ================================================================ utilities
    @staticmethod
    def _utcnow_iso() -> str:
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    # ------------------------------------------------------------ counts/report
    def migration_counts(self) -> Dict[str, int]:
        """Row counts used by the JSON->Postgres migration verifier."""
        counts: Dict[str, int] = {}
        for label, sql in (
            ("projects", "SELECT count(*) FROM research_projects"),
            ("conversations", "SELECT count(*) FROM conversations"),
            ("messages", "SELECT count(*) FROM messages"),
            ("contexts", "SELECT count(*) FROM conversation_context"),
            ("papers", "SELECT count(*) FROM papers"),
            ("reports", "SELECT count(*) FROM reports"),
            ("events", "SELECT count(*) FROM research_events"),
            ("payloads", "SELECT count(*) FROM project_payloads"),
        ):
            row = self._query_one(sql)
            counts[label] = int(row[0]) if row else 0
        return counts


def _dumps_extra(extra: Dict[str, Any]) -> str:
    return __import__("json").dumps(extra, default=str)
