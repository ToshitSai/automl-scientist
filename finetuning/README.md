# finetuning/ — Model Fine-Tuning (STUB)

Scaffold for LLM **supervised fine-tuning / post-training**, kept deliberately
separate from the autonomous-research / tool-use system.

## Isolation rule

| Package | Purpose | Data |
|---|---|---|
| `backend.*` | Classical-ML research, dataset discovery + recommendation | TABULAR (sklearn/xgboost) |
| `finetuning/` | LLM post-training | Instruction/reasoning corpora |

`finetuning/` must **never** be imported by `backend.hf_datasets` or the research
orchestrator (enforced by an AST test). Post-training data must not be surfaced
in the research/tool-use discovery flow.

## Primary dataset

**`nvidia/Nemotron-Post-Training-Dataset-v2`** (designated 2026-09-22).
- License **CC-BY-4.0** (commercial-OK with attribution); **gated: auto**
  (accept terms + `HF_TOKEN`); 1M–10M rows; parquet.
- Splits: `chat`, `math`, `code`, `stem`, `multilingual_{ja,de,it,es,fr}`.
- Row schema includes a **`reasoning`** field (CoT) and a **per-row `license`** field.
- ⚠️ **No function/tool-calling subset** — the "Tool Calling" stage is NOT taught
  by this dataset and must come from separate data + the agent runtime.

`allenai/tulu-3-sft-mixture` is retained as an **alternate** (its top-level ODC-By
tag is not binding: `HuggingFaceH4/no_robots` is CC-BY-NC-4.0 → commercial blocker).

## Contents

- `config.py` — `FineTuneConfig`, dataset license profiles, architecture stages, base-model candidates.
- `license_gate.py` — dataset-aware allow/block (mixture = most-restrictive component; single = top license + per-row audit + gating).
- `dataset_loader.py` — live Hub metadata (works) + SFT streaming stub (`NotImplementedError`).
- `architecture.py` — the 9-stage pipeline + honest per-stage status in this repo + capability→source map.
- `benchmark.py` — before/after benchmark suites (defined) + `run_benchmark` stub that **refuses to fabricate scores**.
- `trainer.py` — license-gated training entry point (`NotImplementedError`).

## Target architecture

```
Strong Base Model → General Instruction/Reasoning Training → Tool Calling
→ Web Search → RAG → Python/Code Execution → Research Tools → Verification
→ Final Answer
```

Must support: conversation, difficult reasoning, math, coding, data analysis,
research, document analysis, web research, tool use, multi-step tasks.

**Fine-tuning is NOT a replacement for tools.** Web search, RAG, code execution,
calculators, and verified facts are runtime capabilities (`architecture.py`
lists which capabilities require the runtime, not training data).

## Base-model guidance

No base model is served by this project today (`backend/llm.py` calls third-party
APIs). The legacy placeholder `Llama-3.1-Tulu-3-8B` is **too weak** for hard
reasoning. Reasoning-capable candidates are listed in
`config.BASE_MODEL_CANDIDATES`; the final choice must be settled by
`benchmark.run_benchmark()` before/after training — **not asserted without
measured scores**.

## License verdict

| Dataset | Research | Commercial |
|---|---|---|
| Nemotron-Post-Training-Dataset-v2 | ✅ allowed (gated: accept terms + token) | ⚠️ allowed only after `per_row_license_audited=True` |
| tulu-3-sft-mixture | ✅ allowed (attribution) | ❌ blocked (no_robots CC-BY-NC; gated + unclear sources) |

## Status

Stub only — **no training/serving/benchmark backend**. Implementing it requires
the extras in `requirements-finetune.txt` (torch/transformers/datasets/trl/peft/
accelerate + lm-eval-harness) on a GPU host; it cannot run on the Vercel
serverless deploy. Heavy deps are kept out of `requirements.txt` and imported
lazily.
