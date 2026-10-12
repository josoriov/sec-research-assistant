-- Gold retrieval data: eligible silver passages with embeddings and citation
-- metadata. Superseded filings are flagged, not dropped, so default retrieval
-- can exclude them while lineage stays complete.
-- Policy is documented in docs/setup.md.
-- `gold_candidate_suffix` mirrors annual_metrics so the publisher can build a
-- consistent candidate set (see airflow/pipeline.py).
{{ config(
    materialized='table',
    alias='retrieval_passages' ~ var('gold_candidate_suffix', ''),
    post_hook=revoke_candidate_api_select(),
) }}

{{ select_retrieval_passages(
    ref('passages'),
    ref('filings'),
    source('silver_external', 'passage_embeddings')
) }}
