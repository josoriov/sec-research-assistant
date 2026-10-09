-- Supersession regression: a filing superseded by a later-filed 10-K/A for the
-- same (cik, report_date) is flagged is_superseded = true, while the amendment is
-- not. Runs the real select_retrieval_passages macro on a fixture, so a
-- regression in the supersession rule fails here.
with filings as (
    select * from (values
        (10::bigint, 1::int, 'orig'::text, '10-K'::text, '2024-11-01'::date, '2024-09-28'::date),
        (11, 1, 'amend', '10-K/A', '2025-01-15', '2024-09-28'),
        (12, 1, 'other-year', '10-K', '2023-11-03', '2023-09-30')
    ) as f(manifest_id, cik, accession, form, filing_date, report_date)
),
passages as (
    select * from (values
        (100::bigint, 1::int, 'orig'::text, 10::bigint, 'h-orig'::text, '{{ var("active_processing_version") }}'::text, 'Item 7.'::text, 'Item 7.'::text, 0::int, 'original text'::text, 'http://x/orig'::text),
        (101, 1, 'amend', 11, 'h-amend', '{{ var("active_processing_version") }}', 'Item 7.', 'Item 7.', 0, 'amended text', 'http://x/amend'),
        (102, 1, 'other-year', 12, 'h-other', '{{ var("active_processing_version") }}', 'Item 7.', 'Item 7.', 0, 'other year text', 'http://x/other')
    ) as p(block_id, cik, accession, manifest_id, passage_hash, processing_version,
           section, heading, block_ordinal, text, url)
),
embeddings as (
    select * from (values
        ('h-orig'::text, '{{ var("active_processing_version") }}'::text, 'sentence-transformers/all-MiniLM-L6-v2'::text, 384::int, '[0,0]'::vector),
        ('h-amend', '{{ var("active_processing_version") }}', 'sentence-transformers/all-MiniLM-L6-v2', 384, '[0,0]'),
        ('h-other', '{{ var("active_processing_version") }}', 'sentence-transformers/all-MiniLM-L6-v2', 384, '[0,0]')
    ) as e(passage_hash, processing_version, model_version, dim, embedding)
),
result as (
    {{ select_retrieval_passages('passages', 'filings', 'embeddings') }}
)
select
    (select count(*) from result) as result_rows,
    (select is_superseded from result where accession = 'orig') as orig_superseded,
    (select is_superseded from result where accession = 'amend') as amend_superseded,
    (select is_superseded from result where accession = 'other-year') as other_superseded
where (select count(*) from result) <> 3
   or (select is_superseded from result where accession = 'orig') is not true
   or (select is_superseded from result where accession = 'amend') is not false
   or (select is_superseded from result where accession = 'other-year') is not false
