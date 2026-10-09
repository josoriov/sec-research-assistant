-- F009 regression: an earlier ineligible-form (10-Q) disclosure with the same
-- value must not hide the later eligible 10-K annual disclosure. Runs the real
-- select_annual_metrics macro on a fixture.
with fixture as (
    select * from (values
        (10::bigint, 1::bigint, 1::int, 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'::text, 'us-gaap'::text, 'RevenueFromContractWithCustomerExcludingAssessedTax'::text, 'USD'::text, '2022-01-01'::date, '2022-12-31'::date, 500::numeric, 2022::int, 'FY'::text, '10-Q'::text, 'q'::text, '2022-11-01'::date, null::text),
        (11, 1, 1, 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax', 'us-gaap', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'USD', '2022-01-01', '2022-12-31', 500, 2022, 'FY', '10-K', 'k', '2023-02-01', null)
    ) as t(source_fact_id, manifest_id, cik, concept, taxonomy, tag, unit,
           period_start, period_end, value, fiscal_year, fiscal_period, form,
           accession, filed_date, frame)
),
result as (
    {{ select_annual_metrics('fixture') }}
)
select
    (select count(*) from result) as result_rows,
    (select count(*) from result where source_fact_id = 11 and accession = 'k' and not is_ambiguous) as eligible_selected
where (select count(*) from result) <> 1
   or (select count(*) from result where source_fact_id = 11 and accession = 'k' and not is_ambiguous) <> 1
