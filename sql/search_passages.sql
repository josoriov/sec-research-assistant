-- Approved tool: exact similarity search over published gold retrieval passages,
-- restricted to the requested fiscal years and/or company before ranking.
--
-- Values are bound by the driver. The optional fiscal-year filter matches the
-- year of the passage's filing report_date (gold metadata), so a request limited
-- to FY2023 cannot return a FY2025 passage. Superseded filings are excluded by
-- default. Only gold.retrieval_passages is read; carried citation metadata is
-- returned.
--
-- Parameters:
--   %(query_vector)s        text   embedding literal of the question
--   %(model_version)s       text   embedding model version to match
--   %(cik)s                 int    optional company filter (NULL = any)
--   %(accession)s           text   optional accession filter (NULL = any)
--   %(fiscal_years)s        int[]  optional report-year filter (NULL = any)
--   %(include_superseded)s  bool   include passages from superseded filings
--   %(limit)s               int    maximum rows
select
    p.passage_id,
    p.cik,
    p.accession,
    p.section,
    p.heading,
    p.url,
    p.text,
    1 - (p.embedding <=> %(query_vector)s::vector) as similarity
from gold.retrieval_passages p
where p.model_version = %(model_version)s
  and (%(cik)s::integer is null or p.cik = %(cik)s)
  and (%(accession)s::text is null or p.accession = %(accession)s)
  and (%(fiscal_years)s::integer[] is null
       or extract(year from p.report_date)::integer = any(%(fiscal_years)s::integer[]))
  and (%(include_superseded)s or p.is_superseded = false)
order by p.embedding <=> %(query_vector)s::vector
limit %(limit)s
