"""Tests for the isolated finetuning/ stub: license gate + isolation invariant."""

import ast
import os

import pytest

from finetuning.config import FineTuneConfig, MIXTURE_COMPONENT_LICENSES
from finetuning import license_gate, trainer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_research_use_allowed():
    d = license_gate.evaluate(FineTuneConfig(intended_use="research"))
    assert d.allowed is True


def test_commercial_use_blocked_by_non_commercial_component():
    d = license_gate.evaluate(FineTuneConfig(intended_use="commercial"))
    assert d.allowed is False
    assert "HuggingFaceH4/no_robots" in d.blocking


def test_commercial_still_blocked_after_dropping_no_robots():
    # Gated + unclear-license components remain, so commercial stays blocked.
    d = license_gate.evaluate(
        FineTuneConfig(intended_use="commercial", excluded_sources=["HuggingFaceH4/no_robots"])
    )
    assert d.allowed is False
    assert d.gated and d.unclear


def test_assert_allowed_raises_for_commercial():
    with pytest.raises(PermissionError):
        license_gate.assert_allowed(FineTuneConfig(intended_use="commercial"))


def test_trainer_enforces_gate_then_not_implemented():
    # Research passes the gate but the training backend is not wired yet.
    with pytest.raises(NotImplementedError):
        trainer.run_finetune(FineTuneConfig(intended_use="research"))
    # Commercial is rejected by the gate before reaching training.
    with pytest.raises(PermissionError):
        trainer.run_finetune(FineTuneConfig(intended_use="commercial"))


def test_no_robots_is_marked_non_commercial():
    assert MIXTURE_COMPONENT_LICENSES["HuggingFaceH4/no_robots"]["status"] == "non_commercial"


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
