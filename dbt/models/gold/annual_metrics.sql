-- Gold needs full disclosure history: deduplication can hide reverted restatements.
-- Selection policy and lineage fields are documented in docs/setup.md.
{{ config(materialized='table') }}

{{ select_annual_metrics(ref('financial_fact_disclosures')) }}
