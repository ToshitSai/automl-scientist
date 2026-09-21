# AI Scientist — Autonomous ML Research Platform

An autonomous machine-learning research assistant inspired by Sakana AI's
*AI Scientist-v2*. You describe a research goal in plain English, it discovers a
suitable dataset on Hugging Face, runs **real** exploratory analysis, trains
**real** baseline and experimental models, diagnoses errors, generates
hypotheses, and writes a research report — all through a conversational chat UI.

It is also a general assistant: it answers conceptual questions ("what is
recall?", "what is XGBoost?") directly, without launching a research run.

---

## Features

- **Conversational research agent** with intent routing (casual chat, general
  questions, explanations, research start/follow-up/control, report requests).
- **Hugging Face dataset discovery** — search, rank, inspect real metadata, and
  load a dataset only after you approve it.
- **Real training pipeline** — no simulated or fabricated metrics. Baselines and
  experiments run actual scikit-learn / XGBoost models.
- **Fraud-aware evaluation** — Precision, Recall, F1, ROC-AUC, PR-AUC, FPR, FNR
  and a confusion matrix, with class-imbalance handling.
- **Sandboxed experiment execution** — model-generated training code runs in an
  isolated subprocess (Docker when available), never directly on the host.
- **Error analysis, hypothesis generation and an experiment loop** that iterates
  toward a better model.
- **Experiment tracking** — optional best-effort MLflow logging; a local JSON
  store is the source of truth for projects, datasets and conversation history.
- **Graceful LLM fallback** — multi-provider (OpenAI → Gemini → Anthropic →
  Mistral) with deterministic heuristics so the app works even with no API keys.

---

## Tech stack

| Layer    | Technology                                              |
|----------|---------------------------------------------------------|
| Frontend | React 19, Vite 6, Tailwind CSS 4, Recharts, lucide-react |
| Backend  | FastAPI, Uvicorn (Python 3.10+)                          |
| ML       | pandas, numpy, scikit-learn, XGBoost, pyarrow            |
| Storage  | Local JSON file store (`database/research_store.json`)   |
| External | Hugging Face Hub API, OpenAlex, Semantic Scholar (keyless) |
| Tests    | pytest                                                   |

---

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for the frontend)
- Optional: **Docker** (stronger sandbox isolation for generated code)
- Optional: **MLflow server** on `http://localhost:5000` (experiment tracking)

---

## Setup

### 1. Clone and configure

```bash
git clone <your-repo-url> "model nova"
cd "model nova"

# Create your environment file (all keys are optional — see below)
cp .env.example .env
```

### 2. Backend

```bash
# Install the FULL local stack (FastAPI + pandas/scikit-learn/xgboost/pyarrow).
# requirements.txt alone is the minimal Vercel serverless subset and is NOT
# enough to download datasets or train models locally.
pip install -r requirements-local.txt

# Run the API server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

On Windows you may need `py` instead of `python`, and UTF-8 mode avoids console
encoding errors:

```bash
set PYTHONUTF8=1 && py -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The API is then available at `http://127.0.0.1:8000` (interactive docs at
`/docs`).

### 3. Frontend

```bash
npm install
npm run dev
```

The UI is served at `http://localhost:3000` and talks to the backend on port
8000.

> **Note:** `vite.config.js` ignores backend/database/sandbox paths in its file
> watcher. This prevents the page from full-reloading (and losing React state)
> every time the backend writes to `research_store.json` or `__pycache__`.

---

## Configuration (`.env`)

Every variable is **optional**. The app degrades gracefully:

- **LLM providers** (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`,
  `MISTRAL_API_KEY`): the first valid provider is used. If none are set or all
  fail, deterministic heuristic fallbacks keep the workflow running.
- `OPENAI_API_BASE`, `OPENAI_MODEL`: override the OpenAI endpoint/model.
- `OPENALEX_API_KEY`: polite-pool access for literature search. Semantic Scholar
  is queried keyless.
- `HF_TOKEN`: only needed for gated/private datasets. Public discovery and
  download work without it.
- `MLFLOW_TRACKING_URI`: best-effort experiment logging with a short timeout;
  ignored if MLflow is not running.
- `DATABASE_URL`, `REDIS_URL`: **reserved**. The persistent store is a local JSON
  file; these are read but not yet wired to a live Postgres/Redis connection.

### Security

- Secrets live **server-side only** (`.env` / process environment). They are
  never bundled into frontend code, never returned by an API response, and never
  printed to logs.
- The settings UI transmits only a boolean `apiKeySet` flag, never the key value.
- Model-generated training code executes in an isolated subprocess sandbox, not
  directly on the host.
- `.env` is git-ignored. Only `.env.example` (with placeholder values) is tracked.

---

## Usage

1. Open `http://localhost:3000`.
2. Ask a general question ("what is overfitting?") for a direct answer, **or**
   describe a research goal ("improve fraud detection on credit card
   transactions").
3. The agent proposes ranked Hugging Face datasets. **Approve** one to download
   it and launch the real pipeline.
4. Watch the run progress through plain-English stages: *Understanding the
   data*, *Building the first model*, *Generating ideas*, *Running experiments*,
   *Diagnosing errors*, *Writing the report*.
5. Inspect real metrics, the experiment tree, error analysis and the final
   research report.

You can pause/resume/stop a run, and ask follow-up questions ("why did the second
model do better?") that are answered from the **real** stored results.

---

## Testing

```bash
# Full suite (unit + integration + conversation regression).
# Live integration tests auto-skip when the backend is not running on :8000.
PYTHONUTF8=1 py -m pytest tests/ -q
```

- `tests/test_intent_router.py` — intent classification, concept matching,
  follow-up grounding, natural-conversation and general-knowledge regressions.
- `tests/test_hf_parsing.py` — HF reference parsing and target-column detection.
- `tests/test_store_conversation.py` — per-message conversation history.
- `tests/test_live_integration.py` — end-to-end checks against a running server
  (skipped if the server is down).
- `tests/conftest.py` — autouse fixtures isolate the JSON store into a temp file
  and disable LLM calls so unit tests are deterministic and side-effect free.

To run the live integration tests, start the backend first (see Setup §2).

---

## Deployment (Vercel)

The app deploys to Vercel as a static frontend + a Python serverless API.

- **Repository:** `github.com/ToshitSai/automl-scientist`
- **Production branch:** `main` (pushing to `main` triggers a production deploy)
- **Live URL:** `https://automl-scientist.vercel.app`
- **Build:** `npm run build` → `dist/` (configured in `vercel.json`)
- **API:** `vercel.json` rewrites `/api/*` → `api/index.py`, which exposes the
  FastAPI app (`backend.main:app`) as the serverless handler. The frontend calls
  a **relative** `/api` base (`src/api.js`), so it always targets the same
  origin — never `localhost`.

### Deployment workflow

```bash
git add <changed files>      # do NOT commit database/research_store.json (runtime state)
git commit -m "..."
git push origin HEAD:main    # local branch may be 'master' tracking origin/main
```

Vercel then rebuilds from `main`. Verify the deployed commit matches your local
`HEAD` and test the live URL — a local file change alone never reaches the site.

### Serverless dependency split (important)

- `requirements.txt` — **minimal** (fastapi, uvicorn, python-multipart). This is
  what Vercel installs. The conversational API (chat, intent routing,
  explanations, HF dataset *search*) runs on this plus the stdlib.
- `requirements-local.txt` — the **full** ML stack (pandas, scikit-learn,
  xgboost, pyarrow). Local development only.

The heavy stack is excluded from the deployment on purpose: it exceeds Vercel's
serverless bundle limit, and dataset download + model training are long-running
operations that cannot complete inside a function timeout. On the live site,
dataset *inspection/approval* and the *training pipeline* therefore degrade or
fail gracefully; the full research workflow is a local capability.

---

## Project layout

```
backend/        FastAPI app, intent router, LLM clients, HF datasets,
                dataset analyzer, trainer, error analyzer, literature search,
                report generator, telemetry tracker
agents/         Research orchestrator (pipeline state machine)
sandbox/        Isolated runner for model-generated experiment code
database/       File-backed JSON store (projects, datasets, sessions, messages)
src/            React frontend (components, api client, pages)
tests/          pytest unit / integration / regression suites
docs/           Architecture, environment and attribution notes
```

---

## Known limitations

- **Persistence is a local JSON file**, not a database. `DATABASE_URL` /
  `REDIS_URL` are accepted but not connected; concurrent multi-process writes are
  guarded by an in-process lock only.
- **MLflow tracking is best-effort** and silently skipped when unavailable.
- **LLM diversity depends on valid API keys.** Without them, hypothesis
  generation falls back to deterministic templates (real execution, but less
  varied experiment ideas).
- **Target-column detection** falls back to the last column when no obvious
  label is found, rather than prompting the user to disambiguate.
- Sandbox isolation is process-level by default; install Docker for stronger
  isolation of generated code.

---

## Attribution

Inspired by Sakana AI's *AI Scientist-v2*. See `docs/UPSTREAM_ATTRIBUTION.md`
and `docs/LEGAL_AND_ATTRIBUTION.md`.
