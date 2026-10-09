-- F009 regression: when a period is disclosed 100 (10-K), restated to 200, then
-- restated back to 100, gold must serve the latest disclosure (100, accession c)
-- rather than the March 200. Runs the real select_annual_metrics macro on a
-- fixture so a regression fails here.
with fixture as (
    select * from (values
        (1::bigint, 1::bigint, 1::int, 'us-gaap:NetIncomeLoss'::text, 'us-gaap'::text, 'NetIncomeLoss'::text, 'USD'::text, '2023-01-01'::date, '2023-12-31'::date, 100::numeric, 2023::int, 'FY'::text, '10-K'::text, 'a'::text, '2024-02-01'::date, null::text),
        (2, 1, 1, 'us-gaap:NetIncomeLoss', 'us-gaap', 'NetIncomeLoss', 'USD', '2023-01-01', '2023-12-31', 200, 2023, 'FY', '10-K/A', 'b', '2024-03-01', null),
        (3, 1, 1, 'us-gaap:NetIncomeLoss', 'us-gaap', 'NetIncomeLoss', 'USD', '2023-01-01', '2023-12-31', 100, 2023, 'FY', '10-K/A', 'c', '2024-04-01', null)
    ) as t(source_fact_id, manifest_id, cik, concept, taxonomy, tag, unit,
           period_start, period_end, value, fiscal_year, fiscal_period, form,
           accession, filed_date, frame)
),
result as (
    {{ select_annual_metrics('fixture') }}
)
select
    (select count(*) from result) as result_rows,
    (select count(*) from result
      where source_fact_id = 3 and value = 100 and accession = 'c' and is_ambiguous) as latest_selected
where (select count(*) from result) <> 1
   or (select count(*) from result
        where source_fact_id = 3 and value = 100 and accession = 'c' and is_ambiguous) <> 1
