-- Restatement/comparative selection guard: for each gold period, no eligible
-- annual disclosure for the same (cik, metric, period, unit) may have been filed
-- later than the value gold serves. Uses the full disclosure history, so a
-- value that reverted or an earlier ineligible form cannot hide the latest
-- eligible disclosure.
with candidates as (
    select
        f.cik, m.metric, f.period_start, f.period_end, f.unit, f.filed_date
    from {{ ref('financial_fact_disclosures') }} f
    join {{ ref('metric_concepts') }} m
      on f.taxonomy = m.taxonomy
     and f.tag = m.tag
     and f.unit = m.unit
    where f.form in ('10-K', '10-K/A')
      and f.fiscal_period = 'FY'
      and f.period_start is not null
      and f.period_end - f.period_start between 350 and 380
)
select c.*
from candidates c
join {{ ref('annual_metrics') }} a
  on a.cik = c.cik
 and a.metric = c.metric
 and a.period_start = c.period_start
 and a.period_end = c.period_end
 and a.unit = c.unit
where c.filed_date > a.filed_date
