-- Filing documents that failed validation, with the reason and bronze reference.
{{ config(materialized='table') }}

select
    manifest_id, cik, accession, form, primary_document, url, filing_date,
    report_date, quarantine_reason as reason
from (
    {{ staged_filings(
        source('bronze', 'filing_documents'), source('bronze', 'manifest')
    ) }}
) staged
where staged.quarantine_reason is not null
