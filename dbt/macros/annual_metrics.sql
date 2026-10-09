-- Shared with fixture tests; selection policy is documented in docs/setup.md.
{% macro select_annual_metrics(disclosures_relation) %}
with mapped as (
    select
        m.metric,
        f.*
    from {{ disclosures_relation }} f
    join {{ ref('metric_concepts') }} m
      on f.taxonomy = m.taxonomy
     and f.tag = m.tag
     and f.unit = m.unit
),

annual as (
    select *
    from mapped
    where form in ('10-K', '10-K/A')
      and fiscal_period = 'FY'
      and period_start is not null
      and period_end - period_start between 350 and 380
),

ranked as (
    select
        *,
        min(value) over period <> max(value) over period as is_ambiguous,
        row_number() over (
            period
            order by filed_date desc nulls last, accession desc nulls last, source_fact_id desc
        ) as rn
    from annual
    window period as (partition by cik, metric, period_start, period_end, unit)
)

select
    r.cik,
    r.metric,
    r.concept,
    r.taxonomy,
    r.tag,
    r.unit,
    r.period_start,
    r.period_end,
    extract(year from r.period_end)::int as fiscal_year,
    r.value,
    r.is_ambiguous,
    r.source_fact_id,
    r.manifest_id,
    r.accession,
    r.form,
    r.filed_date
from ranked r
where r.rn = 1
{% endmacro %}
