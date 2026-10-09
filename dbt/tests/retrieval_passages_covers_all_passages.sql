-- F013 publication gate: every validated silver passage must appear in gold for
-- the current embedding model version. Missing vectors (or a dropped join) are
-- returned and fail the build instead of silently publishing partial retrieval
-- data. References both silver and gold, so a silver-only build excludes it.
with gold as (
    select passage_hash, processing_version
    from {{ ref('retrieval_passages') }}
    where model_version = '{{ var("embedding_model_version") }}'
)

select p.passage_hash, p.processing_version, p.manifest_id
from {{ ref('passages') }} p
left join gold g
  on g.passage_hash = p.passage_hash
 and g.processing_version = p.processing_version
where g.passage_hash is null
  and p.processing_version = '{{ var("active_processing_version") }}'
