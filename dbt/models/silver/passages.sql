-- Validated, source-linked passages (bronze.document_blocks -> silver).
-- Only blocks belonging to a valid filing pass; the rest quarantine.
{{ config(materialized='table') }}

select
    block_id, manifest_id, filing_cik as cik, filing_accession as accession,
    block_ordinal, section, heading, text, passage_hash, processing_version, url
from (
    {{ staged_document_blocks(
        source('bronze', 'document_blocks'), ref('filings')
    ) }}
) staged
where staged.quarantine_reason is null
