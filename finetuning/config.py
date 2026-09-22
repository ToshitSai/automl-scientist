"""Configuration for the (stub) fine-tuning module.

Zero third-party dependencies — stdlib only, matching the rest of the project.
The heavy training stack (torch/transformers/datasets) is deliberately NOT
imported here; see ``requirements-finetune.txt`` for the optional extras a
future training backend would need.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

# --------------------------------------------------------------------------- #
# Datasets
# --------------------------------------------------------------------------- #
# PRIMARY general post-training corpus (designated 2026-09-22).
PRIMARY_SFT_DATASET = "nvidia/Nemotron-Post-Training-Dataset-v2"
# Earlier general instruction-tuning corpus; kept as an alternate, NOT primary.
ALTERNATE_SFT_DATASET = "allenai/tulu-3-sft-mixture"
# Back-compat alias.
DEFAULT_SFT_DATASET = PRIMARY_SFT_DATASET

# --------------------------------------------------------------------------- #
# Component license map for allenai/tulu-3-sft-mixture.
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
TULU3_COMPONENT_LICENSES: Dict[str, Dict[str, str]] = {
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

# Back-compat alias used by older imports/tests.
MIXTURE_COMPONENT_LICENSES = TULU3_COMPONENT_LICENSES

# --------------------------------------------------------------------------- #
# Per-dataset license profiles (inspected on the HF Hub, 2026-09-22).
#
# kind:
#   "mixture" -> usable license = MOST RESTRICTIVE component (see components).
#   "single"  -> one top-level license; but watch the flags below.
#
# Flags that can still block commercial use even with a permissive top license:
#   gated               -> access approval / login required before download
#   per_row_license     -> every row carries its own `license` field; a
#                          per-row audit is required before commercial use
#   no_tool_call_subset -> dataset does not teach function/tool calling
# --------------------------------------------------------------------------- #
DATASET_LICENSE_PROFILES: Dict[str, Dict] = {
    PRIMARY_SFT_DATASET: {
        "kind": "single",
        "license": "cc-by-4.0",
        "gated": True,               # gated: auto (Company + Institutional Email)
        "per_row_license": True,     # schema has a `license` column on each row
        "no_tool_call_subset": True, # splits: chat/math/code/stem/multilingual only
        "splits": ["chat", "math", "code", "stem",
                   "multilingual_ja", "multilingual_de", "multilingual_it",
                   "multilingual_es", "multilingual_fr"],
        "components": None,
    },
    ALTERNATE_SFT_DATASET: {
        "kind": "mixture",
        "license": "odc-by",         # top-level tag is NOT binding for a mixture
        "gated": False,
        "per_row_license": False,
        "no_tool_call_subset": False,
        "splits": None,
        "components": TULU3_COMPONENT_LICENSES,
    },
}

# --------------------------------------------------------------------------- #
# Post-training architecture (the target pipeline) and base-model guidance.
# These are design constants for the stub; nothing here trains or serves yet.
# --------------------------------------------------------------------------- #
ARCHITECTURE_STAGES: List[str] = [
    "strong_base_model",
    "general_instruction_reasoning_training",
    "tool_calling",
    "web_search",
    "rag",
    "python_code_execution",
    "research_tools",
    "verification",
    "final_answer",
]

# Reasoning-capable base-model candidates for the hard-reasoning + math + code +
# agentic profile. NOT benchmarked here — selection must be settled by
# benchmark.run_benchmark() once a GPU training/serving backend exists. The
# previous placeholder (Llama-3.1-Tulu-3-8B) is considered TOO WEAK for this.
BASE_MODEL_CANDIDATES: List[str] = [
    "Qwen/Qwen3-32B",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
    "meta-llama/Llama-3.3-70B-Instruct",
    "nvidia/Llama-3.1-Nemotron-Ultra-253B-v1",
]
LEGACY_WEAK_BASE_MODEL = "allenai/Llama-3.1-Tulu-3-8B"


@dataclass
class FineTuneConfig:
    """Configuration for a supervised fine-tuning run (stub)."""

    dataset_repo_id: str = PRIMARY_SFT_DATASET
    base_model: str = BASE_MODEL_CANDIDATES[0]
    output_dir: str = "models/finetuned"

    # Intended use drives the license gate. "commercial" is blocked unless the
    # dataset's licensing conditions are satisfied.
    intended_use: str = "research"  # "research" | "commercial"

    # For mixtures: sources to exclude (e.g. drop "HuggingFaceH4/no_robots").
    excluded_sources: List[str] = field(default_factory=list)
    # For datasets with a per-row `license` field: set True once a per-row audit
    # has confirmed every retained row is cleared for the intended use.
    per_row_license_audited: bool = False

    # Hyperparameters — placeholders for a future backend.
    num_epochs: int = 2
    learning_rate: float = 5e-6
    per_device_batch_size: int = 1
    max_seq_len: int = 4096

    def profile(self) -> Optional[Dict]:
        return DATASET_LICENSE_PROFILES.get(self.dataset_repo_id)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_env(cls) -> "FineTuneConfig":
        """Build a config from optional environment variables (all defaulted)."""
        return cls(
            dataset_repo_id=os.environ.get("FT_DATASET", PRIMARY_SFT_DATASET),
            base_model=os.environ.get("FT_BASE_MODEL", BASE_MODEL_CANDIDATES[0]),
            output_dir=os.environ.get("FT_OUTPUT_DIR", "models/finetuned"),
            intended_use=os.environ.get("FT_INTENDED_USE", "research"),
        )
