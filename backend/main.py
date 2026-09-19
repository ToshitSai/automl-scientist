import os
import shutil
import tempfile
import asyncio
import json
import traceback
import csv
import random
import sys
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from database.store import store

app = FastAPI(title="AutoML Scientist Engine API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_datasets_dir():
    local_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploaded_datasets")
    try:
        os.makedirs(local_dir, exist_ok=True)
        test_file = os.path.join(local_dir, ".writable_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return local_dir
    except Exception:
        tmp_dir = os.path.join(tempfile.gettempdir(), "automl_scientist_datasets")
        os.makedirs(tmp_dir, exist_ok=True)
        return tmp_dir

DATASETS_DIR = get_datasets_dir()

def _generate_auto_benchmark_dataset(path: str):
    """Generates a realistic credit card fraud detection benchmark dataset using pure Python stdlib."""
    import csv
    import random

    rng = random.Random(42)
    n_samples = 300
    n_fraud = 25

    rows = []
    headers = ['transaction_id', 'time_seconds', 'amount', 'v1', 'v2', 'v3', 'v4', 'is_fraud']

    # Non-fraud samples
    for i in range(n_samples - n_fraud):
        tx_id = f"tx_{i:04d}"
        t_sec = round(rng.uniform(0, 86400), 2)
        amt = round(rng.expovariate(1.0 / 50.0), 2)
        v1 = round(rng.gauss(0, 1), 4)
        v2 = round(rng.gauss(0, 1), 4)
        v3 = round(rng.gauss(0, 1), 4)
        v4 = round(rng.gauss(0, 1), 4)
        rows.append([tx_id, t_sec, amt, v1, v2, v3, v4, 0])

    # Fraud samples (distinct distributions)
    for i in range(n_fraud):
        tx_id = f"tx_{n_samples - n_fraud + i:04d}"
        t_sec = round(rng.choice([rng.uniform(0, 18000), rng.uniform(72000, 86400)]), 2)
        amt = round(rng.expovariate(1.0 / 300.0), 2)
        v1 = round(rng.gauss(-2.5, 1.5), 4)
        v2 = round(rng.gauss(2.0, 1.2), 4)
        v3 = round(rng.gauss(-3.0, 1.8), 4)
        v4 = round(rng.gauss(2.8, 1.1), 4)
        rows.append([tx_id, t_sec, amt, v1, v2, v3, v4, 1])

    rng.shuffle(rows)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def safe_docker_check() -> bool:
    try:
        from sandbox.runner import is_docker_available
        return is_docker_available()
    except Exception:
        return False

# Global Exception Handler to ensure ALL errors are returned as JSON
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = str(exc) or "An unexpected server error occurred."
    print(f"[API ERROR] {request.method} {request.url.path}: {error_msg}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": error_msg,
            "code": "INTERNAL_SERVER_ERROR",
            "path": request.url.path
        }
    )

@app.get("/api/health")
def health_check():
    """Health check endpoint for API dependencies."""
    llm_configured = bool(os.environ.get("OPENAI_API_KEY"))
    docker_ready = safe_docker_check()
    return {
        "status": "healthy",
        "api": True,
        "database": True,
        "llm": llm_configured,
        "docker": docker_ready
    }

@app.get("/api/config")
def config_status():
    """Returns system configuration status without exposing secrets."""
    return {
        "openai": {
            "configured": bool(os.environ.get("OPENAI_API_KEY"))
        },
        "database": {
            "configured": True,
            "type": "File-backed JSON Store"
        },
        "docker": {
            "available": safe_docker_check()
        }
    }

@app.get("/api/settings")
def get_settings():
    st = store.get_settings()
    docker_ready = safe_docker_check()
    st["dockerAvailable"] = docker_ready
    st["sandboxMode"] = "Docker Sandbox (Isolated Container)" if docker_ready else "Process Sandbox (Subprocess isolation)"
    return st

@app.post("/api/settings")
def update_settings(payload: dict):
    store.update_settings(payload)
    return {"status": "ok", "settings": store.get_settings()}

@app.get("/api/projects")
def list_projects():
    return store.list_projects()

@app.post("/api/research")
async def start_research(
    objective: str = Form(...),
    budget: int = Form(60),
    llm_provider: str = Form("Heuristic / Rule-based"),
    max_experiments: int = Form(5),
    file: Optional[UploadFile] = File(None)
):
    try:
        # Validate Research Objective
        obj_clean = objective.strip()
        meaningless_inputs = ["hi", "hello", "test", "demo", "run", "a", "asdf", "123", "hey", "testing", "objective"]
        if len(obj_clean) < 10 or obj_clean.lower() in meaningless_inputs:
            raise HTTPException(
                status_code=400,
                detail="Please enter a meaningful machine-learning research objective. (e.g. 'Improve fraud detection while increasing recall and controlling false positives.')"
            )

        import uuid
        project_id = f"proj-{uuid.uuid4().hex[:6]}"
        dataset_path = None
        dataset_name = "Not provided"

        if file and file.filename:
            dataset_name = file.filename
            ext = os.path.splitext(file.filename)[1]
            dataset_path = os.path.join(DATASETS_DIR, f"{project_id}{ext}")
            with open(dataset_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        else:
            dataset_name = "Auto: credit_card_fraud_benchmark.csv"
            dataset_path = os.path.join(DATASETS_DIR, f"{project_id}_auto.csv")
            _generate_auto_benchmark_dataset(dataset_path)

        project = store.create_project(
            project_id=project_id,
            name=f"Research: {objective[:35]}",
            objective=objective,
            dataset_name=dataset_name,
            budget=budget,
            provider=llm_provider,
            max_experiments=max_experiments
        )

        try:
            from agents.orchestrator import run_research_pipeline
            run_research_pipeline(project_id, dataset_path)
        except Exception as orchestrator_err:
            print(f"[ORCHESTRATOR LAUNCH ERROR]: {orchestrator_err}")
            store.add_agent_log(project_id, "RESEARCH_ORCHESTRATOR", f"Launch error: {orchestrator_err}", "FAILED")
            store.update_project(project_id, {"status": "FAILED", "errorDetail": str(orchestrator_err)})

        updated_project = store.get_project(project_id) or project

        return {"success": True, "status": updated_project.get("status", "COMPLETED"), "projectId": project_id, "project": updated_project}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[START RESEARCH ERROR]: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "code": "RESEARCH_START_FAILED"
            }
        )

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    proj = store.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj

@app.post("/api/projects/{project_id}/control")
def set_control_signal(project_id: str, payload: dict):
    signal = payload.get("signal", "RUN") # "STOP", "PAUSE", "RUN"
    store.set_control_signal(project_id, signal)
    return {"status": "ok", "project": store.get_project(project_id)}

@app.get("/api/projects/{project_id}/stream")
async def stream_project_events(project_id: str):
    """
    Server-Sent Events (SSE) streaming endpoint for live research telemetry.
    """
    async def event_generator():
        last_log_count = 0
        while True:
            proj = store.get_project(project_id)
            if not proj:
                yield f"data: {json.dumps({'error': 'Project not found'})}\n\n"
                break

            logs = proj.get("agentLogs", [])
            if len(logs) > last_log_count:
                new_logs = logs[last_log_count:]
                last_log_count = len(logs)
                event_payload = {
                    "projectId": project_id,
                    "status": proj.get("status"),
                    "activeAgent": proj.get("activeAgent"),
                    "stageStates": proj.get("stageStates"),
                    "researchQuestion": proj.get("researchQuestion"),
                    "experimentsCount": proj.get("experimentsCount"),
                    "bestMetric": proj.get("bestMetric"),
                    "computeUsed": proj.get("computeUsed"),
                    "newLogs": new_logs,
                    "events": proj.get("events", [])
                }
                yield f"data: {json.dumps(event_payload)}\n\n"

            if proj.get("status") in ["COMPLETED", "FAILED", "STOPPED"]:
                yield f"data: {json.dumps({'event': 'finished', 'status': proj.get('status')})}\n\n"
                break

            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/projects/{project_id}/dataset")
def get_dataset_report(project_id: str):
    report = store.get_dataset_report(project_id)
    if not report:
        return JSONResponse(status_code=200, content=None)
    return report

@app.get("/api/projects/{project_id}/baselines")
def get_baselines(project_id: str):
    return store.get_baselines(project_id)

@app.get("/api/projects/{project_id}/tree")
def get_tree_nodes(project_id: str):
    return store.get_tree_nodes(project_id)

@app.get("/api/projects/{project_id}/error-analysis")
def get_error_analysis(project_id: str):
    analysis = store.get_error_analysis(project_id)
    if not analysis:
        return JSONResponse(status_code=200, content=None)
    return analysis

@app.get("/api/projects/{project_id}/literature")
def get_literature(project_id: str):
    return store.get_literature(project_id)

@app.get("/api/projects/{project_id}/report")
def get_report(project_id: str):
    report = store.get_report(project_id)
    return {"report": report}

@app.get("/api/projects/{project_id}/report/download")
def download_report(project_id: str, fmt: str = Query("md")):
    proj = store.get_project(project_id)
    report_md = store.get_report(project_id) or "Report not generated yet."

    if fmt == "json":
        data = {
            "project": proj,
            "reportMarkdown": report_md,
            "dataset": store.get_dataset_report(project_id),
            "baselines": store.get_baselines(project_id),
            "tree": store.get_tree_nodes(project_id),
            "errorAnalysis": store.get_error_analysis(project_id)
        }
        return Response(content=json.dumps(data, indent=2), media_type="application/json", headers={"Content-Disposition": f"attachment; filename=Research_Report_{project_id}.json"})
    else:
        return Response(content=report_md, media_type="text/markdown", headers={"Content-Disposition": f"attachment; filename=Research_Report_{project_id}.md"})
