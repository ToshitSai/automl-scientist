"""Reliability regression tests for the critical backend fixes.

Covers the five issues found in the backend audit:
  1. Duplicate concurrent launches of the same project (orchestrator registry).
  2. Restart reconciliation (ghost IN_PROGRESS runs) + resume that actually
     relaunches a dead run instead of flipping a control flag.
  3. Failure laundering: failed experiments / runs must never be reported as
     COMPLETED, and failed runs must not inherit the baseline metric.
  4. Dataset handoff into the sandbox (real basenames, container env paths).
  5. Store reliability (atomic saves, concurrent mutations, RLock).

The store is isolated and the LLM disabled by tests/conftest.py; the heavy
pipeline dependencies (literature search, training, sandbox execution) are
stubbed so these tests stay hermetic and deterministic.
"""
import json
import threading
import time

import pandas as pd
import pytest

import database.store as store_mod
from database.store import ResearchStore, store

import agents.orchestrator as orch
import sandbox.runner as runner


@pytest.fixture(autouse=True)
def clear_run_registry():
    """The orchestrator run registry is module-level; keep tests isolated."""
    orch._active_runs.clear()
    yield
    orch._active_runs.clear()


# ---------------------------------------------------------------------------
# 1. Duplicate launch guard
# ---------------------------------------------------------------------------
def test_run_registry_atomic_claim():
    assert orch._try_register_run("p-reg") is True
    assert orch._try_register_run("p-reg") is False  # already claimed
    assert orch.is_run_active("p-reg") is True
    orch._unregister_run("p-reg")
    assert orch._try_register_run("p-reg") is True  # reclaimable after release
    orch._unregister_run("p-reg")


def test_duplicate_launch_refused(isolate_store, monkeypatch, tmp_path):
    pid = "proj-dup"
    isolate_store.create_project(pid, "n", "Improve fraud detection", "d.csv", 60, None,
                                 dataset_path=str(tmp_path / "d.csv"))
    started, release = threading.Event(), threading.Event()

    def fake_pipeline(project_id, dataset_path, dataset_meta=None, test_path=None):
        started.set()
        release.wait(timeout=5)
        orch._unregister_run(project_id)  # mirror the real wrapper's cleanup

    monkeypatch.setattr(orch, "_orchestrate_pipeline", fake_pipeline)
    try:
        assert orch.run_research_pipeline_async(pid, str(tmp_path / "d.csv")) is True
        assert started.wait(timeout=5)
        # Second launch while the first is still active must be refused.
        assert orch.run_research_pipeline_async(pid, str(tmp_path / "d.csv")) is False
        logs = isolate_store.get_project(pid)["agentLogs"]
        assert any("Duplicate launch refused" in l["message"] for l in logs)
    finally:
        release.set()

    deadline = time.time() + 5
    while orch.is_run_active(pid) and time.time() < deadline:
        time.sleep(0.01)
    assert not orch.is_run_active(pid)
    # After the run finished, a new launch is allowed again.
    monkeypatch.setattr(orch, "_orchestrate_pipeline", lambda *a, **k: orch._unregister_run(a[0]))
    assert orch.run_research_pipeline_async(pid, str(tmp_path / "d.csv")) is True


# ---------------------------------------------------------------------------
# 2. Restart reconciliation + resume
# ---------------------------------------------------------------------------
def test_reconcile_marks_ghost_runs_failed(isolate_store):
    for pid, st in [("a", "IN_PROGRESS"), ("b", "RUNNING"), ("c", "QUEUED"),
                    ("d", "PAUSED"), ("e", "COMPLETED"), ("f", "FAILED"), ("g", "STOPPED")]:
        isolate_store.create_project(pid, "n", "objective text here", "d.csv", 60, None)
        isolate_store.update_project(pid, {"status": st})

    reconciled = isolate_store.reconcile_stale_runs()
    assert set(reconciled) == {"a", "b", "c"}

    p = isolate_store.get_project("a")
    assert p["status"] == "FAILED"
    assert "restart" in p["errorDetail"].lower()
    assert any(e["type"] == "research.interrupted" for e in p["events"])
    assert any("marked FAILED" in l["message"] for l in p["agentLogs"])
    # Terminal + user-paused projects are untouched.
    assert isolate_store.get_project("e")["status"] == "COMPLETED"
    assert isolate_store.get_project("f")["status"] == "FAILED"
    assert isolate_store.get_project("g")["status"] == "STOPPED"
    assert isolate_store.get_project("d")["status"] == "PAUSED"


def test_reconcile_is_idempotent(isolate_store):
    isolate_store.create_project("a", "n", "objective text here", "d.csv", 60, None)
    first = isolate_store.reconcile_stale_runs()
    second = isolate_store.reconcile_stale_runs()
    assert first == ["a"] and second == []


def test_resume_relaunches_dead_run(isolate_store, monkeypatch, tmp_path):
    pid = "proj-resume"
    ds = tmp_path / "train.csv"
    ds.write_text("v1,v2,is_fraud\n1,2,0\n3,4,1\n")
    isolate_store.create_project(pid, "n", "Improve fraud detection", "train.csv", 60, None,
                                 dataset_path=str(ds), dataset_meta={"source": "huggingface"})
    isolate_store.update_project(pid, {"status": "FAILED"})  # e.g. reconciled after restart

    launched = {}

    def fake_launch(pid_, path, meta=None, test=None):
        launched.update({"pid": pid_, "path": path, "meta": meta})
        return True

    monkeypatch.setattr(orch, "run_research_pipeline_async", fake_launch)
    res = orch.resume_pipeline(pid)
    assert res == {"resumed": True, "relaunched": True, "reason": "relaunched"}
    assert launched == {"pid": pid, "path": str(ds), "meta": {"source": "huggingface"}}
    assert isolate_store.get_project(pid)["status"] == "IN_PROGRESS"
    assert any(e["type"] == "research.resumed" for e in isolate_store.get_project(pid)["events"])


def test_resume_active_run_only_unpauses(isolate_store, monkeypatch):
    pid = "proj-live"
    isolate_store.create_project(pid, "n", "objective text here", "d.csv", 60, None)
    isolate_store.set_control_signal(pid, "PAUSE")
    orch._active_runs.add(pid)  # simulate a live (paused) pipeline thread

    def must_not_launch(*a, **k):
        raise AssertionError("an active run must be unpaused, not relaunched")

    monkeypatch.setattr(orch, "run_research_pipeline_async", must_not_launch)
    try:
        res = orch.resume_pipeline(pid)
        assert res == {"resumed": True, "relaunched": False, "reason": "run_active"}
        p = isolate_store.get_project(pid)
        assert p["controlSignal"] == "RUN"
        assert p["status"] == "IN_PROGRESS"
    finally:
        orch._unregister_run(pid)


def test_resume_without_dataset_fails_honestly(isolate_store, monkeypatch):
    pid = "proj-nods"
    isolate_store.create_project(pid, "n", "objective text here", "d.csv", 60, None)  # no datasetPath
    monkeypatch.setattr(orch, "run_research_pipeline_async", lambda *a, **k: True)
    res = orch.resume_pipeline(pid)
    assert res == {"resumed": False, "relaunched": False, "reason": "dataset_missing"}
    assert any("no longer available" in l["message"]
               for l in isolate_store.get_project(pid)["agentLogs"])


def test_resume_unknown_project_reported(isolate_store):
    assert orch.resume_pipeline("does-not-exist")["reason"] == "not_found"


def test_control_endpoint_resume_relaunches(monkeypatch, tmp_path):
    TestClient = pytest.importorskip("fastapi.testclient").TestClient
    from backend.main import app

    pid = "proj-ctrl"
    ds = tmp_path / "train.csv"
    ds.write_text("v1,v2,is_fraud\n1,2,0\n3,4,1\n")
    store.create_project(pid, "n", "Improve fraud detection", "train.csv", 60, None,
                         dataset_path=str(ds))
    store.update_project(pid, {"status": "FAILED"})
    called = {}
    monkeypatch.setattr(orch, "run_research_pipeline_async",
                        lambda pid_, *a, **k: called.setdefault("pid", pid_))

    with TestClient(app) as client:  # context manager also runs startup reconciliation
        r = client.post(f"/api/projects/{pid}/control", json={"signal": "RUN"})
    assert r.status_code == 200
    body = r.json()
    assert body["resume"]["relaunched"] is True
    assert called["pid"] == pid
    assert store.get_project(pid)["status"] == "IN_PROGRESS"


# ---------------------------------------------------------------------------
# 3. Honest failure propagation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("docker,code,expected", [
    (True, 0, "COMPLETED"),
    (False, 0, "NOT_CONFIGURED"),
    (True, 1, "FAILED"),
    (False, 1, "FAILED"),    # regression: used to be laundered to NOT_CONFIGURED
    (True, 124, "FAILED"),
    (False, 124, "FAILED"),
])
def test_sandbox_stage_state_is_honest(docker, code, expected):
    assert orch._sandbox_stage_state(docker, code) == expected


def test_compute_final_status():
    core = {"dataset_eda": "COMPLETED", "baseline_training": "COMPLETED", "research_report": "COMPLETED"}
    # Every attempted experiment failed -> FAILED (regression: used to be COMPLETED).
    assert orch._compute_final_status(core, ["FAILED", "FAILED"]) == "FAILED"
    # At least one experiment produced a result -> COMPLETED.
    assert orch._compute_final_status(core, ["IMPROVED", "FAILED"]) == "COMPLETED"
    assert orch._compute_final_status(core, ["PLATEAUED"]) == "COMPLETED"
    # No experiments attempted (budget exhausted early) but core stages fine -> COMPLETED.
    assert orch._compute_final_status(core, []) == "COMPLETED"
    # A core stage failed -> FAILED regardless of experiments.
    broken = {**core, "research_report": "FAILED"}
    assert orch._compute_final_status(broken, ["IMPROVED"]) == "FAILED"


class _StaticModel:
    """Deterministic stand-in for a trained baseline model."""

    def predict(self, X):
        return [0] * len(X)


def _stub_training(monkeypatch):
    def fake_train(file_path, target_col, task_type="classification", test_path=None):
        baselines = [{
            "id": "base-1", "name": "Stub Logistic Regression", "type": "Linear",
            "hyperparams": "stub", "whySelected": "stub",
            "metrics": {"f1": 0.5, "pr_auc": 0.5, "accuracy": 0.8, "precision": 0.5, "recall": 0.5},
            "trainingTime": "0s", "status": "COMPLETED",
        }]
        X_test = pd.DataFrame({"v1": [1, 2, 3, 4], "v2": [4, 3, 2, 1]})
        y_test = pd.Series([0, 1, 0, 0])
        return baselines, _StaticModel(), X_test, y_test

    monkeypatch.setattr(orch, "train_baselines", fake_train)


def _setup_pipeline_project(isolate_store, tmp_path, pid, max_experiments):
    ds = tmp_path / "train.csv"
    rows = ["v1,v2,is_fraud"]
    for i in range(40):
        rows.append(f"{i},{(i * 7) % 13},{1 if i % 8 == 0 else 0}")
    ds.write_text("\n".join(rows) + "\n")
    isolate_store.create_project(pid, "n", "Improve fraud detection on stub data", "train.csv", 60, None,
                                 dataset_path=str(ds))
    isolate_store.update_project(pid, {"maxExperiments": max_experiments})
    return str(ds)


def _patch_pipeline_deps(monkeypatch, tmp_path, exec_result_factory):
    monkeypatch.setattr(orch, "EXPERIMENTS_BASE_DIR", str(tmp_path / "experiments"))
    monkeypatch.setattr(orch, "search_literature", lambda *a, **k: [])
    monkeypatch.setattr(orch.tracker, "log_project_telemetry", lambda *a, **k: None)
    _stub_training(monkeypatch)
    monkeypatch.setattr(orch, "execute_sandboxed_experiment",
                        lambda script, path, timeout_sec=60, extra_env=None: exec_result_factory())


def test_pipeline_all_failed_experiments_yields_failed_project(isolate_store, monkeypatch, tmp_path):
    pid = "proj-itfail"
    ds = _setup_pipeline_project(isolate_store, tmp_path, pid, max_experiments=2)

    def failing_exec():
        return {"sandboxMode": "Process Sandbox", "dockerAvailable": False, "exitCode": 1,
                "runtime": "0.1s", "stdout": "", "stderr": "simulated crash",
                "metrics": {}, "success": False}

    _patch_pipeline_deps(monkeypatch, tmp_path, failing_exec)
    orch._orchestrate_pipeline(pid, ds, None, None)

    proj = isolate_store.get_project(pid)
    assert proj["status"] == "FAILED"
    assert "All attempted experiments failed" in (proj.get("errorDetail") or "")
    assert proj["stageStates"]["sandboxed_execution"] == "FAILED"

    exp_nodes = [n for n in isolate_store.get_tree_nodes(pid) if n["id"] != "node-root"]
    assert len(exp_nodes) == 2
    assert all(n["status"] == "FAILED" for n in exp_nodes)
    # Failed runs must NOT inherit the baseline metric (regression).
    assert all(n["metricValue"] == 0.0 for n in exp_nodes)
    # The report is still generated (for debugging) but must disclose the failures.
    report = isolate_store.get_report(pid) or ""
    assert "`FAILED`" in report


def test_pipeline_improvement_yields_completed_project(isolate_store, monkeypatch, tmp_path):
    pid = "proj-itok"
    ds = _setup_pipeline_project(isolate_store, tmp_path, pid, max_experiments=1)

    def improving_exec():
        return {"sandboxMode": "Process Sandbox", "dockerAvailable": False, "exitCode": 0,
                "runtime": "1s", "stdout": "ok", "stderr": "",
                "metrics": {"metric_name": "PR_AUC", "metric_value": 0.9, "metrics": {"pr_auc": 0.9}},
                "success": True}

    _patch_pipeline_deps(monkeypatch, tmp_path, improving_exec)
    orch._orchestrate_pipeline(pid, ds, None, None)

    proj = isolate_store.get_project(pid)
    assert proj["status"] == "COMPLETED"
    assert proj["errorDetail"] is None
    # Success without Docker is still honestly NOT_CONFIGURED (preserved semantics).
    assert proj["stageStates"]["sandboxed_execution"] == "NOT_CONFIGURED"

    exp_nodes = [n for n in isolate_store.get_tree_nodes(pid) if n["id"] != "node-root"]
    assert len(exp_nodes) == 1
    node = exp_nodes[0]
    assert node["status"] == "IMPROVED"
    assert node["metricValue"] == 0.9
    assert "0.9" in proj["bestMetric"]


# ---------------------------------------------------------------------------
# 4. Dataset handoff into the sandbox
# ---------------------------------------------------------------------------
def test_docker_args_preserve_real_basenames_and_override_host_paths(tmp_path):
    dataset = tmp_path / "train.parquet"
    dataset.write_text("stub")
    test_split = tmp_path / "test.parquet"
    test_split.write_text("stub")

    cmd = runner.build_docker_run_args(
        str(tmp_path / "tmpdir"), str(dataset),
        {"TEST_PATH": str(test_split), "TARGET_COL": "is_fraud", "PRIMARY_METRIC": "pr_auc"},
    )

    envs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-e"]
    # Extension-based readers keep working: real basename, not 'dataset.csv'.
    assert "DATASET_PATH=/app/dataset/train.parquet" in envs
    # The held-out split is mounted and TEST_PATH points at the CONTAINER path.
    assert "TEST_PATH=/app/test/test.parquet" in envs
    assert all(not v.startswith(str(tmp_path)) for v in envs)  # no host paths leak into env
    assert "METRICS_PATH=/app/metrics.json" in envs
    assert f"{dataset}:/app/dataset/train.parquet:ro" in cmd
    assert f"{test_split}:/app/test/test.parquet:ro" in cmd


def test_docker_args_without_test_split_keeps_empty_env(tmp_path):
    dataset = tmp_path / "data.csv"
    dataset.write_text("stub")
    cmd = runner.build_docker_run_args(str(tmp_path / "tmpdir"), str(dataset),
                                       {"TEST_PATH": "", "TARGET_COL": "y"})
    envs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-e"]
    assert "DATASET_PATH=/app/dataset/data.csv" in envs
    assert not any(v.startswith("/app/test/") for v in envs)
    assert "TEST_PATH=" in " ".join(cmd)  # empty TEST_PATH from extra_env is passed through


def test_process_sandbox_hands_off_dataset_and_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "is_docker_available", lambda: False)
    ds = tmp_path / "train.csv"
    ds.write_text("a,b,target\n1,2,0\n3,4,1\n5,6,0\n")

    script = (
        "import os, json\n"
        "p = os.environ['DATASET_PATH']\n"
        "assert os.path.exists(p), 'dataset missing at ' + p\n"
        "assert p.lower().endswith('.csv'), 'wrong extension handed off: ' + p\n"
        "with open(p) as f:\n"
        "    assert len(f.readlines()) == 4\n"
        "with open(os.environ['METRICS_PATH'], 'w') as f:\n"
        "    json.dump({'metric_name': 'F1', 'metric_value': 0.5, 'metrics': {}}, f)\n"
        "print('ok')\n"
    )
    res = runner.execute_sandboxed_experiment(script, str(ds), timeout_sec=60,
                                              extra_env={"TEST_PATH": "", "TARGET_COL": "target"})
    assert res["exitCode"] == 0, res["stderr"]
    assert res["success"] is True
    assert res["metrics"]["metric_value"] == 0.5


def test_process_sandbox_reports_failure_honestly(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "is_docker_available", lambda: False)
    ds = tmp_path / "train.csv"
    ds.write_text("a\n1\n")
    res = runner.execute_sandboxed_experiment("raise RuntimeError('boom')", str(ds), timeout_sec=30)
    assert res["exitCode"] != 0
    assert res["success"] is False
    assert "boom" in res["stderr"]
    assert res["metrics"] == {}


# ---------------------------------------------------------------------------
# 5. Store reliability
# ---------------------------------------------------------------------------
def test_save_is_atomic_and_valid_json(isolate_store, tmp_path):
    pid = "proj-atomic"
    isolate_store.create_project(pid, "n", "objective text here", "d.csv", 60, None)
    ResearchStore.save(isolate_store)  # bypass the conftest no-op shim: real save

    data = json.loads((tmp_path / "store.json").read_text(encoding="utf-8"))
    assert pid in data["projects"]
    assert list(tmp_path.glob(".research_store_*")) == []  # no temp leftovers


def test_failed_save_keeps_last_good_state(isolate_store, tmp_path, monkeypatch):
    pid = "proj-safe"
    isolate_store.create_project(pid, "n", "objective text here", "d.csv", 60, None)
    ResearchStore.save(isolate_store)
    good = (tmp_path / "store.json").read_text(encoding="utf-8")

    # In-memory change whose persistence will fail (simulated disk full).
    isolate_store.update_project(pid, {"status": "RUNNING"})
    real_dump = store_mod.json.dump

    def boom(*a, **k):
        raise RuntimeError("simulated disk full")

    monkeypatch.setattr(store_mod.json, "dump", boom)
    ResearchStore.save(isolate_store)  # must warn, clean up, and NOT corrupt the file
    monkeypatch.setattr(store_mod.json, "dump", real_dump)

    assert (tmp_path / "store.json").read_text(encoding="utf-8") == good
    assert list(tmp_path.glob(".research_store_*")) == []


def test_concurrent_mutations_do_not_lose_updates_or_crash(isolate_store):
    pid = "proj-race"
    isolate_store.create_project(pid, "n", "objective text here", "d.csv", 60, None)
    errors = []

    def worker(i):
        try:
            for j in range(25):
                isolate_store.add_agent_log(pid, f"AGENT-{i}", f"w{i}-j{j}")
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    logs = isolate_store.get_project(pid)["agentLogs"]
    assert len(logs) == 100  # every append survived the concurrent save() calls


def test_create_project_persists_launch_context(isolate_store, tmp_path):
    ds = tmp_path / "train.parquet"
    meta = {"source": "huggingface", "repoId": "owner/name"}
    isolate_store.create_project("p-ctx", "n", "objective text here", "owner/name", 60, None,
                                 max_experiments=3, dataset_path=str(ds), test_path=str(tmp_path / "t.parquet"),
                                 dataset_meta=meta)
    p = isolate_store.get_project("p-ctx")
    assert p["datasetPath"] == str(ds)
    assert p["testPath"] == str(tmp_path / "t.parquet")
    assert p["datasetMeta"] == meta
    # Defaults stay backwards compatible.
    isolate_store.create_project("p-ctx2", "n", "objective text here", "d", 60, None)
    assert isolate_store.get_project("p-ctx2")["datasetPath"] is None
