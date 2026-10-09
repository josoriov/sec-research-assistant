-- Staging view over bronze.source_facts. The typing and quarantine rules live in
-- the staged_source_facts macro so the regression test can exercise the exact
-- same logic; see dbt/macros/staging.sql.
{{ config(materialized='view') }}

{{ staged_source_facts(source('bronze', 'source_facts')) }}
