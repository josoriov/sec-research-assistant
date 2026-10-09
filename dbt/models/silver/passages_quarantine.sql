-- Passages that failed validation, with the reason and bronze reference.
{{ config(materialized='table') }}

select
    block_id, manifest_id, cik, accession, block_ordinal, section, heading,
    text, passage_hash, processing_version, quarantine_reason as reason
from (
    {{ staged_document_blocks(
        source('bronze', 'document_blocks'), ref('filings')
    ) }}
) staged
where staged.quarantine_reason is not null
