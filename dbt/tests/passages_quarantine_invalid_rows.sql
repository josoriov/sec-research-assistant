-- Quarantine regression: invalid blocks (missing text/accession/hash/version, no
-- matching filing, or company/accession that disagrees with the cited filing) are
-- routed to quarantine with a reason, while a valid block passes. Runs the real
-- staged_document_blocks macro on a fixture.
with blocks as (
    select * from (values
        (1::bigint, 10::bigint, 1::int, 'acc'::text, 0::int, 'Item 7.'::text, 'Item 7.'::text, 'valid text'::text, 'h1'::text, 'extract-v1'::text),
        (2, 10, 1, 'acc', 1, null, null, '', 'h2', 'extract-v1'),
        (3, 10, 1, '', 2, null, null, 'x', 'h3', 'extract-v1'),
        (4, 10, 1, 'acc', 3, null, null, 'x', '', 'extract-v1'),
        (5, 10, 1, 'acc', 4, null, null, 'x', 'h5', ''),
        (6, 999, 1, 'acc', 5, null, null, 'x', 'h6', 'extract-v1'),
        (7, 10, 999, 'acc', 6, null, null, 'x', 'h7', 'extract-v1'),
        (8, 10, 1, 'wrong', 7, null, null, 'x', 'h8', 'extract-v1')
    ) as b(id, manifest_id, cik, accession, block_ordinal, section, heading,
           text, block_hash, processing_version)
),
filings as (
    select * from (values (10::bigint, 1::int, 'acc'::text, 'http://x'::text))
        as f(manifest_id, cik, accession, url)
),
staged as (
    {{ staged_document_blocks('blocks', 'filings') }}
),
expected as (
    select * from (values
        (1::bigint, null::text),
        (2, 'missing_text'),
        (3, 'missing_accession'),
        (4, 'missing_passage_hash'),
        (5, 'missing_processing_version'),
        (6, 'unknown_filing'),
        (7, 'cik_mismatch'),
        (8, 'accession_mismatch')
    ) as e(block_id, reason)
),
mismatches as (
    select s.block_id
    from staged s
    join expected e using (block_id)
    where s.quarantine_reason is distinct from e.reason
)
select
    (select count(*) from mismatches) as reason_mismatches,
    (select count(*) from staged) as staged_rows,
    (select count(*) from expected) as expected_rows
where (select count(*) from mismatches) > 0
   or (select count(*) from staged) <> (select count(*) from expected)
