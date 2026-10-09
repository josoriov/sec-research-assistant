-- Gold retrieval data: eligible silver passages with embeddings and citation
-- metadata. Superseded filings are flagged, not dropped, so default retrieval
-- can exclude them while lineage stays complete.
-- Policy is documented in docs/setup.md.
{{ config(materialized='table') }}

{{ select_retrieval_passages(
    ref('passages'),
    ref('filings'),
    source('silver_external', 'passage_embeddings')
) }}
