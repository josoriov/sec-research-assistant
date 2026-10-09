-- Keep the earliest bronze reference at the approved fact grain.
-- Full disclosure history remains available for gold's latest-filed selection.
{{ config(materialized='table') }}

select distinct on (cik, concept, unit, period_start, period_end, value)
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
from {{ ref('financial_fact_disclosures') }}
-- Earliest disclosure wins for exact duplicates; ties broken deterministically.
order by cik, concept, unit, period_start, period_end, value,
         filed_date asc nulls last, accession asc nulls last, source_fact_id asc
