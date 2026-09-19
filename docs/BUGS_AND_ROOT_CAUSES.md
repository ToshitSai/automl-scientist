# AutoML Scientist — Bugs and Root Cause Analysis

## Overview
This document details the root causes and resolutions for the four primary issues identified in the master audit of the **AutoML Scientist** autonomous research engine.

---

## Bug 1: Stage Status Disconnect (COMPLETED showing while Baselines = 0, Literature = 0, Tree Search = 0)

### Root Cause
1. **Permissive Backend Transitions**: The research orchestrator previously marked stage strings in `agentLogs` without verifying whether underlying artifacts (baseline models, literature papers, hypothesis nodes, experiment scripts) actually existed in the database store.
2. **Fragile Frontend State Derivation**: The React frontend checked `agentLogs.some(l => l.agent === step.agent)` to mark steps as `done`, treating the mere presence of an log entry as stage completion.

### Solution Implemented
- **Database Gating**: Added `stageStates` to `database/store.py` (`research_question`, `literature_search`, `dataset_eda`, `baseline_training`, `hypothesis_generation`, `sandboxed_execution`, `error_diagnostics`, `research_report`).
- **Artifact Verification**: Updated `agents/orchestrator.py` with `verify_stage_artifacts()`. Stages transition to `COMPLETED` **only** after confirming that output artifacts exist in the database.
- **Frontend Refactoring**: Refactored `ResearchChatWorkspace.jsx` and `WorkspaceView.jsx` to render step badges directly from `project.stageStates` (`COMPLETED`, `RUNNING`, `NOT_CONFIGURED`, `FAILED`, `NOT_STARTED`).

---

## Bug 2: Unexpected Token 'A' JSON Parsing Error

### Root Cause
When backend exceptions or HTTP 500 errors occurred, FastAPI or the web server returned plain text or HTML error messages (e.g. `"A server error occurred"`). The frontend attempted to parse this using `response.json()` directly without inspecting `response.ok` or `content-type`, throwing a unhandled `SyntaxError: Unexpected token 'A'`.

### Solution Implemented
- **API Wrapper Safety (`src/api.js`)**: Updated `startResearch` and API helper methods to inspect `response.ok`. If `response.ok` is `false`, the helper reads `response.text()` first, attempts JSON parsing, and falls back to a clean error object:
  ```json
  {
    "success": false,
    "error": "Dataset file missing. Please upload a dataset file (.csv or .parquet) to proceed with autonomous research."
  }
  ```
- **Backend Error Response Gating**: Wrapped endpoint logic in `try/except` blocks returning structured `HTTPException(status_code=400/500, detail=...)`.

---

## Bug 3: Heuristic Fallback vs LLM Autonomous Provider Disconnect

### Root Cause
The engine reported `"Engine: Heuristic / Rule-based"` indiscriminately, creating ambiguity as to whether an actual LLM provider was active or a rule-synthesis fallback was executing.

### Solution Implemented
- **Engine Provider Selection**: Added explicit LLM provider selection (`OpenAI GPT-4o`, `Claude 3.5 Sonnet`, `Ollama Local`, `Heuristic / Rule-based`).
- **Settings Endpoint (`GET /api/settings`)**: Exposes whether `OPENAI_API_KEY` is present and whether Docker daemon is active.
- **Explicit Status Display**: If an LLM is unconfigured, the UI clearly displays `NOT CONFIGURED` or `Heuristic Fallback`, preventing simulated equivalence.

---

## Bug 4: Serverless HTTP Request Timeout for Long-Running ML Jobs

### Root Cause
Deploying long-running ML training loops (which can take minutes or hours) directly inside a serverless HTTP endpoint causes serverless platforms (such as Vercel) to terminate requests after 10–60 seconds, resulting in dropped connections and abandoned state.

### Solution Implemented
- **Asynchronous Worker Handoff**: `POST /api/research` initializes the project record in the store (`status: "QUEUED"`) and returns the `project_id` immediately (<100ms).
- **Decoupled Research Thread**: The research orchestrator executes in a background worker thread (`threading.Thread`).
- **Server-Sent Events (SSE)**: The frontend subscribes to `GET /api/projects/{id}/stream` for real-time telemetry, log updates, and stage state transitions without blocking HTTP request threads.
