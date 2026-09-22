"""Benchmark harness for the post-training pipeline (STUB).

Owner directive: "Benchmark the model before and after every training change."

This module DEFINES the evaluation suites and the before/after workflow, but it
does NOT execute them and NEVER fabricates scores. Running real benchmarks
requires a served model + the eval dependencies (lm-eval-harness and friends) on
a GPU host — none of which exist in this repo yet. Until then ``run_benchmark``
raises NotImplementedError rather than returning invented numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import FineTuneConfig

# Capability -> representative public benchmark suite(s). These are the standard
# instruments for the capabilities the assistant must support; they are named so
# a future backend wires them up, not run here.
BENCHMARK_SUITES: Dict[str, List[str]] = {
    "general_knowledge": ["mmlu", "mmlu_pro"],
    "difficult_reasoning": ["gpqa_diamond", "bbh", "arc_challenge"],
    "mathematics": ["gsm8k", "math", "aime"],
    "coding": ["humaneval", "mbpp", "livecodebench"],
    "instruction_following": ["ifeval", "alpaca_eval"],
    "tool_use": ["bfcl", "tau_bench"],         # function/tool calling
    "multilingual": ["mgsm", "xcopa"],
    "safety": ["wildguard", "toxigen"],
}


@dataclass
class BenchmarkResult:
    label: str                 # "base" | "post_train" | arbitrary tag
    base_model: str
    dataset_repo_id: Optional[str]
    scores: Dict[str, float] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "label": self.label,
            "base_model": self.base_model,
            "dataset_repo_id": self.dataset_repo_id,
            "scores": self.scores,
            "notes": self.notes,
        }


def suites_for(capabilities: Optional[List[str]] = None) -> Dict[str, List[str]]:
    """Return the benchmark suites to run (all, or filtered to capabilities)."""
    if not capabilities:
        return dict(BENCHMARK_SUITES)
    return {c: BENCHMARK_SUITES[c] for c in capabilities if c in BENCHMARK_SUITES}


def run_benchmark(config: FineTuneConfig, label: str = "base") -> BenchmarkResult:
    """STUB — run the suites against a served model and return REAL scores.

    Not implemented. A future backend must:
      1. serve ``config.base_model`` (or the fine-tuned checkpoint) on a GPU host;
      2. run each suite in ``suites_for()`` via lm-eval-harness / native runners;
      3. return only measured scores — never defaults, guesses, or placeholders.

    To satisfy "before and after every training change", call this with
    label="base" on the untrained model and label="post_train" on the checkpoint,
    then diff the two BenchmarkResult.score dicts.
    """
    raise NotImplementedError(
        "Benchmark backend is not wired. No model is served in this repo and the "
        "serverless deploy cannot run one. Refusing to fabricate scores — install "
        "the eval stack on a GPU host and implement this before claiming any "
        "before/after result."
    )


def compare(before: BenchmarkResult, after: BenchmarkResult) -> Dict[str, float]:
    """Per-suite delta (after - before). Only valid on REAL measured results."""
    keys = set(before.scores) | set(after.scores)
    return {k: after.scores.get(k, float("nan")) - before.scores.get(k, float("nan")) for k in sorted(keys)}
