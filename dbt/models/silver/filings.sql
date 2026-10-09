-- Validated filing documents (bronze.filing_documents -> silver).
{{ config(materialized='table') }}

select
    manifest_id, cik, accession, form, primary_document, url, filing_date, report_date
from (
    {{ staged_filings(
        source('bronze', 'filing_documents'), source('bronze', 'manifest')
    ) }}
) staged
where staged.quarantine_reason is null
