-- Bronze tables. Applied idempotently by the ingester, running as the pipeline
-- role, so both fresh and pre-existing volumes get them (docker-entrypoint init
-- hooks only run when the data volume is first created). Original bytes live in
-- MinIO under the bronze/ bucket; these tables index them and hold the
-- source-faithful facts.

CREATE TABLE IF NOT EXISTS bronze.manifest (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cik          integer     NOT NULL,
    source       text        NOT NULL,
    accession    text,
    url          text        NOT NULL,
    bucket       text        NOT NULL,
    -- NULL until a download succeeds; a failed attempt has no bytes to hash.
    object_key   text,
    content_hash text,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    status       text        NOT NULL,  -- stored | failed | resolved
    error        text,
    -- Hash-addressed objects: a changed response gets a new key and row; an
    -- unchanged rerun conflicts and is skipped. NULL object_key rows (failures)
    -- are all distinct in PostgreSQL and never conflict.
    UNIQUE (bucket, object_key)
);

CREATE INDEX IF NOT EXISTS manifest_cik_source_idx
    ON bronze.manifest (cik, source);

-- Idempotent migration for volumes created before failures were recorded: a
-- failed attempt has no bytes, so these columns must allow NULL.
ALTER TABLE bronze.manifest ALTER COLUMN object_key DROP NOT NULL;
ALTER TABLE bronze.manifest ALTER COLUMN content_hash DROP NOT NULL;

CREATE TABLE IF NOT EXISTS bronze.source_facts (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    manifest_id   bigint NOT NULL REFERENCES bronze.manifest (id),
    cik           integer NOT NULL,
    fact_hash     text NOT NULL,
    concept       text,
    taxonomy      text,
    tag           text,
    unit          text,
    start_date    text,
    end_date      text,
    value_text    text,
    fiscal_year   integer,
    fiscal_period text,
    form          text,
    accession     text,
    frame         text,
    filed_date    text,
    source        jsonb NOT NULL,
    UNIQUE (manifest_id, fact_hash)
);

CREATE INDEX IF NOT EXISTS source_facts_concept_idx
    ON bronze.source_facts (concept);
