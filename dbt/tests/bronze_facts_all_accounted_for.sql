-- bronze -> silver completeness: every bronze fact must be accounted for.
-- Valid facts must appear in the disclosure history (financial_facts is the
-- deduplicated subset, so we match against disclosures); invalid facts must be
-- quarantined.
select stg.source_fact_id
from {{ ref('stg_source_facts') }} stg
left join {{ ref('financial_fact_disclosures') }} d
  on d.source_fact_id = stg.source_fact_id
where stg.quarantine_reason is null
  and d.source_fact_id is null

union all

select stg.source_fact_id
from {{ ref('stg_source_facts') }} stg
left join {{ ref('financial_facts_quarantine') }} q
  on q.source_fact_id = stg.source_fact_id
where stg.quarantine_reason is not null
  and q.source_fact_id is null
