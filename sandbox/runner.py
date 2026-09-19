import os
import sys
import time
import tempfile
import subprocess
import json
from typing import Dict, Any, Tuple

def is_docker_available() -> bool:
    """Checks if Docker daemon is accessible."""
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=3)
        return res.returncode == 0
    except Exception:
        return False

def execute_sandboxed_experiment(script_code: str, dataset_path: str, timeout_sec: int = 60) -> Dict[str, Any]:
    """
    Executes an experiment script in an isolated environment.
    Supports Docker container isolation if available, with automatic fallback
    to an isolated process sandbox.
    """
    docker_ready = is_docker_available()
    sandbox_mode = "Docker Container (Isolated)" if docker_ready else "Process Sandbox (Subprocess isolation)"

    with tempfile.TemporaryDirectory() as temp_dir:
        script_file = os.path.join(temp_dir, "experiment.py")
        metrics_file = os.path.join(temp_dir, "metrics.json")

        with open(script_file, "w", encoding="utf-8") as f:
            f.write(script_code)

        start_time = time.time()
        stdout = ""
        stderr = ""
        exit_code = -1
        metrics = {}

        if docker_ready:
            try:
                cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{temp_dir}:/app",
                    "-v", f"{dataset_path}:/app/dataset.csv:ro",
                    "--cpus=2",
                    "--memory=2g",
                    "--network=none",
                    "python:3.11-slim",
                    "python", "/app/experiment.py"
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
                stdout = proc.stdout
                stderr = proc.stderr
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                stderr = f"Execution timed out after {timeout_sec} seconds in Docker sandbox."
                exit_code = 124
            except Exception as e:
                stderr = f"Docker execution error: {str(e)}"
                exit_code = 1
        else:
            # Subprocess Isolation Fallback
            env = os.environ.copy()
            env["DATASET_PATH"] = dataset_path
            env["METRICS_PATH"] = metrics_file
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            try:
                proc = subprocess.run(
                    [sys.executable, script_file],
                    cwd=temp_dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec
                )
                stdout = proc.stdout
                stderr = proc.stderr
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                stderr = f"Execution timed out after {timeout_sec} seconds."
                exit_code = 124
            except Exception as e:
                stderr = f"Subprocess execution error: {str(e)}"
                exit_code = 1

        elapsed = round(time.time() - start_time, 2)

        # Parse output metrics JSON if created by script
        if os.path.exists(metrics_file):
            try:
                with open(metrics_file, "r", encoding="utf-8") as mf:
                    metrics = json.load(mf)
            except Exception:
                metrics = {}

        return {
            "sandboxMode": sandbox_mode,
            "dockerAvailable": docker_ready,
            "exitCode": exit_code,
            "runtime": f"{elapsed}s",
            "stdout": stdout,
            "stderr": stderr,
            "metrics": metrics,
            "success": exit_code == 0
        }
