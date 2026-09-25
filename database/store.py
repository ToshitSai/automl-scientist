import os
import json
import threading
import tempfile
from typing import Dict, Any, List, Optional

# Ensure a local .env is loaded so DATABASE_URL is visible in dev too. On Vercel
# the value is a real environment variable and this is a no-op.
try:
    import backend.config  # noqa: F401
except Exception:
    pass


def get_default_store_path():
    local_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database")
    try:
        os.makedirs(local_dir, exist_ok=True)
        test_file = os.path.join(local_dir, ".writable_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return os.path.join(local_dir, "research_store.json")
    except Exception:
        tmp_dir = os.path.join(tempfile.gettempdir(), "automl_scientist")
        os.makedirs(tmp_dir, exist_ok=True)
        return os.path.join(tmp_dir, "research_store.json")

STORE_FILE = get_default_store_path()

# When False, DATABASE_URL is ignored and the JSON file is used even if present
# (used by the hermetic unit-test suite and for local offline development).
DB_DISABLED = os.environ.get("STORE_DB_DISABLED", "").strip() in ("1", "true", "True")


class ResearchStore:
    """Facade over the persistent data layer.

    Two backends, chosen once at construction:

      * Postgres repository (default when DATABASE_URL is set and not disabled).
        Source of truth: PostgreSQL with a typed relational schema + pgvector.
      * JSON file (fallback, and always used when DATABASE_URL is unset).
        Legacy path, kept so the app degrades gracefully — offline dev, hermetic
        tests, and outages never crash a request.

    The public method set is unchanged from the original file-backed store, so
    backend routes, the orchestrator and tests keep working unchanged.
    """

    def __init__(self, filepath: str = STORE_FILE):
        self.filepath = filepath
        # RLock: public mutators hold the lock while mutating AND saving; save()
        # re-acquires it (reentrant) instead of deadlocking.
        self.lock = threading.RLock()
        self.repo = self._make_repo()
        self.backend = self.repo  # legacy attribute: tests may disable this
        self._db_healthy = self.repo is not None
        self._load()

    @staticmethod
    def _make_repo():
        if DB_DISABLED:
            return None
        url = (os.environ.get("DATABASE_URL") or "").strip()
        if not url:
            return None
        try:
            from database.repository import Repository
            repo = Repository(url)
            repo.ensure_schema()
            repo.ensure_system_user()
            return repo
        except Exception as e:
            print(f"[STORE DB INIT WARNING]: {e}")
            return None

    # --------------------------------------------------------------- loading
    def _load(self):
        if self.repo is not None:
            try:
                self.repo.reconcile_stale_runs()
            except Exception as e:
                print(f"[STORE DB RECONCILE WARNING]: {e}")
                self._db_healthy = False
        self._load_file()

    def _load_file(self):
        """Load the JSON file into self.data (warm cache + fallback path)."""
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            if os.path.exists(self.filepath):
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            else:
                self.data = self._default_state()
        except Exception:
            self.data = self._default_state()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "projects": {},
            "datasets": {},
            "baselines": {},
            "experiments": {},
            "tree_nodes": {},
            "error_analyses": {},
            "literature": {},
            "reports": {},
            "sessions": {},
            "settings": {
                "llmProvider": "Not configured",
                "apiKeySet": False,
                "sandboxMode": "Process Sandbox (Subprocess isolation)",
                "dockerAvailable": False,
                "maxExperiments": 5,
                "timeBudgetMins": 60
            }
        }

    # --------------------------------------------------------------- writing
    def save(self, namespace: Optional[str] = None, key: Optional[str] = None):
        """Persist state. Postgres writes happen inside each mutator (one row /
        one upsert); with the file backend — or after a DB failure degraded to
        the file — this atomically rewrites the JSON."""
        with self.lock:
            if self.repo is None or not self._db_healthy:
                self._save_file()

    def _save_file(self):
        with self.lock:
            try:
                dir_name = os.path.dirname(self.filepath) or "."
                os.makedirs(dir_name, exist_ok=True)
                fd, tmp_path = tempfile.mkstemp(prefix=".research_store_", suffix=".tmp", dir=dir_name)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(self.data, f, indent=2)
                    os.replace(tmp_path, self.filepath)
                except BaseException:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                    raise
            except Exception as e:
                print(f"[STORE SAVE WARNING]: {e}")

    # -------------------------------------------------------------- settings
    def get_settings(self) -> Dict[str, Any]:
        if self.repo is not None and self._db_healthy:
            try:
                return self.repo.get_all_settings()
            except Exception as e:
                print(f"[STORE DB WARNING]: {e}")
                self._db_healthy = False
        return self.data.get("settings", {})

    def update_settings(self, settings: Dict[str, Any]):
        with self.lock:
            self.data.setdefault("settings", {}).update(settings)
            if self.repo is not None and self._db_healthy:
                try:
                    self.repo.set_settings(settings)
                except Exception as e:
                    print(f"[STORE DB WARNING]: {e}")
                    self._db_healthy = False
            self.save()

    # -------------------------------------------------------------- projects
    def create_project(self, project_id: str, name: str, objective: str, dataset_name: str, budget: int, provider: str,
                       max_experiments: int = 5, dataset_path: Optional[str] = None, test_path: Optional[str] = None,
                       dataset_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        import datetime
        project = {
            "id": project_id,
            "name": name or objective[:40],
            "objective": objective,
            "researchQuestion": None,
            "datasetName": dataset_name or "Not selected",
            # Persisted launch context so an interrupted run can be relaunched
            # (resume) after a server restart without re-uploading the dataset.
            "datasetPath": dataset_path,
            "testPath": test_path,
            "datasetMeta": dataset_meta,
            "status": "QUEUED",
            "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "experimentsCount": 0,
            "maxExperiments": max_experiments,
            "bestMetric": "N/A",
            "bestModel": "Not trained",
            "llmProvider": provider or "HEURISTIC FALLBACK",
            "engineState": "LLM AUTONOMOUS" if (provider and "OpenAI" in provider) else "HEURISTIC FALLBACK",
            "budgetMins": budget,
            "computeUsed": f"0.0 mins / {budget} mins",
            "activeAgent": "INITIALIZING",
            "agentLogs": [],
            "events": [],
            "controlSignal": "RUN", # "RUN", "PAUSE", "STOP"
            "stageStates": {
                "research_question": "NOT_STARTED",
                "dataset_eda": "NOT_STARTED",
                "literature_search": "NOT_STARTED",
                "baseline_training": "NOT_STARTED",
                "hypothesis_generation": "NOT_STARTED",
                "sandboxed_execution": "NOT_STARTED",
                "error_diagnostics": "NOT_STARTED",
                "research_report": "NOT_STARTED"
            }
        }
        with self.lock:
            self.data.setdefault("projects", {})[project_id] = project
            self._db_write(
                lambda: self.repo.save_project(project_id, project),
                file_fallback=lambda: self.save("projects", project_id))
        return project

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        if self.repo is not None and self._db_healthy:
            try:
                project = self.repo.get_project(project_id)
                if project is not None:
                    with self.lock:
                        self.data.setdefault("projects", {})[project_id] = project
                    return project
                return None
            except Exception as e:
                print(f"[STORE DB WARNING]: {e}")
                self._db_healthy = False
        return self.data.get("projects", {}).get(project_id)

    def list_projects(self) -> List[Dict[str, Any]]:
        if self.repo is not None and self._db_healthy:
            try:
                projects = self.repo.list_projects()
                with self.lock:
                    self.data["projects"] = {p["id"]: p for p in projects}
                return projects
            except Exception as e:
                print(f"[STORE DB WARNING]: {e}")
                self._db_healthy = False
        return list(self.data.get("projects", {}).values())

    def update_project(self, project_id: str, updates: Dict[str, Any]):
        with self.lock:
            if self.repo is not None and self._db_healthy:
                # PATCH in Postgres without requiring the local cache.
                self._db_write(
                    lambda: self.repo.save_project(project_id, updates),
                    file_fallback=lambda: self._update_project_file(project_id, updates))
                # Keep the warm cache coherent for fallback reads.
                cached = self.data.get("projects", {}).get(project_id)
                if cached is not None:
                    cached.update(updates)
                return
            self._update_project_file(project_id, updates)
            self.save("projects", project_id)

    def _update_project_file(self, project_id: str, updates: Dict[str, Any]):
        if project_id in self.data.get("projects", {}):
            self.data["projects"][project_id].update(updates)

    def update_stage_state(self, project_id: str, stage: str, state: str):
        """Updates a specific stage state in the run state machine (NOT_STARTED, RUNNING, COMPLETED, FAILED, NOT_CONFIGURED)."""
        with self.lock:
            if self.repo is not None and self._db_healthy:
                def _db():
                    current = (self.repo.get_project(project_id) or {}).get("stageStates") or {}
                    current[stage] = state
                    self.repo.save_project(project_id, {"stageStates": current})
                self._db_write(_db,
                               file_fallback=lambda: self._update_stage_state_file(project_id, stage, state))
                cached = self.data.get("projects", {}).get(project_id)
                if cached is not None:
                    cached.setdefault("stageStates", {})[stage] = state
                return
            self._update_stage_state_file(project_id, stage, state)
            self.save("projects", project_id)

    def _update_stage_state_file(self, project_id: str, stage: str, state: str):
        if project_id in self.data.get("projects", {}):
            proj = self.data["projects"][project_id]
            proj.setdefault("stageStates", {})[stage] = state

    def add_event(self, project_id: str, event_type: str, details: Optional[Dict[str, Any]] = None):
        """Emits a structured backend event."""
        with self.lock:
            if self.repo is not None and self._db_healthy:
                self._db_write(
                    lambda: self.repo.append_project_event(project_id, event_type, details),
                    file_fallback=lambda: self._add_event_file(project_id, event_type, details))
                cached = self.data.get("projects", {}).get(project_id)
                if cached is not None:
                    import datetime
                    cached.setdefault("events", []).append({
                        "type": event_type,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "details": details or {}
                    })
                return
            self._add_event_file(project_id, event_type, details)
            self.save("projects", project_id)

    def _add_event_file(self, project_id: str, event_type: str, details: Optional[Dict[str, Any]]):
        import datetime
        if project_id in self.data.get("projects", {}):
            evt = {
                "type": event_type,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "details": details or {}
            }
            self.data["projects"][project_id].setdefault("events", []).append(evt)

    def set_control_signal(self, project_id: str, signal: str):
        updates: Dict[str, Any] = {"controlSignal": signal}
        if signal == "STOP":
            updates["status"] = "STOPPED"
        elif signal == "PAUSE":
            updates["status"] = "PAUSED"
        elif signal == "RUN":
            current = self.get_project(project_id) or {}
            if current.get("status") in ("PAUSED", "STOPPED"):
                updates["status"] = "IN_PROGRESS"
        self.update_project(project_id, updates)

    def add_agent_log(self, project_id: str, agent_name: str, message: str, status: str = "IN_PROGRESS"):
        with self.lock:
            if self.repo is not None and self._db_healthy:
                self._db_write(
                    lambda: self.repo.append_agent_log(project_id, agent_name, message, status),
                    file_fallback=lambda: self._add_agent_log_file(project_id, agent_name, message, status))
                cached = self.data.get("projects", {}).get(project_id)
                if cached is not None:
                    import datetime
                    cached["activeAgent"] = agent_name
                    cached.setdefault("agentLogs", []).append({
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "agent": agent_name,
                        "message": message,
                        "status": status
                    })
                return
            self._add_agent_log_file(project_id, agent_name, message, status)
            self.save("projects", project_id)

    def _add_agent_log_file(self, project_id: str, agent_name: str, message: str, status: str):
        import datetime
        if project_id in self.data.get("projects", {}):
            proj = self.data["projects"][project_id]
            proj["activeAgent"] = agent_name
            proj.setdefault("agentLogs", []).append({
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "agent": agent_name,
                "message": message,
                "status": status
            })

    # ----------------------------------------------------- per-project payloads
    def save_dataset_report(self, project_id: str, report: Dict[str, Any]):
        with self.lock:
            self.data.setdefault("datasets", {})[project_id] = report
            self._db_write(
                lambda: self.repo.save_dataset_report(project_id, report),
                file_fallback=lambda: self.save("datasets", project_id))

    def get_dataset_report(self, project_id: str) -> Optional[Dict[str, Any]]:
        if self.repo is not None and self._db_healthy:
            try:
                return self.repo.get_dataset_report(project_id)
            except Exception as e:
                print(f"[STORE DB WARNING]: {e}")
                self._db_healthy = False
        return self.data.get("datasets", {}).get(project_id)

    def save_baselines(self, project_id: str, baselines: List[Dict[str, Any]]):
        with self.lock:
            self.data.setdefault("baselines", {})[project_id] = baselines
            self._db_write(
                lambda: self.repo.save_baselines(project_id, baselines),
                file_fallback=lambda: self.save("baselines", project_id))

    def get_baselines(self, project_id: str) -> List[Dict[str, Any]]:
        if self.repo is not None and self._db_healthy:
            try:
                return self.repo.get_baselines(project_id)
            except Exception as e:
                print(f"[STORE DB WARNING]: {e}")
                self._db_healthy = False
        return self.data.get("baselines", {}).get(project_id, [])

    def save_tree_nodes(self, project_id: str, nodes: List[Dict[str, Any]]):
        with self.lock:
            self.data.setdefault("tree_nodes", {})[project_id] = nodes
            self._db_write(
                lambda: self.repo.save_tree_nodes(project_id, nodes),
                file_fallback=lambda: self.save("tree_nodes", project_id))

    def get_tree_nodes(self, project_id: str) -> List[Dict[str, Any]]:
        if self.repo is not None and self._db_healthy:
            try:
                return self.repo.get_tree_nodes(project_id)
            except Exception as e:
                print(f"[STORE DB WARNING]: {e}")
                self._db_healthy = False
        return self.data.get("tree_nodes", {}).get(project_id, [])

    def save_error_analysis(self, project_id: str, analysis: Dict[str, Any]):
        with self.lock:
            self.data.setdefault("error_analyses", {})[project_id] = analysis
            self._db_write(
                lambda: self.repo.save_error_analysis(project_id, analysis),
                file_fallback=lambda: self.save("error_analyses", project_id))

    def get_error_analysis(self, project_id: str) -> Optional[Dict[str, Any]]:
        if self.repo is not None and self._db_healthy:
            try:
                return self.repo.get_error_analysis(project_id)
            except Exception as e:
                print(f"[STORE DB WARNING]: {e}")
                self._db_healthy = False
        return self.data.get("error_analyses", {}).get(project_id)

    def save_literature(self, project_id: str, papers: List[Dict[str, Any]]):
        with self.lock:
            self.data.setdefault("literature", {})[project_id] = papers
            self._db_write(
                lambda: self.repo.save_literature(project_id, papers),
                file_fallback=lambda: self.save("literature", project_id))

    def get_literature(self, project_id: str) -> List[Dict[str, Any]]:
        if self.repo is not None and self._db_healthy:
            try:
                return self.repo.get_literature(project_id)
            except Exception as e:
                print(f"[STORE DB WARNING]: {e}")
                self._db_healthy = False
        return self.data.get("literature", {}).get(project_id, [])

    def save_report(self, project_id: str, report_md: str):
        with self.lock:
            self.data.setdefault("reports", {})[project_id] = report_md
            self._db_write(
                lambda: self.repo.save_report(project_id, report_md),
                file_fallback=lambda: self.save("reports", project_id))

    def get_report(self, project_id: str) -> Optional[str]:
        if self.repo is not None and self._db_healthy:
            try:
                report = self.repo.get_report(project_id)
                if report is not None:
                    with self.lock:
                        self.data.setdefault("reports", {})[project_id] = report
                    return report
                return None
            except Exception as e:
                print(f"[STORE DB WARNING]: {e}")
                self._db_healthy = False
        return self.data.get("reports", {}).get(project_id)

    # ------------------------------------------------------------- sessions
    def get_session(self, session_id: str) -> Dict[str, Any]:
        sid = session_id or "default-session"
        if self.repo is not None and self._db_healthy:
            try:
                session = self.repo.get_session(sid)
                with self.lock:
                    self.data.setdefault("sessions", {})[sid] = session
                return session
            except Exception as e:
                print(f"[STORE DB WARNING]: {e}")
                self._db_healthy = False
        with self.lock:
            sessions = self.data.setdefault("sessions", {})
            if sid not in sessions:
                sessions[sid] = {
                    "session_id": sid,
                    "last_user_message": None,
                    "last_assistant_message": None,
                    "last_topic": None,
                    "pending_action": None,
                    "active_project_id": None,
                    "messages": []
                }
                self.save("sessions", sid)
            return sessions[sid]

    def update_session(self, session_id: str, updates: Dict[str, Any]):
        sid = session_id or "default-session"
        with self.lock:
            if self.repo is not None and self._db_healthy:
                self._db_write(
                    lambda: self.repo.update_session(sid, updates),
                    file_fallback=lambda: self._update_session_file(sid, updates))
                cached = self.data.setdefault("sessions", {}).get(sid)
                if cached is not None:
                    cached.update(updates)
                return
            self._update_session_file(sid, updates)
            self.save("sessions", sid)

    def _update_session_file(self, session_id: str, updates: Dict[str, Any]):
        sessions = self.data.setdefault("sessions", {})
        if session_id not in sessions:
            sessions[session_id] = {
                "session_id": session_id,
                "last_user_message": None,
                "last_assistant_message": None,
                "last_topic": None,
                "pending_action": None,
                "active_project_id": None,
                "messages": []
            }
        sessions[session_id].update(updates)

    def set_pending_action(self, session_id: str, action_type: str, topic: Optional[str] = None, query: Optional[str] = None, project_id: Optional[str] = None):
        self.update_session(session_id, {
            "pending_action": {
                "type": action_type,
                "topic": topic,
                "query": query,
                "projectId": project_id
            }
        })

    def clear_pending_action(self, session_id: str):
        self.update_session(session_id or "default-session", {"pending_action": None})

    def record_message(self, session_id: str, role: str, content: str,
                       intent: Optional[str] = None, topic: Optional[str] = None,
                       research_id: Optional[str] = None,
                       pending_action: Optional[Dict[str, Any]] = None,
                       max_history: int = 200):
        """Append a single conversational message to the session history.

        Stored as its own row (id, role, content, timestamp, intent, topic,
        research_id, pending_action) so the full conversation can be
        reconstructed and audited.
        """
        import datetime
        import uuid
        sid = session_id or "default-session"
        msg = {
            "id": str(uuid.uuid4()),
            "conversation_id": sid,
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "intent": intent,
            "topic": topic,
            "research_id": research_id,
            "pending_action": pending_action,
        }
        with self.lock:
            if self.repo is not None and self._db_healthy:
                self._db_write(
                    lambda: self.repo.record_message(
                        sid, role, content, intent=intent, topic=topic,
                        research_id=research_id, pending_action=pending_action,
                        message_id=msg["id"]),
                    file_fallback=lambda: self._record_message_file(msg, max_history))
                cached = self.data.setdefault("sessions", {}).get(sid)
                if cached is not None:
                    history = cached.setdefault("messages", [])
                    history.append(msg)
                    if len(history) > max_history:
                        del history[:len(history) - max_history]
                return
            self._record_message_file(msg, max_history)
            self.save("sessions", sid)

    def _record_message_file(self, msg: Dict[str, Any], max_history: int):
        sid = msg["conversation_id"]
        sess = self.get_session(sid)
        history = sess.setdefault("messages", [])
        history.append(msg)
        if len(history) > max_history:
            del history[:len(history) - max_history]

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        sid = session_id or "default-session"
        if self.repo is not None and self._db_healthy:
            try:
                messages = self.repo.get_messages(sid)
                with self.lock:
                    cached = self.data.setdefault("sessions", {}).setdefault(sid, {"messages": []})
                    cached["messages"] = messages
                return messages
            except Exception as e:
                print(f"[STORE DB WARNING]: {e}")
                self._db_healthy = False
        sess = self.get_session(sid)
        return sess.get("messages", [])

    def reconcile_stale_runs(self) -> List[str]:
        """Mark runs stuck in a non-terminal state as FAILED (startup reconciliation).

        Pipeline runs live in background threads of a single process. After a
        server restart no thread exists anymore, so any project still marked
        QUEUED / IN_PROGRESS / RUNNING is a ghost run: it can never progress and
        would block resume / duplicate-launch logic. Projects the user paused
        explicitly (PAUSED) are left untouched so their intent survives.
        """
        with self.lock:
            if self.repo is not None and self._db_healthy:
                try:
                    return self.repo.reconcile_stale_runs()
                except Exception as e:
                    print(f"[STORE DB WARNING]: {e}")
                    self._db_healthy = False
            # File-backend reconciliation (legacy in-memory path).
            import datetime
            reconciled: List[str] = []
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            for pid, proj in self.data.get("projects", {}).items():
                if proj.get("status") in ("QUEUED", "IN_PROGRESS", "RUNNING"):
                    proj["status"] = "FAILED"
                    proj["errorDetail"] = "Research interrupted: the server restarted while the pipeline was running."
                    proj.setdefault("agentLogs", []).append({
                        "timestamp": now,
                        "agent": "RESEARCH_ORCHESTRATOR",
                        "message": "Server restart detected: the interrupted run was marked FAILED. Resume to relaunch the research pipeline.",
                        "status": "FAILED",
                    })
                    proj.setdefault("events", []).append({
                        "type": "research.interrupted",
                        "timestamp": now,
                        "details": {},
                    })
                    reconciled.append(pid)
            if reconciled:
                self.save()
            return reconciled

    # ------------------------------------------------------------ DB plumbing
    def _db_write(self, db_fn, file_fallback):
        """Run a Postgres write; on failure degrade to the file backend once."""
        try:
            db_fn()
        except Exception as e:
            print(f"[STORE DB WARNING]: {e}")
            self._db_healthy = False
            try:
                file_fallback()
            except Exception as fe:
                print(f"[STORE SAVE WARNING]: {fe}")

    def using_postgres(self) -> bool:
        """True when the Postgres repository is active and healthy."""
        return self.repo is not None and self._db_healthy

store = ResearchStore()
