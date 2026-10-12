-- The read-only API role must not be able to read candidate gold tables.
--
-- db/init/01-init.sh grants the API role SELECT on every table the pipeline
-- creates in `gold` (default privileges), which is what lets served tables be
-- read without an explicit grant. Candidate tables would inherit that same
-- grant, so each gold model revokes it in a post-hook. dbt runs post-hooks
-- inside the model's transaction, so the candidate is never readable by the
-- API role; publish_gold grants SELECT back on the served tables after it
-- swaps the candidates in.
--
-- Without a candidate suffix this returns a harmless no-op, so a manual build
-- keeps the inherited grant on the served tables.
{% macro revoke_candidate_api_select() %}
    {%- set suffix = var('gold_candidate_suffix', '') -%}
    {%- if suffix -%}
    revoke select on gold."{{ model.name }}{{ suffix }}" from "{{ env_var('GOLD_API_DB_USER', 'gold_api') }}"
    {%- else -%}
    select 1
    {%- endif -%}
{% endmacro %}
