-- One validated filing per bronze filing manifest.
select manifest_id, count(*) as n
from {{ ref('filings') }}
group by manifest_id
having count(*) > 1
