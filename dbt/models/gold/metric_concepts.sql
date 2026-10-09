-- Documented concept mapping: which XBRL tag (and unit) represents each
-- supported metric. The MVP scope is revenue, net income, and operating cash
-- flow for recent 10-K filings, so each metric has one tag. Add a row to
-- support more concepts; silver.financial_facts keeps every valid fact, so no
-- ingestion change is needed.
--
--   revenue              net sales / total revenues
--   net_income           net income (loss) attributable to the company
--   operating_cash_flow  net cash provided by operating activities
{{ config(materialized='table') }}

select 'revenue' as metric, 'us-gaap' as taxonomy,
       'RevenueFromContractWithCustomerExcludingAssessedTax' as tag, 'USD' as unit
union all
select 'net_income', 'us-gaap', 'NetIncomeLoss', 'USD'
union all
select 'operating_cash_flow', 'us-gaap', 'NetCashProvidedByUsedInOperatingActivities', 'USD'
