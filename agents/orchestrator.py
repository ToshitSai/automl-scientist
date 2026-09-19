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
from backend.llm import generate_hypothesis_llm, generate_research_question, query_llm

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

def run_research_pipeline(project_id: str, dataset_path: str):
    """Executes the autonomous ML research pipeline synchronously."""
    _orchestrate_pipeline(project_id, dataset_path)

def run_research_pipeline_async(project_id: str, dataset_path: str):
    """Executes the autonomous ML research pipeline asynchronously in a background thread."""
    thread = threading.Thread(target=_orchestrate_pipeline, args=(project_id, dataset_path), daemon=True)
    thread.start()

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

def _orchestrate_pipeline(project_id: str, dataset_path: str):
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
            report = analyze_dataset(dataset_path)
            store.save_dataset_report(project_id, report)
            saved_report = store.get_dataset_report(project_id)

            if not saved_report:
                raise ValueError("Dataset analysis report failed to persist in store!")

            store.update_project(project_id, {"datasetName": report["filename"]})
            store.update_stage_state(project_id, "dataset_eda", "COMPLETED")
            store.add_agent_log(project_id, "DATASET_AGENT", f"Dataset EDA completed & verified. {report['rowCount']} rows, {report['columnCount']} columns. Target: '{report['targetCandidate']}' ({report['taskType']}).", "COMPLETED")
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
        store.add_agent_log(project_id, "BASELINE_AGENT", "Training baseline models (Logistic Regression, Random Forest, Gradient Boosting, MLP)...")
        target_col = report["targetCandidate"]
        task_type = report["taskType"]

        baselines, best_model, X_test, y_test = train_baselines(dataset_path, target_col, task_type)
        store.save_baselines(project_id, baselines)
        saved_baselines = store.get_baselines(project_id)

        completed_b = [b for b in saved_baselines if b["status"] == "COMPLETED"]

        if not completed_b:
            store.update_stage_state(project_id, "baseline_training", "FAILED")
            store.add_agent_log(project_id, "BASELINE_AGENT", "Baseline model training produced 0 valid models!", "FAILED")
            store.update_project(project_id, {"status": "FAILED", "activeAgent": "ERROR"})
            store.add_event(project_id, "research.failed", {"reason": "0 baseline models succeeded"})
            return

        best_b = max(completed_b, key=lambda x: list(x["metrics"].values())[0] if x["metrics"] else 0, default=completed_b[0])
        best_model_name = best_b["name"]
        primary_metric_key = list(best_b['metrics'].keys())[0] if best_b.get("metrics") else ("F1" if task_type == "classification" else "R2")
        best_metric_val = list(best_b['metrics'].values())[0] if best_b.get("metrics") else 0.0
        best_metric_str = f"{primary_metric_key.upper()}: {best_metric_val}"

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
            "parentId": None,
            "title": f"Baseline: {best_model_name}",
            "hypothesis": f"Establish baseline {task_type} performance on dataset `{report['filename']}` using standard benchmark models.",
            "status": "SUCCESS",
            "metricName": primary_metric_key.upper(),
            "metricValue": best_metric_val,
            "hyperparams": f"{best_model_name} default configuration",
            "executionTime": best_b["trainingTime"] if best_b else "0s",
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
            exec_res = execute_sandboxed_experiment(exp_hypothesis["python_script"], dataset_path, timeout_sec=60)

            with open(os.path.join(exp_dir, "stdout.log"), "w", encoding="utf-8") as f:
                f.write(exec_res["stdout"])
            with open(os.path.join(exp_dir, "stderr.log"), "w", encoding="utf-8") as f:
                f.write(exec_res["stderr"])
            with open(os.path.join(exp_dir, "metrics.json"), "w", encoding="utf-8") as f:
                json.dump(exec_res["metrics"], f, indent=2)

            # Check sandbox stage completion rules
            if exec_res.get("dockerAvailable") and exec_res.get("exitCode") == 0:
                store.update_stage_state(project_id, "sandboxed_execution", "COMPLETED")
                store.add_agent_log(project_id, "EXECUTION_MANAGER", "Docker container execution completed successfully (Exit code 0).", "COMPLETED")
            elif not exec_res.get("dockerAvailable"):
                # Docker missing -> state MUST NOT be COMPLETED
                store.update_stage_state(project_id, "sandboxed_execution", "NOT_CONFIGURED")
                store.add_agent_log(project_id, "EXECUTION_MANAGER", "Docker sandbox unavailable on host system. Executed in isolated Process Sandbox. Stage state: NOT CONFIGURED.", "WARNING")
            else:
                store.update_stage_state(project_id, "sandboxed_execution", "FAILED")
                store.add_agent_log(project_id, "EXECUTION_MANAGER", f"Sandboxed execution failed with exit code {exec_res.get('exitCode')}.", "FAILED")

            exp_metric_val = exec_res["metrics"].get("metric_value", best_metric_val)
            exp_metric_name = exec_res["metrics"].get("metric_name", primary_metric_key.upper())

            status = "IMPROVED" if exp_metric_val > best_metric_val else "PLATEAUED"
            if exec_res["exitCode"] != 0:
                status = "FAILED"

            if status == "IMPROVED":
                best_metric_val = exp_metric_val
                best_metric_str = f"{exp_metric_name}: {exp_metric_val}"
                best_model_name = exp_hypothesis["title"]

            exp_node = {
                "id": exp_id,
                "parentId": parent_node_id,
                "title": exp_hypothesis["title"],
                "hypothesis": exp_hypothesis["hypothesis"],
                "status": status,
                "metricName": exp_metric_name,
                "metricValue": exp_metric_val,
                "hyperparams": exp_hypothesis["hyperparams"],
                "executionTime": exec_res["runtime"],
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

            # Error Diagnostics on Experiment
            store.add_agent_log(project_id, "ERROR_ANALYSIS_AGENT", f"Running error diagnostics on Experiment #{exp_idx} predictions...")
            latest_error_diag = perform_error_analysis(best_model, X_test, y_test, list(X_test.columns) if hasattr(X_test, "columns") else None)
            store.save_error_analysis(project_id, latest_error_diag)

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

        core_succeeded = (
            proj_stages.get("dataset_eda") == "COMPLETED" and
            proj_stages.get("baseline_training") == "COMPLETED" and
            proj_stages.get("research_report") == "COMPLETED"
        )

        final_status = "COMPLETED" if core_succeeded else "FAILED"

        store.add_agent_log(project_id, "RESEARCH_ORCHESTRATOR", f"Autonomous research pipeline finished with status: {final_status}.", final_status)
        store.update_project(project_id, {
            "status": final_status,
            "activeAgent": "FINISHED" if core_succeeded else "ERROR",
            "computeUsed": f"{elapsed_mins} mins / {budget_mins} mins"
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

