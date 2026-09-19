# Autonomous Machine Learning Research Lab (AI Scientist) — Roadmap & Implementation Plan

This document outlines the architecture, roadmap, and milestone tracking for **AI Scientist — Autonomous Machine Learning Research Lab**.

---

## 🏛️ Target Architecture

```
User Input ("Improve credit-card fraud detection.")
                     │
                     ▼
           Frontend Research Dashboard
                     │ (REST / SSE Stream)
                     ▼
             FastAPI API Layer
                     │
                     ▼
          Research Orchestrator Engine
                     │
    ┌────────────────┴───────────────────────────┐
    │              Agentic Research Loop        │
    │                                            │
    │  1. Agent 1: Research Planner              │
    │  2. Agent 2: Literature Researcher         │
    │  3. Agent 3: Dataset Agent & EDA           │
    │  4. Agent 4: Experiment Planner            │
    │  5. Agent 5: Sandboxed Code Executor       │
    │  6. Agent 6: Evaluator & Multi-Seed Stat   │
    │  7. Agent 7: Error Analysis Agent          │
    │  8. Agent 8: Hypothesis Generator          │
    │  9. Agent 9: Scientific Critic Agent       │
    │ 10. Agent 10: Scientific Report Generator  │
    └────────────────┬───────────────────────────┘
                     │
    ┌────────────────┴───────────────────────────┐
    │          Research Infrastructure           │
    │  • Experiment Contract (Pydantic Schema)   │
    │  • Sandboxed Execution (Docker / Subprocess)│
    │  • Experiment Tree Search Manager           │
    │  • Research Memory Store                     │
    │  • Real-time Research Event Stream         │
    │  • MLflow & SQLite / JSON Persistence      │
    └────────────────────────────────────────────┘
```

---

## 📋 Implementation Roadmap & Milestone Tracker

- [x] **Phase 0: Repository Audit & Architecture Mapping**
  - Inspected existing codebase, mapped current state, created architecture docs and roadmap.

- [ ] **Phase 1: Experiment Engine & Contract Schema (Core Engine)**
  - Implement strict machine-readable `ExperimentContract` Pydantic schema.
  - Implement modular Dataset Loader supporting CSV and Parquet formats.
  - Implement real Model Trainer (Logistic Regression, Random Forest, XGBoost, LightGBM).
  - Implement Evaluator computing empirical Precision, Recall, F1, ROC-AUC, PR-AUC, FPR, FNR.
  - Implement structured artifact storage (scripts, logs, metrics.json, model files).
  - Verify execution with real tabular credit card fraud / classification datasets (No fake/hardcoded metrics allowed).

- [ ] **Phase 2: Sandboxed Execution & Security Controls**
  - Docker container execution with memory limits (2GB), CPU limits (2 cores), timeout (60s), network isolation (`--network=none`), and non-root execution.
  - Robust subprocess fallback when Docker daemon is not active.
  - Filesystem isolation & prevention of host secret/credential access.

- [ ] **Phase 3: Database, Event Log Stream & MLflow Integration**
  - Unified database models for projects, datasets, literature, experiments, hypotheses, artifacts, and event logs.
  - Real-time event log stream (`RESEARCH_STARTED`, `PLANNER_COMPLETED`, `DATASET_SELECTED`, `BASELINE_COMPLETED`, `EXPERIMENT_COMPLETED`, `CRITIC_REVIEWED`, etc.).
  - MLflow tracking integration for experiment parameter and metric tracking.

- [ ] **Phase 4: Agent 1 (Research Planner) & Agent 3 (Dataset Agent)**
  - Agent 1: Formulate formal research questions, primary/secondary metrics, constraints, success criteria.
  - Agent 3: Thorough dataset EDA, imbalance check, missingness, duplicate detection, target leakage check, feature quality report.

- [ ] **Phase 5: Agent 2 (Literature Researcher)**
  - Live API querying of Semantic Scholar, OpenAlex, arXiv.
  - Extract paper metadata (title, authors, year, abstract, key method, dataset, source URL, DOI).

- [ ] **Phase 6: Agent 4 (Experiment Planner) & Code Generator**
  - Convert hypotheses into valid `ExperimentContract` specs.
  - Synthesize clean, executable Python training & evaluation code matching the contract.

- [ ] **Phase 7: Agent 6 (Evaluator) & Statistical Validation**
  - Multi-seed evaluations (e.g. random seeds 42, 43, 44).
  - Non-parametric bootstrap 95% confidence intervals and standard deviation calculations.

- [ ] **Phase 8: Agent 7 (Error Analysis) & Agent 8 (Hypothesis Generator)**
  - Agent 7: False Positive / False Negative counts, feature-error correlations, quantile slice metrics.
  - Agent 8: Observation -> Hypothesis mapping with explicit reasoning, expected effect, experiment proposal, and risks.

- [ ] **Phase 9: Agent 9 (Scientific Critic Agent)**
  - Audit data leakage, baseline fairness, metric selection, test set misuse, and random variation.
  - Reject invalid or non-reproducible experiment nodes before tree insertion.

- [ ] **Phase 10: Experiment Tree Search Manager & Research Memory**
  - Hierarchical tree structure storing parent-child experiment relationships.
  - Search manager selecting next experiment based on expected improvement, uncertainty, novelty, and compute budget.
  - Research memory store preventing duplicate hypothesis exploration.

- [ ] **Phase 11: Agent 10 (Scientific Report Generator)**
  - Render comprehensive 16-section scientific Markdown report (Abstract, RQ, Background, Literature, Dataset, Method, Baseline, Experiments, Results, Statistical Validation, Error Analysis, Limitations, Findings, Reproducibility, Future Work, References).

- [ ] **Phase 12: Production FastAPI API & Scientific Dashboard UI**
  - Full API endpoints for research lifecycle, control signals (RUN, PAUSE, STOP), reproduction, and streaming.
  - Modern, dark-themed scientific dashboard UI with interactive experiment tree, live event stream, metric charts, literature viewer, error analysis cards, and report renderer.

---

## 🎯 Current Milestone: Phase 1 — Experiment Engine & Contract Schema

Building and verifying the core Experiment Engine without UI dependencies.
