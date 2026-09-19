# AutoML Scientist — Environment Configuration Guide

## Overview
This document outlines the environment variables, service dependencies, and configuration setup for running the **AutoML Scientist** autonomous research engine locally or in production.

---

## Required & Optional Environment Variables

### 1. LLM Provider API Keys
- `OPENAI_API_KEY`: (Optional) OpenAI API key for GPT-4o / GPT-4o-mini research hypothesis synthesis and code generation.
- `ANTHROPIC_API_KEY`: (Optional) Anthropic Claude API key.
- `GEMINI_API_KEY`: (Optional) Google Gemini API key.

*Note: If no LLM API key is provided, the engine operates in `Heuristic / Rule-based` mode, synthesizing valid Python experiment scripts using domain rule templates.*

### 2. Academic Literature Search
- `SEMANTIC_SCHOLAR_API_KEY`: (Optional) API key for Semantic Scholar REST API. If omitted, public unauthenticated requests are used (subject to rate limiting).

### 3. Server Configuration
- `PORT`: HTTP server port (Default: `8000`).
- `HOST`: Server bind address (Default: `127.0.0.1` or `0.0.0.0`).
- `ENVIRONMENT`: `development` | `production`.

### 4. Storage & Execution Directories
- `DATASETS_DIR`: Directory path for uploaded user datasets (Default: `uploaded_datasets/`).
- `EXPERIMENTS_DIR`: Directory path for saved experiment scripts, logs, and artifacts (Default: `experiments/`).

---

## Service Dependencies

| Service | Purpose | Fallback / Behavior if Missing |
| :--- | :--- | :--- |
| **Python 3.10+** | Core runtime for FastAPI backend & ML libraries | Required |
| **Node.js 18+** | Frontend development server (Vite) & build tool | Required |
| **Docker Daemon** | Isolated container sandbox for experiment execution | Fallback to Process Subprocess Sandbox (`sandboxed_execution` marked `NOT_CONFIGURED`) |
| **Semantic Scholar API** | Academic paper retrieval | Fallback to `NOT_CONFIGURED` literature status |

---

## Example `.env` Configuration File

```env
# AutoML Scientist Environment Configuration

# LLM Keys
OPENAI_API_KEY=sk-proj-your-openai-api-key-here
SEMANTIC_SCHOLAR_API_KEY=

# App Server
PORT=8000
HOST=127.0.0.1
ENVIRONMENT=development
```

---

## System Health Check Endpoint

Verify active dependencies by querying the health endpoint:
```bash
curl http://127.0.0.1:8000/api/settings
```

**Example Response**:
```json
{
  "llmProvider": "OpenAI GPT-4o",
  "openaiKeyConfigured": true,
  "dockerAvailable": false,
  "sandboxMode": "Process Sandbox (Subprocess isolation)",
  "budgetMins": 60,
  "maxExperiments": 5
}
```
