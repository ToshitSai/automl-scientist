# Customization Plan: AutoML Scientist

## Strategic Vision

AutoML Scientist shifts the foundation of Sakana AI's AI Scientist-v2 from academic LaTeX manuscript generation to an **enterprise-grade, autonomous machine learning research and optimization platform**.

Instead of writing research papers on open-ended topics, AutoML Scientist takes real-world ML problems and datasets (CSV, Parquet), profiles the data, establishes benchmark baselines, formulates testable hypotheses, executes experiments inside a safe Docker sandbox, performs error analysis, tracks experiments in PostgreSQL, and presents interactive insights via a modern web UI dashboard.

---

## Component Categorization: Reuse, Adapt, Replace & New

| Component | Status | Strategy & Rationale |
| :--- | :--- | :--- |
| **LLM Provider Integration** | **Adapted** | Adapt `ai_scientist/llm.py` into `backend/llm/` supporting OpenAI, Anthropic, and Gemini via unified provider interface with environment variable configs. |
| **Literature Search Tool** | **Adapted** | Adapt `ai_scientist/tools/semantic_scholar.py` into `research/literature.py` to retrieve relevant academic literature for problem context. |
| **Tree Search Mechanics** | **Adapted** | Adapt tree node expansion concepts from `treesearch/agent_manager.py` into `agents/experiment_designer.py` and `database/` experiment tree storage. |
| **Local Subprocess Execution** | **REPLACED** | **Completely remove** local subprocess code execution. Replace with isolated Docker Sandbox (`sandbox/docker_runner.py`). |
| **LaTeX Manuscript Generator** | **REPLACED** | **Replace** LaTeX paper generator with ML-focused Research Report Generator (`reports/report_generator.py`) outputting Markdown, JSON, and PDF summary reports. |
| **Dataset Profiler & Analyzer** | **NEW** | Build `datasets/analyzer.py` for automatic row/col count, class imbalance, missing value, correlation, outlier, leakage, and metric recommendation profiling. |
| **Automated Baseline System** | **NEW** | Build `models/baseline_generator.py` to automatically train initial Logistic Regression, Random Forest, XGBoost/LightGBM, and baseline neural models. |
| **Hypothesis Engine** | **NEW** | Build `agents/hypothesis_agent.py` to generate structured, testable hypotheses with explicit required features and evaluation criteria. |
| **Experiment Tracker** | **NEW** | Build `experiments/tracker.py` storing code versions, hyperparameters, metrics, runtime, logs, and artifacts in PostgreSQL. |
| **Error Analysis Agent** | **NEW** | Build `evaluation/error_analysis.py` analyzing false positives, false negatives, hard examples, and slice-level performance weaknesses. |
| **Statistical Analysis Module** | **NEW** | Build `evaluation/statistical.py` for confidence intervals, paired t-tests, Wilcoxon signed-rank tests, and seed variance analysis. |
| **REST API Server** | **NEW** | Build FastAPI server (`backend/app/main.py`) serving endpoints for research runs, tree state, dataset profiling, and reports. |
| **PostgreSQL Database Engine** | **NEW** | Build database migrations and schema (`database/schema.sql`, SQLAlchemy models) for multi-tenant persistence. |
| **Modern Dark UI Dashboard** | **NEW** | Build comprehensive web frontend (`frontend/`) with 12 main views (Dashboard, New Research, Workspace, Experiment Tree, Experiments, Dataset Analysis, Models, Results, Error Analysis, Literature, Report, Settings). |

---

## Target Project Architecture

```
[ Frontend: React / Modern Web Dashboard (12 Views) ]
                           │ (HTTP REST / JSON)
                           ▼
[ Backend API: FastAPI Server ]
                           │
                           ▼
[ Research Orchestrator Engine ]
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
[ Dataset Agent ]   [ Baseline Agent ]   [ Hypothesis Agent ]
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
              [ Experiment Designer Agent ]
                           │
                           ▼
               [ Coding & Execution Agent ]
                           │
                           ▼
          [ SAFE DOCKER EXPERIMENT SANDBOX ]
         (RAM/CPU Limits, Restricted Network)
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
[ Evaluation Agent ] [ Error Analysis Agent ] [ Statistical Agent ]
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
           [ Experiment Tracker & PostgreSQL DB ]
                           │
                           ▼
             [ Research Report Generator ]
```

---

## Autonomous Research Loop Design

```python
while research_budget_remaining and not stopping_condition_met:
    # 1. Analyze existing experiment tree & metrics
    current_state = analyze_results(experiment_tree)
    
    # 2. Formulate testable ML hypotheses based on past results
    hypotheses = hypothesis_agent.generate(current_state)
    scored_hypotheses = hypothesis_agent.score(hypotheses)
    selected_hypothesis = select_best(scored_hypotheses)
    
    # 3. Design experiment & write candidate code
    experiment_config = experiment_designer.design(selected_hypothesis)
    code = coding_agent.generate_code(experiment_config)
    
    # 4. Execute safely inside Docker container
    result = sandbox.execute(code=code, dataset=dataset, config=experiment_config)
    
    # 5. Evaluate outcomes & perform error analysis
    metrics = evaluation_agent.evaluate(result)
    error_report = error_analysis_agent.analyze(result)
    
    # 6. Update persistent directed experiment tree in DB
    update_experiment_tree(selected_hypothesis, result, metrics, error_report)
    
    # 7. Check budget and statistical convergence
    check_stopping_conditions()
```

---

## Safety & Security Guarantees

1. **Host Isolation**: All code execution occurs inside temporary Docker containers.
2. **Resource Quotas**: Hard memory limits (e.g. 4GB/8GB RAM), CPU core pinning, and strict execution timeouts (e.g., 300s).
3. **Network Isolation**: Disabled network egress during code execution (`--network none`) to prevent data exfiltration or unintended API calls.
4. **Secret Protection**: API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) are kept in backend environment variables and NEVER passed into the sandbox container.
