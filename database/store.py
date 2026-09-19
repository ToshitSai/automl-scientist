import os
import json
import threading
import tempfile
from typing import Dict, Any, List, Optional

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
        self.lock = threading.Lock()
        self._load()

    def _load(self):
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

    def save(self):
        with self.lock:
            try:
                os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
                with open(self.filepath, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                print(f"[STORE SAVE WARNING]: {e}")

    def get_settings(self) -> Dict[str, Any]:
        return self.data.get("settings", {})

    def update_settings(self, settings: Dict[str, Any]):
        self.data.setdefault("settings", {}).update(settings)
        self.save()

    def create_project(self, project_id: str, name: str, objective: str, dataset_name: str, budget: int, provider: str, max_experiments: int = 5) -> Dict[str, Any]:
        import datetime
        project = {
            "id": project_id,
            "name": name or objective[:40],
            "objective": objective,
            "researchQuestion": None,
            "datasetName": dataset_name or "Not selected",
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
        self.data["projects"][project_id] = project
        self.save()
        return project

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.data["projects"].get(project_id)

    def list_projects(self) -> List[Dict[str, Any]]:
        return list(self.data["projects"].values())

    def update_project(self, project_id: str, updates: Dict[str, Any]):
        if project_id in self.data["projects"]:
            self.data["projects"][project_id].update(updates)
            self.save()

    def update_stage_state(self, project_id: str, stage: str, state: str):
        """Updates a specific stage state in the run state machine (NOT_STARTED, RUNNING, COMPLETED, FAILED, NOT_CONFIGURED)."""
        if project_id in self.data["projects"]:
            proj = self.data["projects"][project_id]
            proj.setdefault("stageStates", {})[stage] = state
            self.save()

    def add_event(self, project_id: str, event_type: str, details: Optional[Dict[str, Any]] = None):
        """Emits a structured backend event."""
        import datetime
        if project_id in self.data["projects"]:
            evt = {
                "type": event_type,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "details": details or {}
            }
            self.data["projects"][project_id].setdefault("events", []).append(evt)
            self.save()

    def set_control_signal(self, project_id: str, signal: str):
        if project_id in self.data["projects"]:
            self.data["projects"][project_id]["controlSignal"] = signal
            if signal == "STOP":
                self.data["projects"][project_id]["status"] = "STOPPED"
            elif signal == "PAUSE":
                self.data["projects"][project_id]["status"] = "PAUSED"
            elif signal == "RUN" and self.data["projects"][project_id]["status"] in ["PAUSED", "STOPPED"]:
                self.data["projects"][project_id]["status"] = "IN_PROGRESS"
            self.save()

    def add_agent_log(self, project_id: str, agent_name: str, message: str, status: str = "IN_PROGRESS"):
        import datetime
        if project_id in self.data["projects"]:
            proj = self.data["projects"][project_id]
            proj["activeAgent"] = agent_name
            proj.setdefault("agentLogs", []).append({
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "agent": agent_name,
                "message": message,
                "status": status
            })
            self.save()

    def save_dataset_report(self, project_id: str, report: Dict[str, Any]):
        self.data["datasets"][project_id] = report
        self.save()

    def get_dataset_report(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.data["datasets"].get(project_id)

    def save_baselines(self, project_id: str, baselines: List[Dict[str, Any]]):
        self.data["baselines"][project_id] = baselines
        self.save()

    def get_baselines(self, project_id: str) -> List[Dict[str, Any]]:
        return self.data["baselines"].get(project_id, [])

    def save_tree_nodes(self, project_id: str, nodes: List[Dict[str, Any]]):
        self.data["tree_nodes"][project_id] = nodes
        self.save()

    def get_tree_nodes(self, project_id: str) -> List[Dict[str, Any]]:
        return self.data["tree_nodes"].get(project_id, [])

    def save_error_analysis(self, project_id: str, analysis: Dict[str, Any]):
        self.data["error_analyses"][project_id] = analysis
        self.save()

    def get_error_analysis(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.data["error_analyses"].get(project_id)

    def save_literature(self, project_id: str, papers: List[Dict[str, Any]]):
        self.data["literature"][project_id] = papers
        self.save()

    def get_literature(self, project_id: str) -> List[Dict[str, Any]]:
        return self.data["literature"].get(project_id, [])

    def save_report(self, project_id: str, report_md: str):
        self.data["reports"][project_id] = report_md
        self.save()

    def get_report(self, project_id: str) -> Optional[str]:
        return self.data["reports"].get(project_id)

    def get_session(self, session_id: str) -> Dict[str, Any]:
        sid = session_id or "default-session"
        sessions = self.data.setdefault("sessions", {})
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "last_user_message": None,
                "last_assistant_message": None,
                "last_topic": None,
                "pending_action": None,
                "active_project_id": None
            }
            self.save()
        return sessions[sid]

    def update_session(self, session_id: str, updates: Dict[str, Any]):
        sid = session_id or "default-session"
        sess = self.get_session(sid)
        sess.update(updates)
        self.save()

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
        self.update_session(session_id, {"pending_action": None})

store = ResearchStore()

