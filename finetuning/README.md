# finetuning/ — Model Fine-Tuning (STUB)

Scaffold for LLM **supervised fine-tuning**, kept deliberately separate from the
autonomous-research / tool-use system.

## Isolation rule

| Package | Purpose | Data |
|---|---|---|
| `backend.*` | Classical-ML research, dataset discovery + recommendation | TABULAR (sklearn/xgboost) |
| `finetuning/` | LLM supervised fine-tuning | Instruction corpora (e.g. tulu-3-sft-mixture) |

`finetuning/` must **never** be imported by `backend.hf_datasets` or the
research orchestrator. `allenai/tulu-3-sft-mixture` is the initial *general
instruction-tuning* dataset — it is **not** the data that teaches autonomous
research and must not be surfaced in the research/tool-use discovery flow.

## Contents

- `config.py` — `FineTuneConfig` dataclass + the component license map.
- `license_gate.py` — allow/block decision bounded by the most restrictive component.
- `dataset_loader.py` — live Hub metadata (works) + SFT streaming stub (`NotImplementedError`).
- `trainer.py` — license-gated training entry point (`NotImplementedError`).

## License verdict (inspected 2026-09-22)

The mixture's top-level **ODC-By** tag does **not** make it commercial-safe; the
binding constraint is the most restrictive component.

- ❌ **Blocker:** `HuggingFaceH4/no_robots` — **CC-BY-NC-4.0** (non-commercial).
- 🔒 **Gated (access approval):** `allenai/wildguardmix`, `allenai/wildjailbreak`.
- ❓ **Unclear (needs clearance):** `ai2-adapt-dev/flan_v2_converted` (FLAN v2 derivative),
  `allenai/tulu-3-sft-personas-math-grade`, `allenai/tulu-3-personas-math`,
  `allenai/tulu-3-personas-algebra`.
- ✅ Everything else is permissive (Apache-2.0 / MIT / CC-BY-4.0 / ODC-By).

`license_gate.evaluate(FineTuneConfig(intended_use="commercial"))` returns
`allowed=False` until the above are excluded or cleared. Research use is allowed
with attribution.

## Status

Stub only — **no training backend**. Implementing it requires the extras in
`requirements-finetune.txt` (torch/transformers/datasets/trl/peft/accelerate) on
a GPU host; it cannot run on the Vercel serverless deploy. Heavy deps are kept
out of `requirements.txt` and imported lazily.
