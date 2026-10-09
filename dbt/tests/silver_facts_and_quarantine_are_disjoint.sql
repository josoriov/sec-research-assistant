-- A fact must never be both valid and quarantined.
select source_fact_id
from {{ ref('financial_facts') }}
intersect
select source_fact_id
from {{ ref('financial_facts_quarantine') }}
