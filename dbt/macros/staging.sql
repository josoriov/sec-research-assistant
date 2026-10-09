-- Shared validation keeps the model and fixture tests consistent; see docs/setup.md.
{% macro staged_source_facts(source_relation) %}
with typed as (
    select
        id as source_fact_id,
        manifest_id,
        cik,
        concept,
        taxonomy,
        tag,
        btrim(unit) as unit,
        btrim(accession) as accession,
        value_text,
        start_date,
        end_date,
        fiscal_year,
        fiscal_period,
        form,
        frame,
        {{ safe_date('start_date') }} as period_start,
        {{ safe_date('end_date') }} as period_end,
        {{ safe_date('filed_date') }} as filed_date,
        case when value_text ~ '^-?[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?$'
              and pg_input_is_valid(value_text, 'numeric')
             then value_text::numeric end as value
    from {{ source_relation }}
)

select
    source_fact_id,
    manifest_id,
    cik,
    concept,
    taxonomy,
    tag,
    unit,
    value_text,
    value,
    period_start,
    period_end,
    filed_date,
    fiscal_year,
    fiscal_period,
    form,
    accession,
    frame,
    case
        when concept is null or btrim(concept) = '' then 'missing_concept'
        when tag is null or btrim(tag) = '' then 'missing_concept'
        when unit is null or unit = '' then 'missing_unit'
        when unit not in {{ supported_units_in_list() }} then 'unsupported_unit'
        when value_text is null then 'missing_value'
        when value is null then 'non_numeric_value'
        when end_date is null or period_end is null then 'missing_or_invalid_period_end'
        when start_date is not null and period_start is null then 'invalid_period_start'
        when filed_date is null then 'missing_or_invalid_filed_date'
        when accession is null or accession = '' then 'missing_accession'
        when period_start is not null and period_start > period_end then 'period_start_after_end'
        else null
    end as quarantine_reason
from typed
{% endmacro %}
