# AutoML Scientist — System Architecture

## Architecture Diagram

```
+-----------------------------------------------------------------------+
|                          REACT / VITE UI                              |
|   - Left Sidebar (History, New Research, Search, Status)              |
|   - Research Command Center (Prompt Composer, Dataset Upload)         |
|   - Conversational Workspace (Agent Stream, Inline Cards, Tabs)       |
+----------------------------------+------------------------------------+
                                   | HTTP REST / SSE Stream
                                   v
+-----------------------------------------------------------------------+
|                          FASTAPI BACKEND                              |
|   - Main API Server (`backend/main.py`)                               |
|   - Project & Settings Controller                                     |
|   - Control Signal Router (RUN, PAUSE, STOP)                           |
|   - Server-Sent Events (SSE) Telemetry Stream                         |
+----------------------------------+------------------------------------+
                                   | Async Orchestration Thread
                                   v
+-----------------------------------------------------------------------+
|                  AUTONOMOUS RESEARCH ORCHESTRATOR                     |
|                                                                       |
|  1. Literature Search Agent ------> Semantic Scholar REST API         |
|  2. Dataset Analysis Agent -------> Pandas Profiler                   |
|  3. Baseline Model Agent ---------> Scikit-Learn & XGBoost            |
|  4. Hypothesis & Coding Agent ----> OpenAI API / Rule Synthesizer     |
|  5. Sandboxed Execution Manager --> Docker / Subprocess Sandbox       |
|  6. Error Diagnostics Agent ------> Correlation & Quantile Slices     |
|  7. Scientific Report Agent ------> Markdown & JSON Exporter          |
+----------------------------------+------------------------------------+
                                   | State & Artifacts
                                   v
+-----------------------------------------------------------------------+
|                       STORAGE & WORKSPACES                            |
|   - `database/research_store.json` (Thread-safe JSON Store)           |
|   - `experiments/<project_id>/<exp_id>/`                              |
|       ├── script.py                                                   |
|       ├── stdout.log                                                  |
|       ├── stderr.log                                                  |
|       └── metrics.json                                                |
+-----------------------------------------------------------------------+
```

## Agent Workflows
1. **Research Agent**: Formulates a formal research question from user prompt.
2. **Literature Agent**: Queries Semantic Scholar for relevant academic publications.
3. **Dataset Agent**: Analyzes CSV/Parquet files for row/col counts, data types, target candidate, class imbalance, missing values, duplicates, and data quality issues.
4. **Baseline Agent**: Fits Logistic Regression, Random Forest, XGBoost, and MLP models to establish benchmark performance metrics (F1, Accuracy, PR-AUC, ROC-AUC, R2).
5. **Hypothesis & Coding Agent**: Uses LLM prompts to synthesize testable scientific hypotheses and runnable Python experiment scripts.
6. **Sandboxed Execution Manager**: Executes Python scripts inside isolated subprocesses/Docker containers with execution timeouts and stdout/stderr capture.
7. **Error Analysis Agent**: Evaluates prediction error vectors against feature distributions to diagnose failure modes.
8. **Report Agent**: Compiles findings into a structured scientific Markdown report.
