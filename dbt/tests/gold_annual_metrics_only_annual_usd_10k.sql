-- Annual selection guard: every gold row must be a ~1-year USD fact from a
-- 10-K/10-K/A. Any quarterly, year-to-date, non-USD, or non-annual value here
-- would mean periods or units were mixed.
select *
from {{ ref('annual_metrics') }}
where unit <> 'USD'
   or form not in ('10-K', '10-K/A')
   or period_start is null
   or period_end is null
   or period_end - period_start not between 350 and 380
