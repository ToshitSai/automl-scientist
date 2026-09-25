# Database Architecture — AI Scientist

Status: **implemented and verified** (PostgreSQL 17 local, 4 migrations applied,
JSON data migrated with zero loss, live end-to-end test passed). This document
records the audit, the decision, the final architecture, and operations.

---

## 1. Current storage architecture (audited 2026-09-24)

| What was stored | Where | Survived restart? | Multi-user? | Production-ready? |
|---|---|---|---|---|
| All app state (projects, datasets, baselines, tree_nodes, error_analyses, literature, reports, settings, sessions + 628 messages) | `database/research_store.json` (~20k lines) via `ResearchStore` singleton (RLock + atomic `os.replace`) | Locally only | No — single file + in-process lock | No |
| Dataset CSV/parquet files | `uploaded_datasets/`, `datasets/`, `uploaded_datasets/hf_cache/` | Locally only | No | No |
| Experiment artifacts (logs, metrics.json, scripts) | `experiments/<proj-id>/` | Locally only | No | No |
| Conversation-id mapping | Browser `localStorage` (`ai-scientist-conv-<projectId>`) | Per-browser only | No | No |
| (Partial) KV mirror when `DATABASE_URL` set | `kv_store(namespace, key, JSONB)` — commit `535e75f` | Yes | Partially | No — single JSONB blob per key, no schema, no integrity, no queryability |

A prior patch (commit `535e75f`) had added a one-table JSONB key-value mirror
so Vercel's ephemeral filesystem would not lose conversational memory. It fixed
the symptom (ephemerality) but was not a database: no relational integrity, no
typed columns, no indexes beyond the primary key, no migration tooling, no
vector support.

## 2. Problems found

1. Entire state in one JSON blob; every append re-serializes the whole session.
2. No relational integrity — nothing prevents orphaned references.
3. Not queryable — any filter is a full scan in Python.
4. Concurrency is process-local; multi-instance writes can clobber each other.
5. No user model; sessions are anonymous strings; conversation mapping is
   per-browser via localStorage.
6. No semantic retrieval layer (the "memory" was string fields on a session).
7. No schema versioning / migration story.
8. Restart reconciliation existed as a workaround for jobs living in background
   threads of one process (no durable queue).
9. Large files on local disk — lost on serverless, never backed up.
10. ~110 empty QA probe sessions polluting production data.

## 3. Options considered

| Criterion | SQLite | MongoDB | Supabase (Postgres) | PostgreSQL | **PostgreSQL + pgvector** |
|---|---|---|---|---|---|
| Relational data (project→sessions→experiments→reports) | Yes | App-enforced | Yes | Yes | Yes |
| Transactions / integrity | Yes | Partial | Yes | Yes | Yes |
| Concurrent writers (serverless) | No (file lock) | Yes | Yes | Yes | Yes |
| JSON flexibility (JSONB) | Adequate | Native | Yes | Yes | Yes |
| Vector / semantic search | No | Atlas-only | pgvector | Extension | **Native** |
| Managed hosting for Vercel | No | Costly | Free tier | Free tier (Neon) | Free tier (Neon) |
| Local dev without Docker | Yes | Needs server | Needs server | Easy install | Same Postgres |
| Cost | Free | $$$ | Free tier | Free tier | Free tier |

Dedicated vector databases (Pinecone/Weaviate/Qdrant): rejected — a second
service for a need pgvector covers, with a second failure mode and bill.
Redis-as-primary: rejected (no durability/queries; spec forbids it).

## 4. Recommendation (approved by the user)

**PostgreSQL 16+ as the single primary datastore**, with pgvector for semantic
retrieval, a hybrid schema (typed columns + JSONB payloads), Redis as an
optional cache/job-queue transport, and S3-compatible object storage for large
files. All three scope decisions were confirmed by the user: Neon/Supabase-style
Postgres+pgvector target, hybrid schema, and adapters-first infra scope.

## 5. Why it fits

- The data is deeply relational (project → sessions → events → hypotheses →
  experiments → metrics → artifacts → report). Postgres makes integrity the
  schema's job instead of the app's.
- JSONB gives document-style flexibility for the agent's evolving payloads
  (stage states, agent logs, QA blobs) without giving up relations — legacy
  dict payloads migrated losslessly.
- pgvector covers long-term memory and future RAG with one system; embedding
  columns are nullable, so nothing is vectorized until content exists (and the
  rest of the system works even where the extension is missing).
- The deployment is Vercel serverless: a managed Postgres with the already-
  present psycopg driver is the only architecture that works in both local
  uvicorn and serverless production.
- LLM + DB + retrieval + tools + research engine: the database stores state and
  makes it retrievable; it does not make the model smarter by itself, and it is
  not used for training data or model weights (those stay in object storage /
  separate pipelines).

## 6. Final architecture

```
React UI ── FastAPI (uvicorn / Vercel function)
                 │
                 ├── ResearchStore facade (unchanged public API)
                 │     ├── Repository (Postgres, psycopg3, thread-local conns)
                 │     │     26 tables, UUID PKs, FKs, CHECK statuses,
                 │     │     created_at/updated_at, workload indexes
                 │     └── JSON file backend (fallback: offline dev, outages,
                 │           hermetic tests via STORE_DB_DISABLED)
                 ├── FileStore adapter → local dir (dev) | S3/MinIO/Supabase (prod)
                 └── Redis adapter (optional; durable job records in Postgres)
```

**Schema (migrations/001–004, applied automatically on first connect):**

- Identity/conversation: `users`, `conversations`, `messages`,
  `conversation_context` (+ `metadata` JSONB so unknown session state is never
  dropped), `memories` (typed FACT/PREFERENCE/…, `embedding vector(1536)`).
- Research: `research_projects` (camelCase-compatible columns + `extra_json`
  for unknown legacy keys), `research_sessions`, `research_events` (append-only,
  typed) + `project_payloads` (per-project JSONB collections: agent logs,
  events view, tree nodes, baselines, EDA reports, error analyses, literature).
- Literature: `papers` (normalized, deduped on doi/url) and `citations`
  (claim → source traceability).
- Data/ML: `datasets`, `dataset_versions`, `dataset_files`, `experiments`
  (parent/hypothesis/dataset FKs, status, runtime), `experiment_metrics`
  (unique per experiment+metric), `hypotheses`, `experiment_relationships`,
  `artifacts`, `reports` (versioned markdown rows).
- Ops: `tool_calls`, `jobs` (durable queue; `FOR UPDATE SKIP LOCKED` claiming),
  `files` (object-storage metadata: storage_key, size, sha256 — bytes never in
  Postgres), `documents`/`document_chunks` (RAG: chunk → embedding →
  traceable source), `settings`, `schema_migrations`.

Key decisions:
- **Hybrid schema:** typed columns for anything queried/joined; JSONB for
  evolving agent payloads; unknown legacy fields preserved (`extra_json`,
  `metadata`) so no migration can silently drop data.
- **Payload collections** that the app reads/writes whole per project live in
  `project_payloads` (one upsert), while queryable facts go to typed tables.
- **pgvector is additive** (`003_pgvector.sql`): memories and chunk embeddings
  are used only when the extension exists; otherwise semantic search returns
  empty and everything else keeps working. Verified live on the pgvector-less
  Windows Postgres.
- **Status domains are CHECK constraints**, and the repository coerces legacy
  values into them (e.g. unknown statuses → FAILED) instead of crashing.
- All SQL is parameterized; there is no string interpolation of user data.

## 7. Migration (executed)

```bash
py -m scripts.migrate_json_to_postgres --dry-run   # preview
py -m scripts.migrate_json_to_postgres             # backup + migrate + verify
py -m scripts.migrate_json_to_postgres --verify    # re-verify any time
```

- Creates a timestamped backup of `research_store.json` before writing.
- Idempotent (upserts / conflict-guarded inserts) — re-running converges.
- Mapping: projects → `research_projects` (typed + JSONB + `extra_json`);
  sessions → `conversations` + `messages` (original timestamps and message ids
  preserved) + `conversation_context`; baselines/tree nodes/EDA
  reports/error analyses/literature → `project_payloads` (+ `papers`
  normalized rows); reports → `reports`; settings → `settings`.
- Legacy artifacts without a parent project (QA leftovers: `test-validation-01`,
  `test-phase1-full`, `test-local-run`) are skipped, listed, and preserved in
  the backup — the JSON had no FK enforcement; the database does.

**Result (2026-09-24):** 14 projects, 232 conversations, 918 messages,
6 settings keys, 12/12 payload collections each, 17 deduped papers. Verifier:
`PASS — no data loss detected` (message contents byte-identical per session).

## 8. Testing

- `tests/test_database.py` — migrations, CRUD round-trips, status coercion,
  unknown-key preservation, payload collections, agent logs/events,
  conversations, pending actions, facade delegation, **degradation to the file
  backend when Postgres fails**, jobs claiming, vector memory/document
  retrieval (relevance asserted: related > unrelated, top hit correct),
  file-store round trip + path-traversal rejection. Hermetic by default; live
  Postgres tests activate with `AI_SCIENTIST_DB_TEST_URL`.
- `tests/test_store_db.py` — cross-instance memory: cold-start and warm
  instances see each other's writes through one shared database.
- `tests/test_live_database_e2e.py` — live: chat → message rows verified in
  Postgres via psql → API serves the conversation → migrated research artifacts
  served. Plus a kill/restart check: conversation and 14 projects still served
  from Postgres after the backend is force-killed and restarted.
- Full suite: **237 passed, 6 skipped** (was 219 before the database work).

## 9. Operations

- **Local dev:** `docker compose up -d` (Postgres 16 + pgvector, Redis, MinIO)
  or a local Postgres install + `CREATE DATABASE ai_scientist;`. `py -m
  scripts.migrate_json_to_postgres` for legacy data. Config in `.env`
  (`.env.example` documents every variable).
- **Hermetic mode:** `STORE_DB_DISABLED=1` (set automatically in the test
  suite) forces the JSON backend — no test ever touches a real database.
- **Production (Vercel):** set `DATABASE_URL` to Neon/Supabase (pgvector
  included); the JSON file is never used. Set `STORAGE_URL`/`STORAGE_BUCKET`
  for object storage. Redis optional.
- **Failure behavior:** any Postgres error degrades that request to the JSON
  file backend (never crashes, never loses the write silently); connection
  drops are detected with a 1s ping and connections are transparently reopened.
- **Never in the database:** model weights, training data, and large binaries —
  those belong to object storage (`files` table holds metadata only) and the
  separate training pipeline. No automatic fine-tuning from DB contents.

## 10. Known follow-ups (deliberately out of scope)

1. Auth: `users` table + `user_id` FKs exist; wiring real auth (JWT/session)
   is the next step before multi-tenant use.
2. Move research pipeline launches from in-process threads onto the durable
   `jobs` queue (table + claiming API are ready).
3. Enable pgvector locally (custom Windows build) or rely on Neon/Supabase in
   production — semantic retrieval activates automatically either way.
4. Backfill `files`/`artifacts` rows for historical experiment directories.
