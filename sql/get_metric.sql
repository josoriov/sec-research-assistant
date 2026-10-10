-- Approved tool: get one metric's annual values from published gold.
--
-- All values are bound by the driver (psycopg named parameters); nothing is
-- interpolated into the text, so user input can never change the statement.
-- Parameters:
--   %(cik)s          int   company CIK
--   %(metric)s       text  revenue | net_income | operating_cash_flow
--   %(unit)s         text  metric unit (USD)
--   %(fiscal_years)s int[] optional fiscal-year filter (NULL = every year)
select
    cik,
    metric,
    unit,
    period_start,
    period_end,
    fiscal_year,
    value,
    is_ambiguous,
    source_fact_id,
    manifest_id,
    accession,
    form,
    filed_date
from gold.annual_metrics
where cik = %(cik)s
  and metric = %(metric)s
  and unit = %(unit)s
  -- Cast the nullable array parameter so PostgreSQL can infer its type even when
  -- it is NULL (otherwise the first `is null` is an ambiguous parameter).
  and (%(fiscal_years)s::integer[] is null
       or fiscal_year = any(%(fiscal_years)s::integer[]))
order by period_end
