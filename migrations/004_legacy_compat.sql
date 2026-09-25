-- =============================================================================
-- 004_legacy_compat.sql — research_projects.extra_json
--
-- Preserves unknown/future legacy payload keys (no data loss, migration rule
-- §17). Idempotent: no-op on databases where 001 already declared the column.
-- =============================================================================

ALTER TABLE research_projects
    ADD COLUMN IF NOT EXISTS extra_json JSONB NOT NULL DEFAULT '{}'::jsonb;
