-- Passages must be unique per (manifest, passage hash, processing version).
select manifest_id, passage_hash, processing_version, count(*) as n
from {{ ref('passages') }}
group by manifest_id, passage_hash, processing_version
having count(*) > 1
