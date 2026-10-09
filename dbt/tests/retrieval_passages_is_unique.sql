-- Retrieval grain: one row per (filing, passage hash, processing version, model
-- version). Identical text in different filings legitimately shares one vector,
-- so the filing (manifest) is part of the grain.
select manifest_id, passage_hash, processing_version, model_version, count(*) as n
from {{ ref('retrieval_passages') }}
group by manifest_id, passage_hash, processing_version, model_version
having count(*) > 1
