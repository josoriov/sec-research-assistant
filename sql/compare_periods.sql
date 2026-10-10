-- Approved tool: two annual values of one metric and their change, computed in
-- SQL. All values are bound by the driver (psycopg named parameters).
--
-- The earlier fiscal year is the base (a); the later is the comparison (b):
--   change_absolute = value_b - value_a
--   change_percent  = (value_b - value_a) / value_a, or NULL when value_a is 0
--
-- A fiscal-year label can match more than one eligible annual period (gold's
-- grain is the period, not the year), so each side also reports its candidate
-- count and the distinct periods. The caller asks for clarification when either
-- count exceeds one; it never silently picks a period.
--
-- Parameters:
--   %(cik)s     int   company CIK
--   %(metric)s  text  metric name
--   %(unit)s    text  metric unit (USD)
--   %(year_a)s  int   base fiscal year
--   %(year_b)s  int   comparison fiscal year
with picked as (
    select fiscal_year, period_start, period_end, value, is_ambiguous,
           source_fact_id, manifest_id, accession, form, filed_date
    from gold.annual_metrics
    where cik = %(cik)s
      and metric = %(metric)s
      and unit = %(unit)s
      and fiscal_year in (%(year_a)s, %(year_b)s)
),
a as (select * from picked where fiscal_year = %(year_a)s),
b as (select * from picked where fiscal_year = %(year_b)s),
ra as (select * from a order by period_end, period_start limit 1),
rb as (select * from b order by period_end, period_start limit 1)
select
    (select count(*) from a) as count_a,
    (select string_agg(distinct period_start::text || ' to ' || period_end::text,
                       ', ' order by period_start::text || ' to ' || period_end::text)
       from a) as periods_a,
    (select count(*) from b) as count_b,
    (select string_agg(distinct period_start::text || ' to ' || period_end::text,
                       ', ' order by period_start::text || ' to ' || period_end::text)
       from b) as periods_b,
    ra.value as value_a,
    ra.period_start as period_start_a,
    ra.period_end as period_end_a,
    ra.is_ambiguous as is_ambiguous_a,
    ra.source_fact_id as source_fact_id_a,
    ra.manifest_id as manifest_id_a,
    ra.accession as accession_a,
    ra.form as form_a,
    ra.filed_date as filed_date_a,
    rb.value as value_b,
    rb.period_start as period_start_b,
    rb.period_end as period_end_b,
    rb.is_ambiguous as is_ambiguous_b,
    rb.source_fact_id as source_fact_id_b,
    rb.manifest_id as manifest_id_b,
    rb.accession as accession_b,
    rb.form as form_b,
    rb.filed_date as filed_date_b,
    rb.value - ra.value as change_absolute,
    case
        when ra.value = 0 then null
        else (rb.value - ra.value) / ra.value
    end as change_percent
from (select 1) one
left join ra on true
left join rb on true
