-- F010/F011 regression: the staging validation must quarantine out-of-range
-- dates (including year zero), missing required fields, unsupported units, and
-- numeric overflow with a reason, while valid (leap) dates pass. Runs the real
-- staged_source_facts macro on a fixture, so it fails if validation regresses.
with fixture as (
    select * from (values
        (1::bigint, 1::bigint, 1::int, 'us-gaap:X'::text, 'us-gaap'::text, 'X'::text, 'USD'::text, 'a'::text, '1'::text, '2023-01-01'::text, '2023-02-30'::text, 2023::int, 'FY'::text, '10-K'::text, null::text, '2024-02-01'::text),
        (2, 1, 1, 'us-gaap:X', 'us-gaap', 'X', 'USD', 'a', '1', '2023-03-01', '2024-02-29', 2024, 'FY', '10-K', null, '2024-03-01'),
        (3, 1, 1, 'us-gaap:X', 'us-gaap', 'X', 'USD', 'a', '1', '2022-03-01', '2023-02-29', 2023, 'FY', '10-K', null, '2023-03-01'),
        (4, 1, 1, 'us-gaap:X', 'us-gaap', 'X', 'USD', '',  '1', '2023-01-01', '2023-12-31', 2023, 'FY', '10-K', null, '2024-02-01'),
        (5, 1, 1, 'us-gaap:X', 'us-gaap', 'X', 'bananas', 'a', '1', '2023-01-01', '2023-12-31', 2023, 'FY', '10-K', null, '2024-02-01'),
        (6, 1, 1, '',          'us-gaap', 'X', 'USD', 'a', '1', '2023-01-01', '2023-12-31', 2023, 'FY', '10-K', null, '2024-02-01'),
        (7, 1, 1, 'us-gaap:X', 'us-gaap', 'X', 'USD', 'a', '1', '2023-01-01', '2023-12-31', 2023, 'FY', '10-K', null, null),
        (8, 1, 1, 'us-gaap:X', 'us-gaap', 'X', 'USD', 'a', null, '2023-01-01', '2023-12-31', 2023, 'FY', '10-K', null, '2024-02-01'),
        (9, 1, 1, 'us-gaap:X', 'us-gaap', 'X', 'USD', 'a', 'not-a-number', '2023-01-01', '2023-12-31', 2023, 'FY', '10-K', null, '2024-02-01'),
        (10, 1, 1, 'us-gaap:X', 'us-gaap', 'X', 'USD', 'a', '1', '2023-01-01', '0000-12-31', 2023, 'FY', '10-K', null, '2024-02-01'),
        (11, 1, 1, 'us-gaap:X', 'us-gaap', 'X', 'USD', 'a', '1', '0000-01-01', '2023-12-31', 2023, 'FY', '10-K', null, '2024-02-01'),
        (12, 1, 1, 'us-gaap:X', 'us-gaap', 'X', 'USD', 'a', '1', '2023-01-01', '2023-12-31', 2023, 'FY', '10-K', null, '0000-01-01'),
        (13, 1, 1, 'us-gaap:X', 'us-gaap', 'X', 'USD', 'a', repeat('1', 131073), '2023-01-01', '2023-12-31', 2023, 'FY', '10-K', null, '2024-02-01')
    ) as t(id, manifest_id, cik, concept, taxonomy, tag, unit, accession, value_text,
           start_date, end_date, fiscal_year, fiscal_period, form, frame, filed_date)
),
staged as (
    {{ staged_source_facts('fixture') }}
),
expected as (
    select * from (values
        (1::bigint, 'missing_or_invalid_period_end'::text),
        (2, null),
        (3, 'missing_or_invalid_period_end'),
        (4, 'missing_accession'),
        (5, 'unsupported_unit'),
        (6, 'missing_concept'),
        (7, 'missing_or_invalid_filed_date'),
        (8, 'missing_value'),
        (9, 'non_numeric_value'),
        (10, 'missing_or_invalid_period_end'),
        (11, 'invalid_period_start'),
        (12, 'missing_or_invalid_filed_date'),
        (13, 'non_numeric_value')
    ) as e(source_fact_id, reason)
),
mismatches as (
    select s.source_fact_id
    from staged s
    join expected e using (source_fact_id)
    where s.quarantine_reason is distinct from e.reason
)
select
    (select count(*) from mismatches) as reason_mismatches,
    (select count(*) from staged) as staged_rows,
    (select count(*) from expected) as expected_rows
where (select count(*) from mismatches) > 0
   or (select count(*) from staged) <> (select count(*) from expected)
