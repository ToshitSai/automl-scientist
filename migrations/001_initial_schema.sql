-- =============================================================================
-- 001_initial_schema.sql — AI Scientist relational schema (PostgreSQL 16+)
--
-- Conventions:
--   * UUID primary keys (gen_random_uuid()).
--   * created_at / updated_at on every table; triggers keep updated_at fresh.
--   * Status columns are CHECK-constrained; JSONB for evolving agent payloads
--     (hybrid schema), typed columns for everything queried or joined.
--   * Vector columns are NULLABLE: nothing is vectorized until content exists
--     (pgvector only for semantic retrieval, never for structured queries).
--   * Large binaries NEVER live in Postgres: files table holds storage metadata
--     and the storage_key points at object storage (local dir / S3 / MinIO).
-- =============================================================================

-- ---------------------------------------------------------------- extensions
-- NOTE: the pgvector extension (+ vector columns + ivfflat indexes) is applied
-- by migrations/003_pgvector.sql with graceful guards, so the schema also works
-- on Postgres servers without the extension (semantic retrieval then simply
-- stays disabled until pgvector is available).
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid()

-- ---------------------------------------------------------- schema_migrations
CREATE TABLE IF NOT EXISTS schema_migrations (
    id          SERIAL PRIMARY KEY,
    migration   TEXT        NOT NULL UNIQUE,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --------------------------------------------------------------------- users
-- Single-user local dev maps to a system user; real auth can layer in later.
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     TEXT UNIQUE,                -- future auth subject id
    display_name    TEXT,
    email           TEXT UNIQUE,
    preferences     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Immutable system user used when no authentication exists yet.
INSERT INTO users (id, external_id, display_name)
VALUES ('00000000-0000-0000-0000-000000000000', 'system', 'Local User')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------- conversations
CREATE TABLE IF NOT EXISTS conversations (
    id              TEXT PRIMARY KEY,           -- app-level id, e.g. conv-<proj>-<rand>
    user_id         UUID        NOT NULL REFERENCES users(id),
    title           TEXT,
    status          TEXT        NOT NULL DEFAULT 'ACTIVE'
                                CHECK (status IN ('ACTIVE', 'ARCHIVED', 'DELETED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_conversations_user      ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated   ON conversations(updated_at DESC);

-- ------------------------------------------------------------------ messages
CREATE TABLE IF NOT EXISTS messages (
    id                  TEXT PRIMARY KEY,       -- uuid4 hex, mirrors record_message
    conversation_id     TEXT        NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role                TEXT        NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content             TEXT        NOT NULL,
    intent              TEXT,
    topic               TEXT,
    research_id         TEXT,
    metadata            JSONB       NOT NULL DEFAULT '{}'::jsonb,   -- pending_action + extras
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_research     ON messages(research_id);

-- ------------------------------------------------------- conversation_context
-- Rolling conversational state per session (last topic, pronoun resolution
-- subjects, pending action) — the hot state the intent router mutates.
CREATE TABLE IF NOT EXISTS conversation_context (
    conversation_id         TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    last_user_message       TEXT,
    last_assistant_message  TEXT,
    last_topic              TEXT,
    last_reasoning_subjects JSONB       NOT NULL DEFAULT '[]'::jsonb,
    recent_topics           JSONB       NOT NULL DEFAULT '[]'::jsonb,
    pending_action          JSONB,                      -- NULL = no pending action
    active_project_id       TEXT,
    metadata                JSONB       NOT NULL DEFAULT '{}'::jsonb,  -- unknown/future session state (no field ever dropped)
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_context_project ON conversation_context(active_project_id);

-- ------------------------------------------------------------------ memories
-- Explicit long-term memory (never auto-persisted personal data).
CREATE TABLE IF NOT EXISTS memories (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id     TEXT        REFERENCES conversations(id) ON DELETE SET NULL,
    memory_type         TEXT        NOT NULL
                                CHECK (memory_type IN ('FACT', 'PREFERENCE', 'PROJECT_CONTEXT', 'RESEARCH_CONTEXT', 'USER_PROVIDED_CONTEXT')),
    content             TEXT        NOT NULL,
    metadata            JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- embedding vector(1536) + ivfflat index are added by 003_pgvector.sql.
CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id, memory_type);

-- ----------------------------------------------------------- research_projects
CREATE TABLE IF NOT EXISTS research_projects (
    id                  TEXT PRIMARY KEY,       -- proj-<hex6> from create_project
    user_id             UUID        NOT NULL REFERENCES users(id),
    name                TEXT        NOT NULL,
    objective           TEXT        NOT NULL,
    research_question   TEXT,
    status              TEXT        NOT NULL DEFAULT 'QUEUED'
                                    CHECK (status IN ('QUEUED', 'IN_PROGRESS', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'STOPPED')),
    control_signal      TEXT        NOT NULL DEFAULT 'RUN' CHECK (control_signal IN ('RUN', 'PAUSE', 'STOP')),
    dataset_id          UUID,       -- FK added after datasets table (below)
    dataset_name        TEXT,
    dataset_path        TEXT,       -- local/relative path (dev convenience)
    test_path           TEXT,
    dataset_meta        JSONB,
    llm_provider        TEXT,
    engine_state        TEXT,
    budget_mins         INTEGER,
    max_experiments     INTEGER     NOT NULL DEFAULT 5,
    experiments_count   INTEGER     NOT NULL DEFAULT 0,
    best_metric         TEXT,
    best_model          TEXT,
    compute_used        TEXT,
    active_agent        TEXT,
    error_detail        TEXT,
    stage_states        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    extra_json          JSONB       NOT NULL DEFAULT '{}'::jsonb,  -- unknown/future legacy keys (no field ever dropped)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_projects_user   ON research_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON research_projects(status, created_at DESC);

-- ---------------------------------------------------------- research_sessions
-- One pipeline execution (launch/resume) of a project.
CREATE TABLE IF NOT EXISTS research_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      TEXT        NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    status          TEXT        NOT NULL DEFAULT 'RUNNING'
                                CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    summary         JSONB       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_rsessions_project ON research_sessions(project_id, started_at DESC);

-- ------------------------------------------------------------- research_events
-- Append-only event log (store.add_event + agentLogs entries).
CREATE TABLE IF NOT EXISTS research_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      TEXT        NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    session_id      UUID        REFERENCES research_sessions(id) ON DELETE SET NULL,
    event_type      TEXT        NOT NULL,
    agent           TEXT,
    message         TEXT,
    status          TEXT,
    details         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_revents_project ON research_events(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_revents_type    ON research_events(event_type);

-- ------------------------------------------------------------ research_sources
-- Web sources discovered during research.
CREATE TABLE IF NOT EXISTS research_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      TEXT        REFERENCES research_projects(id) ON DELETE CASCADE,
    url             TEXT        NOT NULL,
    title           TEXT,
    source_type     TEXT        NOT NULL DEFAULT 'WEB'
                                CHECK (source_type IN ('WEB', 'PAPER', 'DATASET_DOC', 'DOCUMENT', 'OTHER')),
    content         TEXT,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    retrieved_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, url)
);
CREATE INDEX IF NOT EXISTS idx_rsources_project ON research_sources(project_id);

-- --------------------------------------------------------------------- papers
CREATE TABLE IF NOT EXISTS papers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT        NOT NULL,
    authors         JSONB       NOT NULL DEFAULT '[]'::jsonb,   -- ["Name", ...]
    url             TEXT,
    doi             TEXT,
    publisher       TEXT,
    year            INTEGER,
    abstract        TEXT,
    source_type     TEXT,
    external_id     TEXT,       -- OpenAlex / Semantic Scholar work id
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    retrieved_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_papers_url_doi
    ON papers(COALESCE(doi, ''), COALESCE(url, ''));
CREATE INDEX IF NOT EXISTS idx_papers_title ON papers(title);

-- ------------------------------------------------------------------ citations
-- Traceable claim → source link (prevents fake/unsupported citations).
CREATE TABLE IF NOT EXISTS citations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id            UUID        REFERENCES papers(id) ON DELETE CASCADE,
    project_id          TEXT        REFERENCES research_projects(id) ON DELETE CASCADE,
    claim               TEXT        NOT NULL,
    supporting_text     TEXT,
    location            TEXT,
    confidence          NUMERIC(4,3) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_citations_project ON citations(project_id);
CREATE INDEX IF NOT EXISTS idx_citations_paper   ON citations(paper_id);

-- ------------------------------------------------------------------- datasets
CREATE TABLE IF NOT EXISTS datasets (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          TEXT        REFERENCES research_projects(id) ON DELETE SET NULL,
    name                TEXT        NOT NULL,
    source              TEXT,       -- 'huggingface' | 'upload' | 'generated' | ...
    url                 TEXT,
    owner               TEXT,
    revision            TEXT,
    license             TEXT,
    description         TEXT,
    task_type           TEXT,       -- classification | regression | ...
    target_column       TEXT,
    row_count           BIGINT,
    column_count        INTEGER,
    schema              JSONB,      -- column name/type map
    splits              JSONB,      -- {"train": n, "test": n, ...}
    quality_summary     JSONB,
    hash                TEXT,
    external_id         TEXT,       -- HF dataset id, e.g. gusdelact/credit-card-fraud-curated
    metadata            JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_datasets_project   ON datasets(project_id);
CREATE INDEX IF NOT EXISTS idx_datasets_external  ON datasets(external_id);

-- ------------------------------------------------------------ dataset_versions
CREATE TABLE IF NOT EXISTS dataset_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id          UUID        NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    version             TEXT        NOT NULL,
    file_id             UUID,       -- FK added after files (below)
    row_count           BIGINT,
    hash                TEXT,
    changelog           TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dataset_id, version)
);
CREATE INDEX IF NOT EXISTS idx_dversions_dataset ON dataset_versions(dataset_id);

-- ---------------------------------------------------------------- dataset_files
CREATE TABLE IF NOT EXISTS dataset_files (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id          UUID        NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    version_id          UUID        REFERENCES dataset_versions(id) ON DELETE CASCADE,
    split               TEXT,       -- train | validation | test
    file_id             UUID,       -- FK added after files (below)
    row_count           BIGINT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dfiles_dataset ON dataset_files(dataset_id);

-- ----------------------------------------------------------------------- files
-- Object-storage metadata. The actual bytes live at storage_url/storage_key —
-- never inside Postgres.
CREATE TABLE IF NOT EXISTS files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    storage_key     TEXT        NOT NULL UNIQUE,    -- e.g. datasets/<proj>/train.csv
    storage_backend TEXT        NOT NULL DEFAULT 'local' CHECK (storage_backend IN ('local', 's3', 'minio', 'supabase')),
    file_type       TEXT,                           -- text/csv, application/pdf, ...
    size_bytes      BIGINT,
    hash_sha256     TEXT,
    owner_user_id   UUID        REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_files_owner ON files(owner_user_id);

ALTER TABLE dataset_versions
    DROP CONSTRAINT IF EXISTS fk_dversions_file;
ALTER TABLE dataset_versions
    ADD CONSTRAINT fk_dversions_file FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL;
ALTER TABLE dataset_files
    DROP CONSTRAINT IF EXISTS fk_dfiles_file;
ALTER TABLE dataset_files
    ADD CONSTRAINT fk_dfiles_file FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL;
ALTER TABLE research_projects
    DROP CONSTRAINT IF EXISTS fk_projects_dataset;
ALTER TABLE research_projects
    ADD CONSTRAINT fk_projects_dataset FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE SET NULL;

-- ----------------------------------------------------------------- experiments
CREATE TABLE IF NOT EXISTS experiments (
    id                      TEXT PRIMARY KEY,       -- app-level experiment id
    project_id              TEXT        NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    session_id              UUID        REFERENCES research_sessions(id) ON DELETE SET NULL,
    parent_experiment_id    TEXT        REFERENCES experiments(id) ON DELETE SET NULL,
    hypothesis_id           UUID,       -- FK added after hypotheses (below)
    dataset_id              UUID        REFERENCES datasets(id) ON DELETE SET NULL,
    dataset_version_id      UUID        REFERENCES dataset_versions(id) ON DELETE SET NULL,
    model_name              TEXT,
    model_version           TEXT,
    parameters              JSONB       NOT NULL DEFAULT '{}'::jsonb,
    features                JSONB,
    preprocessing           JSONB,
    seed                    INTEGER,
    split_strategy          TEXT,
    status                  TEXT        NOT NULL DEFAULT 'PENDING'
                                        CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'PLATEAUED', 'STOPPED')),
    runtime_seconds         NUMERIC(12,3),
    resource_usage          JSONB,
    error                   TEXT,
    conclusion              TEXT,
    is_baseline             BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_experiments_project ON experiments(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_experiments_parent  ON experiments(parent_experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiments_status  ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_experiments_dataset ON experiments(dataset_id);

-- ------------------------------------------------------------ experiment_metrics
CREATE TABLE IF NOT EXISTS experiment_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id   TEXT            NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    metric_name     TEXT            NOT NULL,   -- ACCURACY, PR_AUC, ROC_AUC, ...
    metric_value    NUMERIC(14,8),
    details         JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (experiment_id, metric_name)
);
CREATE INDEX IF NOT EXISTS idx_metrics_experiment ON experiment_metrics(experiment_id);

-- ----------------------------------------------------------------- hypotheses
CREATE TABLE IF NOT EXISTS hypotheses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      TEXT        NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    experiment_id   TEXT        REFERENCES experiments(id) ON DELETE SET NULL,   -- hypothesis derived from
    statement       TEXT        NOT NULL,
    rationale       TEXT,
    status          TEXT        NOT NULL DEFAULT 'PROPOSED'
                                CHECK (status IN ('PROPOSED', 'TESTING', 'SUPPORTED', 'REFUTED', 'INCONCLUSIVE')),
    generation      INTEGER,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hypotheses_project    ON hypotheses(project_id);
CREATE INDEX IF NOT EXISTS idx_hypotheses_experiment ON hypotheses(experiment_id);

ALTER TABLE experiments
    DROP CONSTRAINT IF EXISTS fk_experiments_hypothesis;
ALTER TABLE experiments
    ADD CONSTRAINT fk_experiments_hypothesis FOREIGN KEY (hypothesis_id) REFERENCES hypotheses(id) ON DELETE SET NULL;

-- --------------------------------------------------- experiment_relationships
CREATE TABLE IF NOT EXISTS experiment_relationships (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_experiment_id TEXT       NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    child_experiment_id  TEXT       NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    relationship_type   TEXT        NOT NULL DEFAULT 'ITERATION'
                                    CHECK (relationship_type IN ('ITERATION', 'VARIANT', 'ABLATION', 'RETRY')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (parent_experiment_id, child_experiment_id, relationship_type)
);

-- ------------------------------------------------------------------ artifacts
CREATE TABLE IF NOT EXISTS artifacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id   TEXT        REFERENCES experiments(id) ON DELETE CASCADE,
    project_id      TEXT        REFERENCES research_projects(id) ON DELETE CASCADE,
    file_id         UUID        REFERENCES files(id) ON DELETE SET NULL,
    artifact_type   TEXT,                           -- metrics.json | model | plot | log | script
    name            TEXT        NOT NULL,
    storage_key     TEXT,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_artifacts_experiment ON artifacts(experiment_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_project    ON artifacts(project_id);

-- -------------------------------------------------------------------- reports
CREATE TABLE IF NOT EXISTS reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      TEXT        NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    title           TEXT,
    content_md      TEXT        NOT NULL,           -- markdown report body
    report_type     TEXT        NOT NULL DEFAULT 'RESEARCH'
                                CHECK (report_type IN ('RESEARCH', 'EDA', 'ERROR_ANALYSIS', 'DATASET')),
    status          TEXT        NOT NULL DEFAULT 'FINAL' CHECK (status IN ('DRAFT', 'FINAL')),
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reports_project ON reports(project_id, created_at DESC);

-- ----------------------------------------------------------------- tool_calls
CREATE TABLE IF NOT EXISTS tool_calls (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      TEXT        REFERENCES research_projects(id) ON DELETE CASCADE,
    conversation_id TEXT        REFERENCES conversations(id) ON DELETE SET NULL,
    tool_name       TEXT        NOT NULL,
    arguments       JSONB       NOT NULL DEFAULT '{}'::jsonb,
    result          JSONB,
    status          TEXT        NOT NULL DEFAULT 'OK' CHECK (status IN ('OK', 'ERROR', 'TIMEOUT')),
    error           TEXT,
    duration_ms     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_project      ON tool_calls(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_conversation ON tool_calls(conversation_id);

-- ----------------------------------------------------------------------- jobs
-- Durable job queue. Redis is the in-process runtime layer for progress and
-- wake-ups; this table is the durable record so jobs survive restarts.
CREATE TABLE IF NOT EXISTS jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type        TEXT        NOT NULL,           -- research_pipeline | dataset_download | ...
    payload         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    status          TEXT        NOT NULL DEFAULT 'QUEUED'
                                CHECK (status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    priority        INTEGER     NOT NULL DEFAULT 5,
    project_id      TEXT        REFERENCES research_projects(id) ON DELETE CASCADE,
    attempts        INTEGER     NOT NULL DEFAULT 0,
    max_attempts    INTEGER     NOT NULL DEFAULT 3,
    last_error      TEXT,
    scheduled_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status, priority, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);

-- ------------------------------------------------- documents / chunks (RAG)
-- Future RAG path: document → chunk → embedding → retrieval → LLM context.
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      TEXT        REFERENCES research_projects(id) ON DELETE CASCADE,
    user_id         UUID        REFERENCES users(id) ON DELETE CASCADE,
    file_id         UUID        REFERENCES files(id) ON DELETE SET NULL,
    title           TEXT,
    source          TEXT,
    doc_type        TEXT,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project_id);

CREATE TABLE IF NOT EXISTS document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER     NOT NULL,
    content         TEXT        NOT NULL,
    page            INTEGER,
    section         TEXT,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    token_count     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);
-- embedding vector(1536) + ivfflat index are added by 003_pgvector.sql.
CREATE INDEX IF NOT EXISTS idx_chunks_document  ON document_chunks(document_id, chunk_index);

-- ---------------------------------------------------------- project_payloads
-- Per-project JSONB payload collections the app reads/writes whole: agent logs,
-- structured events, experiment-tree nodes, baselines, dataset (EDA) reports
-- and error analyses. One row per (project, kind). Structured data that needs
-- querying lives in its own typed tables instead.
CREATE TABLE IF NOT EXISTS project_payloads (
    project_id  TEXT        NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    kind        TEXT        NOT NULL,
    payload     JSONB       NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, kind)
);

-- ------------------------------------------------------------------- settings
-- Flat application settings (llmProvider, sandboxMode, ...). One row per key.
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT        PRIMARY KEY,
    value       JSONB       NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------- updated_at maintenance
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'users', 'conversations', 'conversation_context', 'memories',
        'research_projects', 'datasets', 'experiments', 'reports', 'jobs'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_updated_at ON %I', t, t);
        EXECUTE format('CREATE TRIGGER trg_%I_updated_at BEFORE UPDATE ON %I
                        FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    END LOOP;
END $$;
