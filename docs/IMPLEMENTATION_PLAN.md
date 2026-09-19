# AutoML Scientist — Implementation Plan

## Development Phases

### Phase 0 — Audit & System Documentation
- [x] Perform comprehensive audit across architecture, APIs, data store, LLM integration, sandboxing, and frontend.
- [x] Create `docs/CURRENT_STATE.md`.
- [x] Create `docs/ARCHITECTURE.md`.
- [x] Create `docs/IMPLEMENTATION_PLAN.md`.
- [x] Create `docs/UPSTREAM_ATTRIBUTION.md`.

### Phase 1 — Single Real End-to-End Execution Milestone
- [x] Real Pandas dataset analysis.
- [x] Real Scikit-learn / XGBoost baseline training.
- [x] LLM hypothesis & Python script synthesis.
- [x] Sandboxed execution with stdout/stderr/metrics logging.
- [x] Statistical error analysis.
- [x] Markdown report generation.

### Phase 2 — Multi-Step Autonomous Loop & Control System
- [x] Iterative experimentation loop up to `max_experiments`.
- [x] Error analysis feedback into next hypothesis formulation.
- [x] `PAUSE`, `RESUME`, and `STOP` control signals.
- [x] Server-Sent Events (SSE) streaming endpoint `/api/projects/{id}/stream`.
- [x] Multi-format report downloads (`.md` and `.json`).

### Phase 3 — Advanced Statistical Analysis & Model Tracking
- [x] Bootstrap confidence intervals for metric scores.
- [x] MLflow compatibility tracking module.
- [x] Advanced fraud-specific feature engineering modules.

### Phase 4 — Sakana Chat Style Interface & User Experience
- [x] Left sidebar (~270px) with logo, search, project history by recency (`TODAY`, `YESTERDAY`, `EARLIER`), and system status.
- [x] Prompt composer with CSV/Parquet file attachment, model selection, budget selection, and send controls.
- [x] Conversational workspace feed with user query bubble, inline progress steps, live telemetry stream, interactive artifact cards (EDA, Baselines, Sandbox Console Logs, Error Analysis, Report).
- [x] Interactive header controls (`Pause`, `Resume`, `Stop`).
- [x] Verified Vercel deployment.
