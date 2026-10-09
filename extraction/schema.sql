-- Bronze tables for extracted filing documents and passages. Applied
-- idempotently by extraction/ (running as the pipeline role), like
-- ingestion/schema.sql, so fresh and pre-existing volumes both get them.
--
-- The original HTML bytes remain in MinIO; these tables hold the source-linked
-- text extracted from them. Validation and gold selection happen downstream in
-- dbt (silver.filings/silver.passages, gold.retrieval_passages).

CREATE TABLE IF NOT EXISTS bronze.filing_documents (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    manifest_id      bigint  NOT NULL REFERENCES bronze.manifest (id),
    cik              integer NOT NULL,
    accession        text    NOT NULL,
    form             text,
    filing_date      text,
    report_date      text,
    primary_document text,
    url              text    NOT NULL,
    -- Set by extraction/ when a stored document yields no usable text, so the
    -- failure is source-linked and routes to quarantine instead of looking like
    -- a successful, evidence-free filing. NULL on success.
    extraction_error text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (manifest_id)
);

-- Idempotent migration for volumes created before the extraction-error column.
ALTER TABLE bronze.filing_documents
    ADD COLUMN IF NOT EXISTS extraction_error text;

CREATE TABLE IF NOT EXISTS bronze.document_blocks (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    manifest_id        bigint  NOT NULL REFERENCES bronze.manifest (id),
    cik                integer NOT NULL,
    accession          text    NOT NULL,
    block_ordinal      integer NOT NULL,
    section            text,
    heading            text,
    text               text    NOT NULL,
    block_hash         text    NOT NULL,
    processing_version text    NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    -- A rerun of the same processing version skips rows already stored (stable
    -- ids); a new version is stored alongside so versions can coexist during a
    -- backfill. Bump the processing version when the parser changes.
    UNIQUE (manifest_id, block_hash, processing_version)
);

CREATE INDEX IF NOT EXISTS document_blocks_cik_accession_idx
    ON bronze.document_blocks (cik, accession);
