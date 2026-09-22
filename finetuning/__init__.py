"""AutoML Scientist — Model Fine-Tuning (STUB).

This package is intentionally SEPARATE from the autonomous-research /
tool-use system. It must never be imported by ``backend.hf_datasets`` or the
research orchestrator (``backend.llm`` / ``backend.trainer``).

Scope:
  * ``backend.*``  -> classical ML research on TABULAR data (sklearn/xgboost),
                      dataset discovery + recommendation. UNRELATED to this pkg.
  * ``finetuning`` -> LLM supervised fine-tuning on instruction corpora such as
                      ``allenai/tulu-3-sft-mixture``.

The dataset ``allenai/tulu-3-sft-mixture`` is the initial GENERAL
instruction-tuning corpus. It is NOT the data that teaches autonomous
research, and it must NOT be surfaced in the research/tool-use dataset flow.

This is a scaffold only: config + license gate + dataset/trainer stubs. No
training backend is wired yet (would require torch/transformers/datasets and a
GPU host — it cannot run on the Vercel serverless deploy). See README.md.
"""

__all__ = [
    "config",
    "license_gate",
    "dataset_loader",
    "architecture",
    "benchmark",
    "trainer",
]
