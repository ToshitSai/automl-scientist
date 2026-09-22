"""Target post-training architecture and honest per-stage status.

The owner's directive: build the assistant as

    Strong Base Model
      -> General Instruction/Reasoning Training
      -> Tool Calling
      -> Web Search
      -> RAG
      -> Python/Code Execution
      -> Research Tools
      -> Verification
      -> Final Answer

supporting: normal conversation, difficult reasoning, mathematics, coding, data
analysis, research, document analysis, web research, tool use, multi-step tasks.

This module records that pipeline as data plus an HONEST status of each stage in
the *current* repository. It does not train or serve anything. Key truth: this
project is an API-backed research agent — there is no locally served base model,
no GPU training/serving backend, so the post-training stages are scaffold-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .config import ARCHITECTURE_STAGES, PRIMARY_SFT_DATASET


@dataclass
class StageStatus:
    stage: str
    status: str        # "implemented" | "partial" | "stub" | "missing"
    where: str         # where it lives (or should) in the repo
    note: str


# Honest mapping as of 2026-09-22. Nothing here claims more than exists.
STAGE_STATUS: Dict[str, StageStatus] = {
    "strong_base_model": StageStatus(
        "strong_base_model", "missing",
        "finetuning/config.py:BASE_MODEL_CANDIDATES",
        "No base model is served. backend/llm.py calls third-party APIs only. "
        "An 8B instruct model is too weak for hard reasoning; pick from the "
        "reasoning-capable candidates after benchmarking.",
    ),
    "general_instruction_reasoning_training": StageStatus(
        "general_instruction_reasoning_training", "stub",
        "finetuning/{trainer,dataset_loader}.py",
        f"Scaffold only; no training backend. Primary corpus = {PRIMARY_SFT_DATASET} "
        "(chat/math/code/stem/multilingual with a `reasoning` field).",
    ),
    "tool_calling": StageStatus(
        "tool_calling", "missing",
        "(needs new module + tool-call data)",
        "NOT covered by the primary dataset (no function-calling subset). Requires "
        "separate tool-call training data AND a runtime that executes tools.",
    ),
    "web_search": StageStatus(
        "web_search", "missing",
        "(needs new tool)",
        "No web-search tool exists. Fine-tuning must NOT be used as a replacement "
        "for live web search.",
    ),
    "rag": StageStatus(
        "rag", "missing",
        "(needs vector store + retriever)",
        "No retrieval-augmented generation pipeline. Fine-tuning is not a substitute "
        "for RAG over user documents.",
    ),
    "python_code_execution": StageStatus(
        "python_code_execution", "partial",
        "sandbox/, backend/trainer.py",
        "Sandboxed execution exists for research training scripts; not yet exposed "
        "as a model-driven tool/calculator.",
    ),
    "research_tools": StageStatus(
        "research_tools", "implemented",
        "backend/hf_datasets.py, literature_search.py, error_analyzer.py",
        "Dataset discovery/inspection/download + literature search + error analysis "
        "are real and tested. These belong to the research system, kept SEPARATE "
        "from model fine-tuning.",
    ),
    "verification": StageStatus(
        "verification", "partial",
        "backend/error_analyzer.py, tests/",
        "Result verification exists for the research pipeline; no general "
        "self-verification step in a model answer path.",
    ),
    "final_answer": StageStatus(
        "final_answer", "implemented",
        "backend/report_generator.py, intent_router.py",
        "Report generation + intent routing produce the user-facing answer.",
    ),
}

# Capability -> which post-training split / mechanism is expected to provide it.
# Used to make explicit that fine-tuning data alone does NOT provide tool-backed
# capabilities (web research, document analysis over new docs, verified facts).
CAPABILITY_SOURCES: Dict[str, str] = {
    "normal_conversation": f"{PRIMARY_SFT_DATASET}:chat",
    "difficult_reasoning": f"{PRIMARY_SFT_DATASET}:stem (+ strong reasoning base model)",
    "mathematics": f"{PRIMARY_SFT_DATASET}:math",
    "coding": f"{PRIMARY_SFT_DATASET}:code",
    "multilingual": f"{PRIMARY_SFT_DATASET}:multilingual_*",
    "data_analysis": "runtime: sandbox python/code execution (NOT fine-tuning alone)",
    "research": "runtime: backend research_tools (NOT fine-tuning alone)",
    "document_analysis": "runtime: RAG over the given documents (NOT fine-tuning alone)",
    "web_research": "runtime: web_search tool (NOT fine-tuning alone)",
    "tool_use": "runtime + separate tool-call training data (NOT in primary dataset)",
    "multi_step_tasks": "runtime: agent loop over tools + verification",
}


def architecture_report() -> List[Dict]:
    """Return the ordered stage statuses (for docs / a future status endpoint)."""
    return [
        {
            "stage": s,
            "status": STAGE_STATUS[s].status,
            "where": STAGE_STATUS[s].where,
            "note": STAGE_STATUS[s].note,
        }
        for s in ARCHITECTURE_STAGES
    ]


def capabilities_requiring_runtime_tools() -> List[str]:
    """Capabilities that fine-tuning ALONE cannot deliver (need tools/RAG/search)."""
    return sorted(c for c, src in CAPABILITY_SOURCES.items() if src.startswith("runtime"))
