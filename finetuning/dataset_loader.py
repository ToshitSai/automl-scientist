"""Dataset loading for the fine-tuning mixture (STUB).

Metadata retrieval works today (stdlib urllib against the HF Hub API). Actual
streaming/tokenization is NOT implemented — it requires ``datasets`` +
``transformers`` and a GPU host, neither of which is available on the Vercel
serverless deploy. Those heavy deps live in ``requirements-finetune.txt`` and
must be imported lazily (inside functions), never at module top level.

This module is isolated from ``backend.hf_datasets`` on purpose: that module
serves the research/tool-use discovery flow over TABULAR data and must not
learn about instruction-tuning corpora.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict

from .config import FineTuneConfig

_HF_API = "https://huggingface.co/api/datasets"
_USER_AGENT = "AutoML-Scientist/2.0 (finetuning stub)"


def fetch_metadata(config: FineTuneConfig) -> Dict[str, Any]:
    """Return live Hub metadata for the configured dataset (no fabrication)."""
    url = f"{_HF_API}/{config.dataset_repo_id}"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {
        "id": data.get("id"),
        "license": (data.get("cardData") or {}).get("license"),
        "gated": data.get("gated"),
        "downloads": data.get("downloads"),
        "lastModified": data.get("lastModified"),
        "tags": data.get("tags", []),
    }


def load_sft_dataset(config: FineTuneConfig):
    """STUB — stream and tokenize the SFT mixture into train/eval splits.

    Not implemented. A future backend should:
      1. run ``license_gate.assert_allowed(config)`` first;
      2. import ``datasets`` lazily and stream ``config.dataset_repo_id``;
      3. apply ``config.excluded_sources`` when loading the mixture;
      4. tokenize with the base model's chat template up to ``max_seq_len``.
    """
    raise NotImplementedError(
        "SFT dataset loading is not wired yet. This is a scaffold; install the "
        "extras in requirements-finetune.txt and implement a training backend "
        "on a GPU host (cannot run on Vercel serverless)."
    )
