# AutoML Scientist — Current System State Audit

## Overview
This document audits the current state of the **AutoML Scientist** codebase, categorizing implemented features, backend capabilities, real data handling, and missing components.

---

## Audit Matrix (A–L)

### A. Current Architecture
- **Web Layer**: Fast REST APIs built with Python FastAPI (`backend/main.py`), served with CORS support.
- **Client Layer**: React + Vite frontend structured around a two-column Sakana Chat style interface (`src/App.jsx`).
- **Engine Layer**: Asynchronous background worker threads (`agents/orchestrator.py`) executing dataset analysis, baseline training, literature search, hypothesis synthesis, sandboxed experiment execution, error diagnostics, and report generation.
- **Persistence Layer**: Thread-safe JSON database (`database/store.py`) writing to `database/research_store.json`.
- **Workspace Layer**: File-backed experiment directories (`experiments/<project_id>/<exp_id>/`) saving `script.py`, `stdout.log`, `stderr.log`, and `metrics.json`.

### B. Existing Functionality
- **Dataset Analysis (`backend/dataset_analyzer.py`)**: Real Pandas inspection calculating row counts, column counts, missing values, duplicate rows, target candidate detection, task type (classification/regression), class distribution percentages, feature skewness, detected data issues, recommended metrics.
- **Baseline Training (`backend/trainer.py`)**: Real `scikit-learn` and `xgboost` model fitting (Logistic Regression, Random Forest, XGBoost/Gradient Boosting, MLP), computing empirical F1, Accuracy, Precision, Recall, PR-AUC, ROC-AUC, R2, RMSE, MAE.
- **Literature Search (`backend/literature_search.py`)**: Live query against Semantic Scholar REST API (`https://api.semanticscholar.org`).
- **LLM Synthesis & Fallback (`backend/llm.py`)**: Connects to OpenAI API when `OPENAI_API_KEY` is present; falls back to structured rule synthesis for Python code generation when unconfigured.
- **Sandbox Execution (`sandbox/runner.py`)**: Executes generated Python experiment scripts in isolated process environments (or Docker container when daemon is available), enforcing execution timeouts and capturing console logs.
- **Statistical Error Analysis (`backend/error_analyzer.py`)**: False Positive / False Negative counts, correlation of numerical features with prediction error vector, quantile slice metrics.
- **Report Generation (`backend/report_generator.py`)**: Renders scientific Markdown research reports summarizing research objectives, dataset EDA, baseline benchmarks, experiment nodes, error analysis, limitations, and future work.

### C. Hardcoded / Demo Data Status
- **Purged**: `database/research_store.json` is clean (`0` pre-populated projects). Unconfigured installations cleanly display `"No research yet"`, `"LLM not configured"`, or `"Process Sandbox (Subprocess isolation)"`.

### D. Existing Backend APIs
- `GET /api/settings`: Fetch system settings and Docker daemon availability.
- `POST /api/settings`: Update settings (LLM provider, budget, max experiments).
- `GET /api/projects`: List all research projects.
- `POST /api/research`: Start new research run with objective and optional uploaded CSV/Parquet file.
- `GET /api/projects/{id}`: Fetch details for a specific project.
- `POST /api/projects/{id}/control`: Send control signals (`RUN`, `PAUSE`, `STOP`).
- `GET /api/projects/{id}/stream`: Server-Sent Events (SSE) streaming endpoint for live research events and logs.
- `GET /api/projects/{id}/dataset`: Fetch dataset EDA report.
- `GET /api/projects/{id}/baselines`: Fetch baseline benchmark results.
- `GET /api/projects/{id}/tree`: Fetch experiment tree search nodes.
- `GET /api/projects/{id}/error-analysis`: Fetch statistical error diagnostics.
- `GET /api/projects/{id}/literature`: Fetch literature papers.
- `GET /api/projects/{id}/report`: Fetch Markdown scientific report.
- `GET /api/projects/{id}/report/download`: Download report in `.md` or `.json` format.

### E. Existing LLM Integration
- Supports OpenAI GPT-4o / GPT-4o-mini via `backend/llm.py`.
- Supports fallback code synthesis when no API key is specified.

### F. Existing ML Execution
- Genuine model fitting using Scikit-learn and XGBoost. No fake metrics or hardcoded scores.

### G. Existing Docker Execution
- Probes `docker info` via subprocess. Accurately reports `Process Sandbox` when local Docker daemon is inactive.

### H. Existing Database
- File-based JSON database with thread locks (`database/store.py`).

### I. Existing Experiment Tracking
- Disk-based experiment workspaces storing scripts, logs, metrics JSON, and tree nodes.

### J. Existing Autonomous Loop
- Multi-step iterative loop executing up to `max_experiments` or until time budget is reached, feeding error analysis from Experiment $N$ into the hypothesis for Experiment $N+1$. Supports `PAUSE`, `RESUME`, and `STOP` controls.

### K. Missing Components
1. PostgreSQL / SQLite schema migration for production persistence.
2. MLflow tracking server integration.
3. User Authentication & JWT multi-user isolation.
4. Advanced statistical confidence interval testing (bootstrap / paired tests).
5. PDF export for research reports.

### L. Recommended Implementation Order
1. Complete system documentation (`docs/*`).
2. Verify end-to-end real execution and multi-experiment iteration.
3. Add MLflow experiment tracking adapter.
4. Add advanced statistical confidence interval analysis to the Error Analysis module.
5. Deploy production build.
