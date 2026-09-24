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

class ResearchStore:
    def __init__(self, filepath: str = STORE_FILE):
        self.filepath = filepath
        # RLock: public mutators hold the lock while mutating AND saving; save()
        # re-acquires it (reentrant) instead of deadlocking.
        self.lock = threading.RLock()
        # Optional Postgres backend (Neon). When DATABASE_URL is set, state is
        # mirrored into a real DB so it survives Vercel's ephemeral filesystem
        # and is shared across instances. When unset (local dev, tests) the store
        # uses the JSON file exactly as before.
        self.backend = self._make_backend()
        self._load()

    @staticmethod
    def _make_backend():
        url = (os.environ.get("DATABASE_URL") or "").strip()
        if not url:
            return None
        try:
            from database.db import PostgresBackend
            return PostgresBackend(url)
        except Exception as e:
            print(f"[STORE DB INIT WARNING]: {e}")
            return None

    def _load(self):
        # DB is the source of truth when configured; fall back to the file on any
        # error or when the table is empty (first run).
        if self.backend is not None:
            try:
                data = self.backend.load_all(self._default_state())
                if data is not None:
                    self.data = data
                    return
            except Exception as e:
                print(f"[STORE DB LOAD WARNING]: {e}")
                self.backend.reset()
        self._load_file()

    def _load_file(self):
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

    def save(self, namespace: Optional[str] = None, key: Optional[str] = None):
        """Persist state.

        With a Postgres backend, writes go to the DB — a single row when
        ``namespace``/``key`` are given (the common, cheap path), otherwise every
        row. Any DB error drops the connection and falls back to the JSON file so
        a transient outage never loses the write silently or crashes the request.

        Without a backend, atomically rewrites the JSON file: write to a temp
        file, then os.replace(). (The old in-place open(path, 'w') truncated the
        store before writing; a crash mid-write left a corrupted file that
        _load() then silently replaced with an empty default state — total loss.)
        """
        with self.lock:
            if self.backend is not None:
                try:
                    if namespace is not None and key is not None:
                        self.backend.save_row(namespace, str(key), self.data[namespace][key])
                    else:
                        self.backend.save_all(self.data)
                    return
                except Exception as e:
                    print(f"[STORE DB SAVE WARNING]: {e}")
                    self.backend.reset()
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

    def get_settings(self) -> Dict[str, Any]:
        return self.data.get("settings", {})

    def update_settings(self, settings: Dict[str, Any]):
        self.data.setdefault("settings", {}).update(settings)
        self.save()

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
            self.data["projects"][project_id] = project
            self.save("projects", project_id)
        return project

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.data["projects"].get(project_id)

    def list_projects(self) -> List[Dict[str, Any]]:
        return list(self.data["projects"].values())

    def update_project(self, project_id: str, updates: Dict[str, Any]):
        with self.lock:
            if project_id in self.data["projects"]:
                self.data["projects"][project_id].update(updates)
                self.save("projects", project_id)

    def update_stage_state(self, project_id: str, stage: str, state: str):
        """Updates a specific stage state in the run state machine (NOT_STARTED, RUNNING, COMPLETED, FAILED, NOT_CONFIGURED)."""
        with self.lock:
            if project_id in self.data["projects"]:
                proj = self.data["projects"][project_id]
                proj.setdefault("stageStates", {})[stage] = state
                self.save("projects", project_id)

    def add_event(self, project_id: str, event_type: str, details: Optional[Dict[str, Any]] = None):
        """Emits a structured backend event."""
        import datetime
        with self.lock:
            if project_id in self.data["projects"]:
                evt = {
                    "type": event_type,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "details": details or {}
                }
                self.data["projects"][project_id].setdefault("events", []).append(evt)
                self.save("projects", project_id)

    def set_control_signal(self, project_id: str, signal: str):
        with self.lock:
            if project_id in self.data["projects"]:
                self.data["projects"][project_id]["controlSignal"] = signal
                if signal == "STOP":
                    self.data["projects"][project_id]["status"] = "STOPPED"
                elif signal == "PAUSE":
                    self.data["projects"][project_id]["status"] = "PAUSED"
                elif signal == "RUN" and self.data["projects"][project_id]["status"] in ["PAUSED", "STOPPED"]:
                    self.data["projects"][project_id]["status"] = "IN_PROGRESS"
                self.save("projects", project_id)

    def add_agent_log(self, project_id: str, agent_name: str, message: str, status: str = "IN_PROGRESS"):
        import datetime
        with self.lock:
            if project_id in self.data["projects"]:
                proj = self.data["projects"][project_id]
                proj["activeAgent"] = agent_name
                proj.setdefault("agentLogs", []).append({
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "agent": agent_name,
                    "message": message,
                    "status": status
                })
                self.save("projects", project_id)

    def save_dataset_report(self, project_id: str, report: Dict[str, Any]):
        with self.lock:
            self.data["datasets"][project_id] = report
            self.save("datasets", project_id)

    def get_dataset_report(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.data["datasets"].get(project_id)

    def save_baselines(self, project_id: str, baselines: List[Dict[str, Any]]):
        with self.lock:
            self.data["baselines"][project_id] = baselines
            self.save("baselines", project_id)

    def get_baselines(self, project_id: str) -> List[Dict[str, Any]]:
        return self.data["baselines"].get(project_id, [])

    def save_tree_nodes(self, project_id: str, nodes: List[Dict[str, Any]]):
        with self.lock:
            self.data["tree_nodes"][project_id] = nodes
            self.save("tree_nodes", project_id)

    def get_tree_nodes(self, project_id: str) -> List[Dict[str, Any]]:
        return self.data["tree_nodes"].get(project_id, [])

    def save_error_analysis(self, project_id: str, analysis: Dict[str, Any]):
        with self.lock:
            self.data["error_analyses"][project_id] = analysis
            self.save("error_analyses", project_id)

    def get_error_analysis(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.data["error_analyses"].get(project_id)

    def save_literature(self, project_id: str, papers: List[Dict[str, Any]]):
        with self.lock:
            self.data["literature"][project_id] = papers
            self.save("literature", project_id)

    def get_literature(self, project_id: str) -> List[Dict[str, Any]]:
        return self.data["literature"].get(project_id, [])

    def save_report(self, project_id: str, report_md: str):
        with self.lock:
            self.data["reports"][project_id] = report_md
            self.save("reports", project_id)

    def reconcile_stale_runs(self) -> List[str]:
        """Mark runs stuck in a non-terminal state as FAILED (startup reconciliation).

        Pipeline runs live in background threads of a single process. After a
        server restart no thread exists anymore, so any project still marked
        QUEUED / IN_PROGRESS / RUNNING is a ghost run: it can never progress and
        would block resume / duplicate-launch logic. Projects the user paused
        explicitly (PAUSED) are left untouched so their intent survives.
        """
        import datetime
        reconciled: List[str] = []
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.lock:
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

    def get_report(self, project_id: str) -> Optional[str]:
        return self.data["reports"].get(project_id)

    def get_session(self, session_id: str) -> Dict[str, Any]:
        sid = session_id or "default-session"
        with self.lock:
            # DB-fresh read: different turns of one conversation can land on
            # different serverless instances, so a warm in-memory copy may be
            # stale. Re-reading the single session row keeps memory consistent
            # across instances. Skipped entirely when no DB is configured.
            if self.backend is not None:
                try:
                    row = self.backend.get_row("sessions", sid)
                    if row is not None:
                        self.data.setdefault("sessions", {})[sid] = row
                except Exception as e:
                    print(f"[STORE DB SESSION READ WARNING]: {e}")
                    self.backend.reset()
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
            sess = self.get_session(sid)
            sess.update(updates)
            self.save("sessions", sid)

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

        Section 3: every message is stored separately with its own id, role,
        content, timestamp, intent, topic, research_id and pending_action so the
        full conversation can be reconstructed and audited.
        """
        import datetime
        import uuid
        sid = session_id or "default-session"
        with self.lock:
            sess = self.get_session(sid)
            history = sess.setdefault("messages", [])
            history.append({
                "id": str(uuid.uuid4()),
                "conversation_id": sid,
                "role": role,
                "content": content,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "intent": intent,
                "topic": topic,
                "research_id": research_id,
                "pending_action": pending_action,
            })
            if len(history) > max_history:
                del history[:len(history) - max_history]
            self.save("sessions", sid)

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        sess = self.get_session(session_id or "default-session")
        return sess.get("messages", [])

store = ResearchStore()

