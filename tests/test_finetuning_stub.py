"""Tests for the isolated finetuning/ stub: license gate, architecture, isolation."""

import ast
import os

import pytest

from finetuning.config import (
    FineTuneConfig,
    PRIMARY_SFT_DATASET,
    ALTERNATE_SFT_DATASET,
    TULU3_COMPONENT_LICENSES,
)
from finetuning import license_gate, trainer, architecture, benchmark

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --- tulu-3 mixture (most-restrictive-component logic) ---------------------- #
def _tulu3(**kw):
    return FineTuneConfig(dataset_repo_id=ALTERNATE_SFT_DATASET, **kw)


def test_mixture_research_allowed():
    assert license_gate.evaluate(_tulu3(intended_use="research")).allowed is True


def test_mixture_commercial_blocked_by_non_commercial_component():
    d = license_gate.evaluate(_tulu3(intended_use="commercial"))
    assert d.allowed is False
    assert "HuggingFaceH4/no_robots" in d.blocking


def test_mixture_commercial_still_blocked_after_dropping_no_robots():
    d = license_gate.evaluate(
        _tulu3(intended_use="commercial", excluded_sources=["HuggingFaceH4/no_robots"])
    )
    assert d.allowed is False
    assert d.gated and d.unclear


def test_no_robots_is_marked_non_commercial():
    assert TULU3_COMPONENT_LICENSES["HuggingFaceH4/no_robots"]["status"] == "non_commercial"


# --- Nemotron v2 (single top-level license + per-row license field) --------- #
def _nemotron(**kw):
    return FineTuneConfig(dataset_repo_id=PRIMARY_SFT_DATASET, **kw)


def test_primary_dataset_is_nemotron():
    assert FineTuneConfig().dataset_repo_id == PRIMARY_SFT_DATASET


def test_nemotron_research_allowed_but_gated_noted():
    d = license_gate.evaluate(_nemotron(intended_use="research"))
    assert d.allowed is True
    assert d.gated == [PRIMARY_SFT_DATASET]
    assert "gated" in d.notes.lower()


def test_nemotron_commercial_requires_per_row_audit():
    # Top-level CC-BY-4.0 is permissive, but per-row `license` field is unaudited.
    d = license_gate.evaluate(_nemotron(intended_use="commercial"))
    assert d.allowed is False
    assert any("per-row" in u for u in d.unclear)


def test_nemotron_commercial_allowed_after_audit():
    d = license_gate.evaluate(
        _nemotron(intended_use="commercial", per_row_license_audited=True)
    )
    assert d.allowed is True


def test_unknown_dataset_is_blocked():
    d = license_gate.evaluate(FineTuneConfig(dataset_repo_id="someone/unknown-thing"))
    assert d.allowed is False
    assert d.unclear


# --- trainer wiring --------------------------------------------------------- #
def test_trainer_research_passes_gate_then_not_implemented():
    with pytest.raises(NotImplementedError):
        trainer.run_finetune(_nemotron(intended_use="research"))


def test_trainer_commercial_rejected_by_gate():
    with pytest.raises(PermissionError):
        trainer.run_finetune(_nemotron(intended_use="commercial"))


# --- architecture map ------------------------------------------------------- #
def test_architecture_covers_all_stages():
    report = architecture.architecture_report()
    assert [r["stage"] for r in report] == architecture.ARCHITECTURE_STAGES


def test_base_model_stage_is_honestly_missing():
    assert architecture.STAGE_STATUS["strong_base_model"].status == "missing"


def test_tool_calling_not_covered_by_primary_dataset():
    # The primary dataset has no function-calling subset; tool_use needs runtime.
    assert architecture.CAPABILITY_SOURCES["tool_use"].startswith("runtime")
    assert "tool_use" in architecture.capabilities_requiring_runtime_tools()


def test_research_and_web_needs_runtime_not_finetuning():
    runtime = architecture.capabilities_requiring_runtime_tools()
    for cap in ("web_research", "document_analysis", "research", "data_analysis"):
        assert cap in runtime


# --- benchmark stub never fabricates --------------------------------------- #
def test_benchmark_run_not_implemented():
    with pytest.raises(NotImplementedError):
        benchmark.run_benchmark(_nemotron(), label="base")


def test_benchmark_suites_include_reasoning_math_code_tools():
    s = benchmark.suites_for()
    for cap in ("difficult_reasoning", "mathematics", "coding", "tool_use"):
        assert cap in s and s[cap]


def test_benchmark_compare_deltas():
    a = benchmark.BenchmarkResult("base", "m", None, scores={"gsm8k": 0.40})
    b = benchmark.BenchmarkResult("post", "m", None, scores={"gsm8k": 0.55})
    assert benchmark.compare(a, b)["gsm8k"] == pytest.approx(0.15)


# --- isolation invariant ---------------------------------------------------- #
def _module_imports(path):
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
    return mods


def test_isolation_backend_does_not_import_finetuning():
    backend_dir = os.path.join(ROOT, "backend")
    for name in os.listdir(backend_dir):
        if name.endswith(".py"):
            for mod in _module_imports(os.path.join(backend_dir, name)):
                assert not mod.startswith("finetuning"), f"backend/{name} imports finetuning"


def test_isolation_finetuning_does_not_import_backend():
    ft_dir = os.path.join(ROOT, "finetuning")
    for name in os.listdir(ft_dir):
        if name.endswith(".py"):
            for mod in _module_imports(os.path.join(ft_dir, name)):
                assert not mod.startswith("backend"), f"finetuning/{name} imports backend"
