"""Configuration for the (stub) fine-tuning module.

Zero third-party dependencies — stdlib only, matching the rest of the project.
The heavy training stack (torch/transformers/datasets) is deliberately NOT
imported here; see ``requirements-finetune.txt`` for the optional extras a
future training backend would need.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List

# The initial GENERAL instruction-tuning corpus designated by the project owner.
# Kept separate from the autonomous-research / tool-use dataset flow.
DEFAULT_SFT_DATASET = "allenai/tulu-3-sft-mixture"

# --------------------------------------------------------------------------- #
# Component license map for the tulu-3-sft-mixture sources.
#
# Captured from a manual inspection of the Hugging Face Hub on 2026-09-22.
# A mixture's usable license is bounded by its MOST RESTRICTIVE component, so
# the top-level ODC-By tag on the mixture is NOT sufficient for commercial use.
#
# status:
#   "commercial_ok"      -> permissive, attribution required
#   "non_commercial"     -> HARD BLOCKER for commercial use
#   "gated"              -> access approval required before download
#   "unclear"            -> no explicit tag / derivative; needs clearance
# --------------------------------------------------------------------------- #
MIXTURE_COMPONENT_LICENSES: Dict[str, Dict[str, str]] = {
    "HuggingFaceH4/oasst1": {"license": "apache-2.0", "status": "commercial_ok"},
    "AI-MO/NuminaMath-TIR": {"license": "apache-2.0", "status": "commercial_ok"},
    "CohereForAI/aya_dataset": {"license": "apache-2.0", "status": "commercial_ok"},
    "teknium/evol-codealpaca-v1": {"license": "apache-2.0", "status": "commercial_ok"},
    "allenai/tulu-3-hard-coded": {"license": "cc-by-4.0", "status": "commercial_ok"},
    "Table-GPT": {"license": "mit", "status": "commercial_ok"},
    "AI2/WildChat-1M": {"license": "odc-by", "status": "commercial_ok"},
    "allenai/SciRIFF": {"license": "odc-by", "status": "commercial_ok"},
    "allenai/tulu-3-sft-personas-instruction-following": {"license": "odc-by", "status": "commercial_ok"},
    "allenai/coconot": {"license": "odc-by", "status": "commercial_ok"},
    "allenai/tulu-3-sft-personas-code": {"license": "odc-by", "status": "commercial_ok"},
    # Non-commercial blocker.
    "HuggingFaceH4/no_robots": {"license": "cc-by-nc-4.0", "status": "non_commercial"},
    # Gated — require access approval.
    "allenai/wildguardmix": {"license": "odc-by", "status": "gated"},
    "allenai/wildjailbreak": {"license": "odc-by", "status": "gated"},
    # No explicit tag / derivative — needs clearance.
    "ai2-adapt-dev/flan_v2_converted": {"license": "unknown (FLAN v2 derivative)", "status": "unclear"},
    "allenai/tulu-3-sft-personas-math-grade": {"license": "unknown", "status": "unclear"},
    "allenai/tulu-3-personas-math": {"license": "unknown (not publicly resolvable)", "status": "unclear"},
    "allenai/tulu-3-personas-algebra": {"license": "unknown (not publicly resolvable)", "status": "unclear"},
}


@dataclass
class FineTuneConfig:
    """Configuration for a supervised fine-tuning run (stub)."""

    dataset_repo_id: str = DEFAULT_SFT_DATASET
    base_model: str = "allenai/Llama-3.1-Tulu-3-8B"
    output_dir: str = "models/finetuned"

    # Intended use drives the license gate. "commercial" is blocked unless the
    # non-commercial / gated / unclear components are excluded or cleared.
    intended_use: str = "research"  # "research" | "commercial"

    # Sources to exclude from the mixture (e.g. drop "HuggingFaceH4/no_robots"
    # to remove the CC-BY-NC blocker for a commercial build).
    excluded_sources: List[str] = field(default_factory=list)

    # Hyperparameters — placeholders for a future backend.
    num_epochs: int = 2
    learning_rate: float = 5e-6
    per_device_batch_size: int = 1
    max_seq_len: int = 4096

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_env(cls) -> "FineTuneConfig":
        """Build a config from optional environment variables (all defaulted)."""
        return cls(
            dataset_repo_id=os.environ.get("FT_DATASET", DEFAULT_SFT_DATASET),
            base_model=os.environ.get("FT_BASE_MODEL", "allenai/Llama-3.1-Tulu-3-8B"),
            output_dir=os.environ.get("FT_OUTPUT_DIR", "models/finetuned"),
            intended_use=os.environ.get("FT_INTENDED_USE", "research"),
        )
