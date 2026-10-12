-- Gold needs full disclosure history: deduplication can hide reverted restatements.
-- Selection policy and lineage fields are documented in docs/setup.md.
-- `gold_candidate_suffix` lets the Airflow publisher build this model under a
-- candidate alias and swap it into place atomically; manual builds use '' and
-- write the served relation directly.
{{ config(
    materialized='table',
    alias='annual_metrics' ~ var('gold_candidate_suffix', ''),
    post_hook=revoke_candidate_api_select(),
) }}

{{ select_annual_metrics(ref('financial_fact_disclosures')) }}
