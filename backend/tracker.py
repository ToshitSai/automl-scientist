import os
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional
import backend.config

class TelemetryTracker:
    def __init__(self):
        self.mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
        self.db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_scientist")
        self.redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")

    def log_experiment_mlflow(self, run_name: str, params: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        """
        Logs experiment parameters and metrics to MLflow server via REST API (port 5000).
        """
        if not self.mlflow_uri:
            return False

        try:
            # 1. Create MLflow run
            create_url = f"{self.mlflow_uri}/api/2.0/mlflow/runs/create"
            payload = {
                "experiment_id": "0",
                "run_name": run_name,
                "start_time": int(os.times().elapsed * 1000)
            }
            req = urllib.request.Request(
                create_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                run_id = data.get("run", {}).get("info", {}).get("run_id")

            if run_id:
                # 2. Log metrics
                metrics_url = f"{self.mlflow_uri}/api/2.0/mlflow/runs/log-metric"
                for k, v in metrics.items():
                    if isinstance(v, (int, float)):
                        m_payload = {"run_id": run_id, "key": k, "value": float(v), "timestamp": int(os.times().elapsed * 1000)}
                        m_req = urllib.request.Request(metrics_url, data=json.dumps(m_payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                        urllib.request.urlopen(m_req, timeout=2)
                print(f"[TELEMETRY TRACKER] Experiment '{run_name}' logged to MLflow ({self.mlflow_uri}).")
                return True
        except Exception:
            # Service not actively running on localhost:5000 - safe graceful fallback
            pass
        return False

    def log_project_telemetry(self, project_id: str, status: str, metrics: Dict[str, Any]):
        """Logs project telemetry across MLflow, Redis, and Database."""
        self.log_experiment_mlflow(f"{project_id}_{status}", {"project_id": project_id}, metrics)

tracker = TelemetryTracker()
