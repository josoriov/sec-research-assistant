-- Silver grain uniqueness: no two rows share
-- (cik, concept, unit, period_start, period_end, value). Different values for
-- the same period are legitimate restatement history and are not duplicates.
select
    cik, concept, unit, period_start, period_end, value, count(*) as duplicated_rows
from {{ ref('financial_facts') }}
group by cik, concept, unit, period_start, period_end, value
having count(*) > 1
