"""Fine-tuning entry point (STUB).

Wires the license gate in front of any (future) training run. The actual
training loop is not implemented — no torch/transformers backend exists yet and
it cannot run on the Vercel serverless deploy.
"""

from __future__ import annotations

from typing import Any, Dict

from .config import FineTuneConfig
from . import license_gate


def run_finetune(config: FineTuneConfig) -> Dict[str, Any]:
    """Validate licensing, then (in future) run supervised fine-tuning.

    Currently enforces the license gate and raises NotImplementedError so the
    scaffold cannot silently no-op. No model is downloaded or trained. A real
    backend should return ``decision.to_dict()`` alongside training metrics.
    """
    decision = license_gate.assert_allowed(config)
    raise NotImplementedError(
        "Fine-tuning backend is not implemented. License gate PASSED "
        f"(use={config.intended_use}, allowed={decision.allowed}). Implement a "
        "training loop using the extras in requirements-finetune.txt on a GPU host."
    )
