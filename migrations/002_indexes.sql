-- =============================================================================
-- 002_indexes.sql — query-path indexes (task §22)
--
-- 001 already indexes most FK paths. This migration adds the named,
-- workload-oriented indexes for the access patterns the app actually uses:
--   * conversation listing per user, newest first
--   * project detail loads (events / experiments / reports newest first)
--   * dataset lookups by external id and name
--   * job polling (only non-terminal jobs — partial index keeps it small)
--   * paper dedupe lookups
-- No speculative indexes: every one below maps to a real query path.
-- =============================================================================

-- Chat sidebar: user's conversations, most recently active first.
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
    ON conversations (user_id, updated_at DESC)
    WHERE status <> 'DELETED';

-- Project detail page: newest events first, filtered by type for timelines.
CREATE INDEX IF NOT EXISTS idx_revents_project_created
    ON research_events (project_id, created_at DESC);

-- Experiment tree reconstruction: parent → children.
CREATE INDEX IF NOT EXISTS idx_experiments_parent_children
    ON experiments (parent_experiment_id) WHERE parent_experiment_id IS NOT NULL;

-- Non-terminal jobs only — the poller never touches finished rows.
CREATE INDEX IF NOT EXISTS idx_jobs_pending
    ON jobs (priority, scheduled_at)
    WHERE status IN ('QUEUED', 'RUNNING');

-- Dataset dedupe on ingest: same HF dataset re-approved shouldn't duplicate.
CREATE INDEX IF NOT EXISTS idx_datasets_name
    ON datasets (lower(name));

-- Literature dedupe by DOI when present.
CREATE INDEX IF NOT EXISTS idx_papers_doi
    ON papers (doi) WHERE doi IS NOT NULL;

-- Vector retrieval with a metadata pre-filter (per-project semantic search):
-- ivfflat alone can't filter, so a btree narrows candidates first. (Created
-- conditionally by 003_pgvector.sql when the extension is available.)
