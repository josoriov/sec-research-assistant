-- Embeddings for validated silver passages. Written by embeddings/ (dbt cannot
-- compute vectors); gold.retrieval_passages joins this table via a dbt source.
--
-- Reuse rule: a row is keyed by (passage_hash, processing_version, model_version),
-- so a vector is recomputed only when the content, the processing version, or the
-- model version changes. The dimension is fixed at 384 (all-MiniLM-L6-v2) and
-- re-checked in dbt before publication.
--
-- pgvector is enabled once by db/init/01-init.sh (task T001).

CREATE TABLE IF NOT EXISTS silver.passage_embeddings (
    passage_hash       text        NOT NULL,
    processing_version text        NOT NULL,
    model_version      text        NOT NULL,
    dim                integer     NOT NULL,
    embedding          vector(384) NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (passage_hash, processing_version, model_version)
);
