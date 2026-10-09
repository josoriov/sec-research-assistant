-- Gold grain uniqueness: one row per (cik, metric, period_start, period_end, unit).
select
    cik, metric, period_start, period_end, unit, count(*) as duplicated_rows
from {{ ref('annual_metrics') }}
group by cik, metric, period_start, period_end, unit
having count(*) > 1
