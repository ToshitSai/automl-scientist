-- =============================================================================
-- 003_pgvector.sql — semantic retrieval layer (task §9)
--
-- Applied ONLY when the `vector` extension is available (Neon, Supabase, and
-- any Postgres with pgvector installed). On servers without pgvector this
-- migration is recorded as applied with a NOTICE and the rest of the schema
-- works unchanged: semantic retrieval simply stays disabled (vector columns
-- absent → repository vector queries return nothing instead of failing).
--
-- Nothing here is used for structured queries — pgvector serves semantic
-- retrieval only (task rule: do NOT vectorize everything).
-- =============================================================================

DO $$
DECLARE
    has_vector BOOLEAN;
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS vector;
        has_vector := TRUE;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'pgvector extension not available — semantic retrieval disabled (install pgvector to enable)';
        has_vector := FALSE;
    END;

    IF has_vector THEN
        -- Long-term memories: semantic recall of facts/preferences.
        ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding vector(1536);
        CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memories
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

        -- RAG chunks: document → chunk → embedding → retrieval → LLM context.
        ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(1536);
        CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
        CREATE INDEX IF NOT EXISTS idx_chunks_document_embedding_ready
            ON document_chunks (document_id) WHERE embedding IS NOT NULL;
    END IF;
END $$;
