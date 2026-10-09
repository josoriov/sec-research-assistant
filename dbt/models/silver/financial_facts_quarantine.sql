-- Keep rejected facts traceable through their bronze references and reasons.
{{ config(materialized='table') }}

select
    source_fact_id,
    manifest_id,
    cik,
    concept,
    taxonomy,
    tag,
    unit,
    value_text,
    period_start,
    period_end,
    fiscal_year,
    fiscal_period,
    form,
    accession,
    quarantine_reason as reason
from {{ ref('stg_source_facts') }}
where quarantine_reason is not null
