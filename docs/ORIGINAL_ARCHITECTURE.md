# Upstream Architecture Analysis: Sakana AI Scientist-v2

## Executive Overview

The AI Scientist-v2 is a fully autonomous scientific research system developed by Sakana AI (building on top of the AIDE tree search framework). It automates the end-to-end scientific process: generating research hypotheses, conducting experiments via LLM-driven code generation, analyzing performance metrics, generating plots, and compiling complete LaTeX scientific manuscripts complete with automated literature review and peer-review evaluation.

---

## Architecture Blueprint

```
                          [ Topic Markdown / Prompt ]
                                       │
                                       ▼
                       ┌──────────────────────────────┐
                       │  perform_ideation_temp_free  │
                       └──────────────┬───────────────┘
                                      │ (Literature Validation via Semantic Scholar)
                                      ▼
                             [ Ideas JSON File ]
                                      │
                                      ▼
                       ┌──────────────────────────────┐
                       │   launch_scientist_bfts.py   │
                       └──────────────┬───────────────┘
                                      │
                                      ▼
                       ┌──────────────────────────────┐
                       │     BFTS Agent Manager       │
                       │   (treesearch/agent_manager)  │
                       └──────────────┬───────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            ▼                         ▼                         ▼
   ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
   │ Parallel Worker │       │ Parallel Worker │       │ Parallel Worker │
   │   (Worker 1)    │       │   (Worker 2)    │       │   (Worker N)    │
   └────────┬────────┘       └────────┬────────┘       └────────┬────────┘
            │                         │                         │
            └─────────────────────────┼─────────────────────────┘
                                      ▼
                       ┌──────────────────────────────┐
                       │ Code Execution / Subprocess  │
                       │      (interpreter.py)        │
                       └──────────────┬───────────────┘
                                      │ (stdout, stderr, metrics, plots)
                                      ▼
                       ┌──────────────────────────────┐
                       │    Journal & Tree Logger     │
                       │   (journal.py, tree viz)     │
                       └──────────────┬───────────────┘
                                      │
                                      ▼
                       ┌──────────────────────────────┐
                       │    Manuscript Generation     │
                       │     (perform_writeup.py)     │
                       └──────────────┬───────────────┘
                                      │ (LaTeX compilation, citations)
                                      ▼
                       ┌──────────────────────────────┐
                       │ Peer Review & Quality Guard  │
                       │   (perform_llm/vlm_review)   │
                       └──────────────────────────────┘
```

---

## Core Components Analysis

### 1. Ideation & Literature Search Module (`ai_scientist/perform_ideation_temp_free.py` & `ai_scientist/tools/semantic_scholar.py`)
- **Inputs**: User-provided topic Markdown file (`workshop-file`) specifying background, problem domain, and guidelines.
- **Mechanism**: Executes multi-step LLM ideation loops (`max-num-generations` and `num-reflections`).
- **Literature Checking**: Integrates with the Semantic Scholar API (`S2_API_KEY`) to query candidate keywords and abstracts. Evaluates novelty by checking if similar papers already exist in the literature.
- **Output**: JSON payload containing structured ideas: `Name`, `Title`, `Experiment`, `Interestingness`, `Feasibility`, `Novelty`, `Novelty_Reasoning`.

### 2. Best-First Tree Search (BFTS) & Agent Manager (`ai_scientist/treesearch/agent_manager.py`)
- **Core Engine**: Built on top of the AIDE (AI Data Engineering) framework.
- **Tree Topology**: Represents research trials as a directed tree where nodes correspond to experimental iterations (code drafts, feature additions, model changes, bug fixes).
- **Search Strategy**: Best-First Tree Search (BFTS). Prioritizes nodes based on validation scores and execution outcomes. Supports multi-worker parallel branch expansion (`num_workers`, `steps`, `num_drafts`).
- **Debug & Retry**: Implements retry logic (`max_debug_depth`, `debug_prob`) when code execution fails or throws exceptions.

### 3. Execution Interpreter (`ai_scientist/treesearch/interpreter.py`)
- **Code Execution**: Executes LLM-written Python scripts locally using standard Python `subprocess` / `exec` calls.
- **Environment Context**: Runs inside the host OS process or active Conda environment.
- **Telemetry**: Captures stdout, stderr, execution duration, and exit codes. Parses metric dicts printed by generated scripts.

### 4. Journaling & Tree Visualization (`ai_scientist/treesearch/journal.py`, `log_summarization.py`)
- **State Capture**: Records node parentage, exact code diffs, execution logs, parsed scalar metrics, and generated image artifacts (matplotlib/seaborn plots).
- **Visualization**: Outputs an interactive HTML tree (`unified_tree_viz.html`) depicting all explored nodes, status indicators (success, failure, bug), and validation trajectories.

### 5. Multi-Provider LLM/VLM Interface (`ai_scientist/llm.py`, `ai_scientist/vlm.py`)
- **Provider Abstractions**: Custom wrapper functions `get_response_from_llm`, `get_batch_responses_from_llm`, and `create_client`.
- **Supported Backends**:
  - OpenAI (`gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini`)
  - Anthropic Claude (`claude-3-5-sonnet`) direct API, AWS Bedrock (`bedrock/...`), or Vertex AI
  - Google Gemini (`gemini-2.0-flash`, `gemini-2.5-pro`) via OpenAI compatibility endpoint
  - OpenRouter, DeepSeek, and local Ollama models (`ollama/qwen3`, `ollama/deepseek-r1`)
- **Features**: Automatic retries via `backoff`, token usage tracking (`@track_token_usage`), and robust JSON extractors (`extract_json_between_markers`).

### 6. Manuscript Writing & Review Engine (`ai_scientist/perform_writeup.py`, `perform_llm_review.py`, `perform_vlm_review.py`)
- **LaTeX Templates**: Uses pre-packaged LaTeX templates (`blank_icml_latex`, `blank_icbinb_latex`).
- **Section Generation**: Sequentially drafts Abstract, Introduction, Background, Method, Experimental Setup, Results, Discussion, and Conclusion.
- **Citation Ingestion**: Queries Semantic Scholar during paper writing to automatically fetch BibTeX citations.
- **Automated Peer Review**: Evaluates written papers using LLM/VLM reviewers based on standard conference criteria (Soundness, Presentation, Contribution, Overall Score, Confidence).

---

## Operational Workflow

1. **Phase 1: Ideation**: User inputs topic Markdown file → LLM generates & refines hypothesis → Semantic Scholar checks novelty → Output `ideas.json`.
2. **Phase 2: Tree Search Experimentation**: `launch_scientist_bfts.py` launches `AgentManager` → Spawns parallel workers → Workers edit Python code → Local interpreter executes script → Metric parser evaluates performance → Tree updates node scores.
3. **Phase 3: Aggregation & Plotting**: Selected best tree path yields final codebase & aggregated plots (`perform_plotting.py`).
4. **Phase 4: Manuscript & Citation**: `perform_writeup.py` constructs LaTeX paper → Queries citations → Compiles PDF.
5. **Phase 5: Automated Peer Review**: LLM/VLM reviewer grades paper → Saves review report.

---

## Upstream Limitations for Practical Enterprise ML

1. **Unsafe Local Execution**: Runs arbitrary LLM-generated code directly on host environment without Docker/container isolation, creating high security risk.
2. **Generic Research Paper Focus**: Designed for open-ended LaTeX paper generation rather than focused, practical ML problem solving on standard structured/tabular/multimodal enterprise datasets.
3. **Lack of Automated Dataset Profiling**: Assumes code templates handle data reading; lacks profiling for missing data, class imbalance, correlations, or target identification.
4. **Lack of Systematic Baseline Modeling**: Does not establish standard ML baseline suites (Logistic Regression, Random Forest, LightGBM/XGBoost) prior to deep exploration.
5. **No Visual Interactive UI Dashboard**: Controlled purely via CLI commands; lacks REST APIs, database persistence, interactive experiment comparison, error analysis GUI, or tree search dashboard.
