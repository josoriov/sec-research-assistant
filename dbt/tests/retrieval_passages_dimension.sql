-- Embeddings must match the pinned model dimension before publication.
select passage_id, dim, vector_dims(embedding) as vector_dim
from {{ ref('retrieval_passages') }}
where dim <> {{ var('embedding_dim') }}
   or vector_dims(embedding) <> {{ var('embedding_dim') }}
