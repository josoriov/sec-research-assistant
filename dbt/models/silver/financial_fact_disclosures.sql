-- Preserve every valid disclosure so deduplication cannot hide gold candidates.
{{ config(materialized='table') }}

select
    source_fact_id,
    manifest_id,
    cik,
    concept,
    taxonomy,
    tag,
    unit,
    period_start,
    period_end,
    value,
    fiscal_year,
    fiscal_period,
    form,
    accession,
    filed_date,
    frame
from {{ ref('stg_source_facts') }}
where quarantine_reason is null
