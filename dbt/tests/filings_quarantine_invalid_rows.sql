-- Quarantine regression for filing validation: missing accession, unsupported
-- form, invalid filing/report dates, a source-linked extraction failure, and a
-- filing whose company/accession contradicts its bronze manifest all quarantine
-- with a reason; a consistent filing passes.
with source as (
    select * from (values
        (1::bigint, 1::int, 'acc'::text, '10-K'::text, null::text, 'http://x'::text, '2024-11-01'::text, '2024-09-28'::text, null::text),
        (2, 1, '', '10-K', null, 'http://x', '2024-11-01', '2024-09-28', null),
        (3, 1, 'acc', '8-K', null, 'http://x', '2024-11-01', '2024-09-28', null),
        (4, 1, 'acc', '10-K', null, 'http://x', '2024-13-01', '2024-09-28', null),
        (5, 1, 'acc', '10-K', null, 'http://x', '2024-11-01', '2024-02-30', null),
        (6, 1, 'acc', '10-K', null, 'http://x', '2024-11-01', '2024-09-28', 'no_usable_text'),
        (7, 1, 'acc', '10-K', null, 'http://x', '2024-11-01', '2024-09-28', null),
        (8, 1, 'acc', '10-K', null, 'http://x', '2024-11-01', '2024-09-28', null),
        (9, 1, 'acc', '10-K', null, 'http://x', '2024-11-01', '2024-09-28', null)
    ) as s(manifest_id, cik, accession, form, primary_document, url,
           filing_date, report_date, extraction_error)
),
manifest as (
    select * from (values
        (1::bigint, 1::int, 'acc'::text),
        (2, 1, ''),
        (3, 1, 'acc'),
        (4, 1, 'acc'),
        (5, 1, 'acc'),
        (6, 1, 'acc'),
        (7, 1, 'different'),
        (8, 999, 'acc')
    ) as m(id, cik, accession)
),
staged as (
    {{ staged_filings('source', 'manifest') }}
),
expected as (
    select * from (values
        (1::bigint, null::text),
        (2, 'missing_accession'),
        (3, 'unsupported_form'),
        (4, 'missing_or_invalid_filing_date'),
        (5, 'missing_or_invalid_report_date'),
        (6, 'no_usable_text'),
        (7, 'accession_manifest_mismatch'),
        (8, 'cik_manifest_mismatch'),
        (9, 'unknown_bronze_manifest')
    ) as e(manifest_id, reason)
),
mismatches as (
    select s.manifest_id
    from staged s
    join expected e using (manifest_id)
    where s.quarantine_reason is distinct from e.reason
)
select
    (select count(*) from mismatches) as reason_mismatches,
    (select count(*) from staged) as staged_rows,
    (select count(*) from expected) as expected_rows
where (select count(*) from mismatches) > 0
   or (select count(*) from staged) <> (select count(*) from expected)
