-- One row per (metric, taxonomy, tag, unit). The revenue metric maps two tags
-- (RevenueFromContractWithCustomerExcludingAssessedTax and Revenues), so the
-- uniqueness grain is the tag, not just the metric.
select metric, taxonomy, tag, unit, count(*) as n
from {{ ref('metric_concepts') }}
group by metric, taxonomy, tag, unit
having count(*) > 1
