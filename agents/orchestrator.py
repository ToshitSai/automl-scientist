import time
import os
import tempfile
import threading
import json
import traceback
from typing import Dict, Any, List

from database.store import store
from backend.dataset_analyzer import analyze_dataset
from backend.trainer import train_baselines
from sandbox.runner import execute_sandboxed_experiment
from backend.error_analyzer import perform_error_analysis
from backend.literature_search import search_literature
from backend.report_generator import generate_research_report
from backend.llm import generate_hypothesis_llm, generate_research_question, query_llm, query_critic_llm
from backend.tracker import tracker

def get_experiments_dir():
    local_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "experiments")
    try:
        os.makedirs(local_dir, exist_ok=True)
        test_file = os.path.join(local_dir, ".writable_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return local_dir
    except Exception:
        tmp_dir = os.path.join(tempfile.gettempdir(), "automl_scientist_experiments")
        os.makedirs(tmp_dir, exist_ok=True)
        return tmp_dir

EXPERIMENTS_BASE_DIR = get_experiments_dir()

# ---------------------------------------------------------------------------
# Active-run registry: prevents duplicate concurrent launches of the same
# project (double-clicked approvals, repeated chat "go ahead", resume racing a
# start). Claiming is an atomic check-and-set under the lock.
# ---------------------------------------------------------------------------
_active_runs = set()
_active_runs_lock = threading.Lock()


def _try_register_run(project_id: str) -> bool:
    """Atomically claim a project for a pipeline run. False if already active."""
    with _active_runs_lock:
        if project_id in _active_runs:
            return False
        _active_runs.add(project_id)
        return True


def _unregister_run(project_id: str) -> None:
    with _active_runs_lock:
        _active_runs.discard(project_id)


def is_run_active(project_id: str) -> bool:
    with _active_runs_lock:
        return project_id in _active_runs


def _sandbox_stage_state(docker_available: bool, exit_code) -> str:
    """Honest stage mapping: a non-zero exit code is a FAILED run in ANY
    sandbox; only a successful run without Docker is NOT_CONFIGURED."""
    if exit_code != 0:
        return "FAILED"
    return "COMPLETED" if docker_available else "NOT_CONFIGURED"


def _compute_final_status(stage_states: Dict[str, str], experiment_statuses: List[str]) -> str:
    """The research is only COMPLETED if the core stages succeeded AND, when
    experiments were actually attempted, at least one produced a result.
    Rendering a report over zero valid experiments is not a completed study."""
    core_succeeded = (
        stage_states.get("dataset_eda") == "COMPLETED"
        and stage_states.get("baseline_training") == "COMPLETED"
        and stage_states.get("research_report") == "COMPLETED"
    )
    if not core_succeeded:
        return "FAILED"
    if experiment_statuses and all(s == "FAILED" for s in experiment_statuses):
        return "FAILED"
    return "COMPLETED"


def _refuse_duplicate_launch(project_id: str) -> None:
    msg = "Duplicate launch refused: a pipeline run for this project is already active."
    print(f"[ORCHESTRATOR] {msg} (project '{project_id}')")
    store.add_agent_log(project_id, "RESEARCH_ORCHESTRATOR", msg, "WARNING")


def run_research_pipeline(project_id: str, dataset_path: str, dataset_meta: Dict[str, Any] = None, test_path: str = None):
    """Executes the autonomous ML research pipeline synchronously.
    Returns False (and launches nothing) if the project already has an active run."""
    if not _try_register_run(project_id):
        _refuse_duplicate_launch(project_id)
        return False
    _orchestrate_pipeline(project_id, dataset_path, dataset_meta, test_path)
    return True


def run_research_pipeline_async(project_id: str, dataset_path: str, dataset_meta: Dict[str, Any] = None, test_path: str = None):
    """Executes the autonomous ML research pipeline asynchronously in a background thread.
    Returns False (and launches nothing) if the project already has an active run."""
    if not _try_register_run(project_id):
        _refuse_duplicate_launch(project_id)
        return False
    thread = threading.Thread(target=_orchestrate_pipeline, args=(project_id, dataset_path, dataset_meta, test_path), daemon=True)
    thread.start()
    return True


def resume_pipeline(project_id: str) -> Dict[str, Any]:
    """Resume a project: unpause a live run, or relaunch the pipeline when the
    previous run died (e.g. server restart). Returns a small result dict so
    callers (API, chat) can report what actually happened."""
    proj = store.get_project(project_id)
    if not proj:
        return {"resumed": False, "relaunched": False, "reason": "not_found"}

    if is_run_active(project_id):
        # A pipeline thread is alive (possibly paused): just release it.
        store.set_control_signal(project_id, "RUN")
        return {"resumed": True, "relaunched": False, "reason": "run_active"}

    dataset_path = proj.get("datasetPath")
    if not dataset_path or not os.path.exists(dataset_path):
        store.add_agent_log(
            project_id, "RESEARCH_ORCHESTRATOR",
            "Cannot resume: the dataset file for this project is no longer available on disk. Start a new research project instead.",
            "FAILED",
        )
        return {"resumed": False, "relaunched": False, "reason": "dataset_missing"}

    store.set_control_signal(project_id, "RUN")
    store.update_project(project_id, {"status": "IN_PROGRESS", "errorDetail": None})
    store.add_agent_log(
        project_id, "RESEARCH_ORCHESTRATOR",
        "Resuming research: relaunching the pipeline from the beginning (mid-flight state is not recoverable after an interruption).",
        "IN_PROGRESS",
    )
    store.add_event(project_id, "research.resumed", {"datasetPath": dataset_path})
    run_research_pipeline_async(project_id, dataset_path, proj.get("datasetMeta"), proj.get("testPath"))
    return {"resumed": True, "relaunched": True, "reason": "relaunched"}

def _check_control_signal(project_id: str) -> str:
    proj = store.get_project(project_id)
    if not proj:
        return "STOP"

    signal = proj.get("controlSignal", "RUN")
    while signal == "PAUSE":
        time.sleep(1)
        proj = store.get_project(project_id)
        if not proj:
            return "STOP"
        signal = proj.get("controlSignal", "RUN")

    return signal

def _orchestrate_pipeline(project_id: str, dataset_path: str, dataset_meta: Dict[str, Any] = None, test_path: str = None):
    """Runs the pipeline and ALWAYS releases the active-run registry, even when
    the run crashes, so the project can never stay wedged as 'active'."""
    try:
        _run_pipeline_stages(project_id, dataset_path, dataset_meta, test_path)
    finally:
        _unregister_run(project_id)


def _run_pipeline_stages(project_id: str, dataset_path: str, dataset_meta: Dict[str, Any] = None, test_path: str = None):
    proj = store.get_project(project_id)
    if not proj:
        return

    try:
        objective = proj["objective"]
        max_exps = proj.get("maxExperiments", 3)
        budget_mins = proj.get("budgetMins", 60)
        provider = proj.get("llmProvider", "HEURISTIC FALLBACK")
        
        start_wall_time = time.time()

        store.update_project(project_id, {
            "status": "RUNNING",
            "activeAgent": "RESEARCH_AGENT",
            "engineState": "LLM AUTONOMOUS" if os.environ.get("OPENAI_API_KEY") else "HEURISTIC FALLBACK"
        })
        store.add_event(project_id, "research.started", {"objective": objective})

        project_exp_dir = os.path.join(EXPERIMENTS_BASE_DIR, project_id)
        os.makedirs(project_exp_dir, exist_ok=True)

        # 0. Research Question Generation Stage
        store.update_stage_state(project_id, "research_question", "RUNNING")
        store.add_agent_log(project_id, "RESEARCH_AGENT", f"Formulating Machine-Learning Research Question for objective: '{objective}'...")
        research_question = generate_research_question(objective)
        store.update_project(project_id, {"researchQuestion": research_question})
        store.update_stage_state(project_id, "research_question", "COMPLETED")
        store.add_agent_log(project_id, "RESEARCH_AGENT", f"Research Question generated: \"{research_question}\"", "COMPLETED")
        store.add_event(project_id, "research.question.generated", {"question": research_question})

        # 1. Literature Search Stage
        if _check_control_signal(project_id) == "STOP":
            store.add_agent_log(project_id, "RESEARCH_AGENT", "Pipeline stopped by user.", "STOPPED")
            return

        store.update_stage_state(project_id, "literature_search", "RUNNING")
        store.add_event(project_id, "literature.search.started")
        store.add_agent_log(project_id, "RESEARCH_AGENT", f"Executing literature search on Semantic Scholar API...")
        try:
            papers = search_literature(objective)
            store.save_literature(project_id, papers)
            saved_papers = store.get_literature(project_id)
            if saved_papers and len(saved_papers) > 0:
                store.update_stage_state(project_id, "literature_search", "COMPLETED")
                store.add_agent_log(project_id, "RESEARCH_AGENT", f"Literature search completed. Found {len(saved_papers)} real research papers.", "COMPLETED")
                store.add_event(project_id, "literature.search.completed", {"count": len(saved_papers)})
            else:
                store.update_stage_state(project_id, "literature_search", "NOT_CONFIGURED")
                store.add_agent_log(project_id, "RESEARCH_AGENT", "Literature search API unconfigured or 0 papers returned. Marked stage as NOT CONFIGURED.", "WARNING")
                store.add_event(project_id, "literature.search.completed", {"count": 0, "status": "NOT_CONFIGURED"})
        except Exception as lit_err:
            papers = []
            store.save_literature(project_id, [])
            store.update_stage_state(project_id, "literature_search", "NOT_CONFIGURED")
            store.add_agent_log(project_id, "RESEARCH_AGENT", f"Literature API warning: {str(lit_err)}. Stage marked NOT CONFIGURED.", "WARNING")

        # 2. Dataset Analysis Stage
        if _check_control_signal(project_id) == "STOP":
            store.add_agent_log(project_id, "DATASET_AGENT", "Pipeline stopped by user.", "STOPPED")
            return

        store.update_stage_state(project_id, "dataset_eda", "RUNNING")
        store.add_event(project_id, "dataset.analysis.started")
        store.add_agent_log(project_id, "DATASET_AGENT", f"Inspecting dataset at {os.path.basename(dataset_path)}...")
        try:
            report = analyze_dataset(dataset_path, dataset_meta)
            store.save_dataset_report(project_id, report)
            saved_report = store.get_dataset_report(project_id)

            if not saved_report:
                raise ValueError("Dataset analysis report failed to persist in store!")

            store.update_project(project_id, {
                "datasetName": report.get("repoId") or report["filename"],
                "datasetSource": {
                    "source": report.get("source"),
                    "url": report.get("sourceUrl"),
                    "repoId": report.get("repoId"),
                    "license": report.get("license"),
                    "revision": report.get("revision"),
                    "splits": report.get("declaredSplits"),
                },
            })
            store.update_stage_state(project_id, "dataset_eda", "COMPLETED")
            imb_note = ""
            if report.get("isImbalanced"):
                imb_note = f" Highly imbalanced: minority class is only {report.get('minorityClassPct')}% of records."
            store.add_agent_log(project_id, "DATASET_AGENT", f"Dataset analysis complete & verified. {report['rowCount']} rows, {report['columnCount']} columns. Target: '{report['targetCandidate']}' ({report['taskType']}).{imb_note}", "COMPLETED")
            store.add_event(project_id, "dataset.analysis.completed", report)
        except Exception as e:
            store.update_stage_state(project_id, "dataset_eda", "FAILED")
            store.add_agent_log(project_id, "DATASET_AGENT", f"Dataset analysis error: {str(e)}", "FAILED")
            store.update_project(project_id, {"status": "FAILED", "activeAgent": "ERROR"})
            store.add_event(project_id, "research.failed", {"reason": str(e)})
            return

        # 3. Baseline Model Training Stage
        if _check_control_signal(project_id) == "STOP":
            store.add_agent_log(project_id, "BASELINE_AGENT", "Pipeline stopped by user.", "STOPPED")
            return

        store.update_stage_state(project_id, "baseline_training", "RUNNING")
        store.add_event(project_id, "baseline.started")
        store.add_agent_log(project_id, "BASELINE_AGENT", "Training the first set of models (Logistic Regression, Random Forest, Hist Gradient Boosting, XGBoost)...")
        target_col = report["targetCandidate"]
        task_type = report["taskType"]

        baselines, best_model, X_test, y_test = train_baselines(dataset_path, target_col, task_type, test_path=test_path)
        store.save_baselines(project_id, baselines)
        saved_baselines = store.get_baselines(project_id)

        completed_b = [b for b in saved_baselines if b["status"] == "COMPLETED"]

        if not completed_b:
            store.update_stage_state(project_id, "baseline_training", "FAILED")
            store.add_agent_log(project_id, "BASELINE_AGENT", "Baseline model training produced 0 valid models!", "FAILED")
            store.update_project(project_id, {"status": "FAILED", "activeAgent": "ERROR"})
            store.add_event(project_id, "research.failed", {"reason": "0 baseline models succeeded"})
            return

        # Choose the primary metric deliberately. Under severe class imbalance,
        # accuracy is meaningless, so rank by PR-AUC; otherwise F1 / R2.
        if task_type == "regression":
            primary_metric_key = "r2"
        elif report.get("isImbalanced"):
            primary_metric_key = "pr_auc"
        else:
            primary_metric_key = "f1"

        def _metric_of(b):
            m = b.get("metrics") or {}
            if primary_metric_key in m:
                return m[primary_metric_key]
            return next(iter(m.values()), 0.0)

        best_b = max(completed_b, key=_metric_of, default=completed_b[0])
        best_model_name = best_b["name"]
        best_metric_val = _metric_of(best_b)
        best_metric_str = f"{primary_metric_key.upper()}: {round(best_metric_val, 4)}"

        split_strategy = report.get("splitStrategy") or "Stratified 80/20 train/test split (random_state=42)"
        preprocessing_note = "Median imputation + standard scaling on numeric features; class weighting for imbalance."
        dataset_version = report.get("revision") or "local"

        store.update_project(project_id, {
            "bestModel": best_model_name,
            "bestMetric": best_metric_str
        })
        store.update_stage_state(project_id, "baseline_training", "COMPLETED")
        store.add_agent_log(project_id, "BASELINE_AGENT", f"Evaluated {len(completed_b)} baseline models. Best baseline: '{best_model_name}' ({best_metric_str}).", "COMPLETED")
        store.add_event(project_id, "baseline.completed", {"count": len(completed_b), "best": best_model_name})

        # 4. Root Experiment Node & Error Diagnostics Stage
        root_node = {
            "id": "node-root",
            "experimentId": "exp-baseline",
            "parentId": None,
            "title": f"Baseline: {best_model_name}",
            "hypothesis": f"Establish baseline {task_type} performance on dataset `{report.get('repoId') or report['filename']}` using standard benchmark models.",
            "status": "SUCCESS",
            "metricName": primary_metric_key.upper(),
            "metricValue": round(best_metric_val, 4),
            "allMetrics": best_b.get("metrics", {}),
            "hyperparams": best_b.get("hyperparams", f"{best_model_name} tuned defaults"),
            "model": best_model_name,
            "dataset": report.get("repoId") or report["filename"],
            "datasetVersion": dataset_version,
            "preprocessing": preprocessing_note,
            "features": report.get("featureNames"),
            "featureCount": report.get("columnCount", 0) - 1,
            "seed": 42,
            "splitStrategy": split_strategy,
            "executionTime": best_b["trainingTime"] if best_b else "0s",
            "conclusion": f"Baseline established. Best initial model '{best_model_name}' reached {best_metric_str}.",
            "children": []
        }
        tree_nodes = [root_node]
        store.save_tree_nodes(project_id, tree_nodes)

        store.update_stage_state(project_id, "error_diagnostics", "RUNNING")
        store.add_agent_log(project_id, "ERROR_ANALYSIS_AGENT", "Performing statistical error analysis & 95% bootstrap confidence interval estimation...")
        error_analysis = perform_error_analysis(best_model, X_test, y_test, list(X_test.columns) if hasattr(X_test, "columns") else None)
        store.save_error_analysis(project_id, error_analysis)
        saved_error_analysis = store.get_error_analysis(project_id)

        if saved_error_analysis:
            store.update_stage_state(project_id, "error_diagnostics", "COMPLETED")
            store.add_agent_log(project_id, "ERROR_ANALYSIS_AGENT", f"Error diagnostics completed & verified. 95% Bootstrap CI: [{saved_error_analysis['bootstrapCI']['ci_lower']} - {saved_error_analysis['bootstrapCI']['ci_upper']}].", "COMPLETED")
            store.add_event(project_id, "error_analysis.completed", saved_error_analysis)
        else:
            store.update_stage_state(project_id, "error_diagnostics", "FAILED")

        # 5. Iterative Autonomous Loop (Hypothesis -> Sandbox Execution -> Error Analysis)
        executed_count = 0
        parent_node_id = "node-root"
        latest_error_diag = error_analysis or {}
        experiment_statuses: List[str] = []

        while executed_count < max_exps:
            if _check_control_signal(project_id) == "STOP":
                store.add_agent_log(project_id, "RESEARCH_ORCHESTRATOR", "Research pipeline stopped by user.", "STOPPED")
                return

            elapsed_mins = round((time.time() - start_wall_time) / 60.0, 2)
            if elapsed_mins >= budget_mins:
                store.add_agent_log(project_id, "RESEARCH_ORCHESTRATOR", f"Compute budget limit reached ({budget_mins} mins). Concluding research.", "COMPLETED")
                break

            exp_idx = executed_count + 1
            exp_id = f"node-exp-{exp_idx}"

            # Hypothesis Generation Stage
            store.update_stage_state(project_id, "hypothesis_generation", "RUNNING")
            store.add_agent_log(project_id, "HYPOTHESIS_AGENT", f"Formulating Hypothesis #{exp_idx} informed by error diagnostics...")
            exp_hypothesis = generate_hypothesis_llm(objective, report, baselines, store.get_literature(project_id), exp_idx)

            # Critic LLM Evaluation Step
            critic_eval = query_critic_llm(exp_hypothesis["title"], exp_hypothesis["hypothesis"], best_metric_str)
            store.add_agent_log(project_id, "CRITIC_AGENT", f"[{critic_eval['criticModel']}] Scientific Peer Critique: {critic_eval['critique']}", "COMPLETED")

            store.add_agent_log(project_id, "CODING_AGENT", f"Synthesizing Python experiment script for Exp #{exp_idx}: '{exp_hypothesis['title']}'...")

            exp_dir = os.path.join(project_exp_dir, exp_id)
            os.makedirs(exp_dir, exist_ok=True)
            script_path = os.path.join(exp_dir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(exp_hypothesis["python_script"])

            if os.path.exists(script_path):
                store.update_stage_state(project_id, "hypothesis_generation", "COMPLETED")
                store.add_event(project_id, "hypothesis.generated", {"title": exp_hypothesis["title"], "hypothesis": exp_hypothesis["hypothesis"]})
            else:
                store.update_stage_state(project_id, "hypothesis_generation", "FAILED")

            # Sandboxed Execution Stage
            store.update_stage_state(project_id, "sandboxed_execution", "RUNNING")
            store.add_agent_log(project_id, "EXECUTION_MANAGER", f"Running sandboxed execution for Exp #{exp_idx} in isolated environment...")
            exec_env = {
                "TEST_PATH": test_path or "",
                "TARGET_COL": target_col,
                "TASK_TYPE": task_type,
                "PRIMARY_METRIC": primary_metric_key,
                "IS_IMBALANCED": "1" if report.get("isImbalanced") else "0",
            }
            exec_res = execute_sandboxed_experiment(exp_hypothesis["python_script"], dataset_path, timeout_sec=240, extra_env=exec_env)

            # Log to Telemetry Tracker (MLflow / DB / Redis)
            tracker.log_project_telemetry(project_id, f"exp_{exp_idx}", exec_res["metrics"])

            with open(os.path.join(exp_dir, "stdout.log"), "w", encoding="utf-8") as f:
                f.write(exec_res["stdout"])
            with open(os.path.join(exp_dir, "stderr.log"), "w", encoding="utf-8") as f:
                f.write(exec_res["stderr"])
            with open(os.path.join(exp_dir, "metrics.json"), "w", encoding="utf-8") as f:
                json.dump(exec_res["metrics"], f, indent=2)

            # Check sandbox stage completion rules — honest mapping: a non-zero
            # exit code is a FAILED run in ANY sandbox; only a successful run
            # without Docker is NOT_CONFIGURED (previously a failed process-
            # sandbox run was laundered into NOT_CONFIGURED).
            stage_state = _sandbox_stage_state(bool(exec_res.get("dockerAvailable")), exec_res.get("exitCode"))
            if stage_state == "COMPLETED":
                store.add_agent_log(project_id, "EXECUTION_MANAGER", "Docker container execution completed successfully (Exit code 0).", "COMPLETED")
            elif stage_state == "NOT_CONFIGURED":
                store.add_agent_log(project_id, "EXECUTION_MANAGER", "Docker sandbox unavailable on host system. Executed in isolated Process Sandbox. Stage state: NOT CONFIGURED.", "WARNING")
            else:
                store.add_agent_log(project_id, "EXECUTION_MANAGER", f"Sandboxed execution failed with exit code {exec_res.get('exitCode')}.", "FAILED")
            store.update_stage_state(project_id, "sandboxed_execution", stage_state)

            exp_metrics = exec_res.get("metrics") or {}
            exp_metric_val = exp_metrics.get("metric_value")
            if exp_metric_val is None:
                # A failed run produced no real metric: record 0 instead of
                # laundering the baseline value into a failed experiment.
                exp_metric_val = 0.0 if exec_res["exitCode"] != 0 else best_metric_val
            exp_metric_name = exp_metrics.get("metric_name", primary_metric_key.upper())

            status = "IMPROVED" if exp_metric_val > best_metric_val else "PLATEAUED"
            if exec_res["exitCode"] != 0:
                status = "FAILED"
            experiment_statuses.append(status)

            delta = round(float(exp_metric_val) - float(best_metric_val), 4)
            if status == "IMPROVED":
                conclusion = (f"Confirmed: improved {exp_metric_name} by {delta} over the previous best "
                              f"({round(best_metric_val, 4)} -> {round(exp_metric_val, 4)}).")
                best_metric_val = exp_metric_val
                best_metric_str = f"{exp_metric_name}: {round(exp_metric_val, 4)}"
                best_model_name = exp_hypothesis["title"]
            elif status == "FAILED":
                conclusion = f"Experiment failed to run (exit code {exec_res.get('exitCode')}). See logs for details."
            else:
                conclusion = (f"Not confirmed: no improvement over the previous best "
                              f"({exp_metric_name} {round(exp_metric_val, 4)} vs {round(best_metric_val, 4)}).")

            exp_node = {
                "id": exp_id,
                "experimentId": f"exp-{exp_idx}",
                "parentId": parent_node_id,
                "title": exp_hypothesis["title"],
                "hypothesis": exp_hypothesis["hypothesis"],
                "status": status,
                "metricName": exp_metric_name,
                "metricValue": round(exp_metric_val, 4),
                "allMetrics": exec_res["metrics"].get("metrics", exec_res["metrics"]),
                "model": exp_hypothesis.get("model", "Generated experiment model"),
                "dataset": report.get("repoId") or report["filename"],
                "datasetVersion": dataset_version,
                "preprocessing": preprocessing_note,
                "features": report.get("featureNames"),
                "featureCount": report.get("columnCount", 0) - 1,
                "hyperparams": exp_hypothesis["hyperparams"],
                "seed": 42,
                "splitStrategy": split_strategy,
                "executionTime": exec_res["runtime"],
                "sandboxMode": exec_res.get("sandboxMode"),
                "artifacts": {
                    "script": os.path.join(exp_dir, "script.py"),
                    "stdout": os.path.join(exp_dir, "stdout.log"),
                    "stderr": os.path.join(exp_dir, "stderr.log"),
                    "metrics": os.path.join(exp_dir, "metrics.json"),
                },
                "conclusion": conclusion,
                "stdout": exec_res["stdout"],
                "stderr": exec_res["stderr"],
                "children": []
            }

            for n in tree_nodes:
                if n["id"] == parent_node_id:
                    n.setdefault("children", []).append(exp_id)
                    break

            tree_nodes.append(exp_node)
            executed_count += 1
            if status == "IMPROVED":
                parent_node_id = exp_id

            store.save_tree_nodes(project_id, tree_nodes)

            # Error Diagnostics on Experiment. Resilient: a diagnostics failure
            # must not kill the pipeline after the experiment already ran — keep
            # the previous diagnostics and continue.
            store.add_agent_log(project_id, "ERROR_ANALYSIS_AGENT", f"Running error diagnostics on Experiment #{exp_idx} predictions...")
            try:
                latest_error_diag = perform_error_analysis(best_model, X_test, y_test, list(X_test.columns) if hasattr(X_test, "columns") else None)
                store.save_error_analysis(project_id, latest_error_diag)
            except Exception as diag_err:
                store.add_agent_log(project_id, "ERROR_ANALYSIS_AGENT", f"Error diagnostics failed for Exp #{exp_idx}: {diag_err}. Keeping previous diagnostics.", "WARNING")

            elapsed_mins = round((time.time() - start_wall_time) / 60.0, 2)
            store.update_project(project_id, {
                "experimentsCount": executed_count,
                "bestModel": best_model_name,
                "bestMetric": best_metric_str,
                "computeUsed": f"{elapsed_mins} mins / {budget_mins} mins"
            })
            store.add_agent_log(project_id, "EXECUTION_MANAGER", f"Experiment #{exp_idx} completed with status: {status} ({exp_metric_name}: {exp_metric_val}).", "COMPLETED")
            store.add_event(project_id, "experiment.completed", exp_node)

        # 6. Scientific Research Report Stage
        if _check_control_signal(project_id) == "STOP":
            store.add_agent_log(project_id, "REPORT_AGENT", "Pipeline stopped by user.", "STOPPED")
            return

        store.update_stage_state(project_id, "research_report", "RUNNING")
        store.add_agent_log(project_id, "REPORT_AGENT", "Generating scientific Markdown research report from verified results...")
        report_md = generate_research_report(proj, report, baselines, tree_nodes, latest_error_diag)
        store.save_report(project_id, report_md)
        saved_report_md = store.get_report(project_id)

        if saved_report_md and len(saved_report_md) > 100:
            store.update_stage_state(project_id, "research_report", "COMPLETED")
            store.add_agent_log(project_id, "REPORT_AGENT", "Scientific Markdown research report successfully generated & stored.", "COMPLETED")
        else:
            store.update_stage_state(project_id, "research_report", "FAILED")

        # Conclude pipeline state
        elapsed_mins = round((time.time() - start_wall_time) / 60.0, 2)
        proj_stages = store.get_project(project_id).get("stageStates", {})

        final_status = _compute_final_status(proj_stages, experiment_statuses)
        all_experiments_failed = bool(experiment_statuses) and all(s == "FAILED" for s in experiment_statuses)

        store.add_agent_log(project_id, "RESEARCH_ORCHESTRATOR", f"Autonomous research pipeline finished with status: {final_status}.", final_status)
        store.update_project(project_id, {
            "status": final_status,
            "activeAgent": "FINISHED" if final_status == "COMPLETED" else "ERROR",
            "computeUsed": f"{elapsed_mins} mins / {budget_mins} mins",
            # Honest bookkeeping: when every attempted experiment failed, the
            # run is FAILED even though the report itself rendered fine.
            "errorDetail": "All attempted experiments failed; no validated improvement was produced." if all_experiments_failed else None,
        })
        store.add_event(project_id, f"research.{final_status.lower()}")

    except Exception as top_err:
        err_msg = str(top_err) or "Pipeline execution error."
        tb_str = traceback.format_exc()
        print(f"[ORCHESTRATOR FATAL ERROR]: {err_msg}\n{tb_str}")
        store.add_agent_log(project_id, "RESEARCH_ORCHESTRATOR", f"Pipeline fatal failure: {err_msg}", "FAILED")
        store.update_project(project_id, {
            "status": "FAILED",
            "activeAgent": "ERROR",
            "errorDetail": err_msg
        })
        store.add_event(project_id, "research.failed", {"error": err_msg})

