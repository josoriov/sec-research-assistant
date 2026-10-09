-- Shared validation and selection for the document/retrieval branch, kept in
-- macros so the fixture regression tests exercise the exact model logic.
-- Policy is documented in docs/setup.md.

{% macro staged_filings(source_relation, manifest_relation) %}
with typed as (
    select
        fd.manifest_id,
        fd.cik,
        btrim(fd.accession) as accession,
        btrim(fd.form) as form,
        fd.primary_document,
        fd.url,
        {{ safe_date('fd.filing_date') }} as filing_date,
        {{ safe_date('fd.report_date') }} as report_date,
        fd.extraction_error,
        m.cik as manifest_cik,
        btrim(m.accession) as manifest_accession
    from {{ source_relation }} fd
    left join {{ manifest_relation }} m on m.id = fd.manifest_id
)

select
    *,
    case
        when accession is null or accession = '' then 'missing_accession'
        when form is null or form not in ('10-K', '10-K/A') then 'unsupported_form'
        when filing_date is null then 'missing_or_invalid_filing_date'
        when report_date is null then 'missing_or_invalid_report_date'
        when manifest_cik is null then 'unknown_bronze_manifest'
        when manifest_cik is distinct from cik then 'cik_manifest_mismatch'
        when manifest_accession is distinct from accession then 'accession_manifest_mismatch'
        when extraction_error is not null then extraction_error
        else null
    end as quarantine_reason
from typed
{% endmacro %}

{% macro staged_document_blocks(blocks_relation, filings_relation) %}
with typed as (
    select
        b.id as block_id,
        b.manifest_id,
        b.cik,
        btrim(b.accession) as accession,
        b.block_ordinal,
        btrim(b.section) as section,
        btrim(b.heading) as heading,
        btrim(b.text) as text,
        b.block_hash as passage_hash,
        b.processing_version
    from {{ blocks_relation }} b
),

joined as (
    select
        t.*,
        f.manifest_id as filing_manifest_id,
        f.cik as filing_cik,
        f.accession as filing_accession,
        f.url as url
    from typed t
    left join {{ filings_relation }} f on f.manifest_id = t.manifest_id
)

select
    *,
    case
        when text is null or text = '' then 'missing_text'
        when accession is null or accession = '' then 'missing_accession'
        when passage_hash is null or passage_hash = '' then 'missing_passage_hash'
        when processing_version is null or processing_version = '' then 'missing_processing_version'
        when filing_manifest_id is null then 'unknown_filing'
        when filing_cik is distinct from cik then 'cik_mismatch'
        when filing_accession is distinct from accession then 'accession_mismatch'
        else null
    end as quarantine_reason
from joined
{% endmacro %}

{#
  Supersession: a filing is superseded when a later-filed 10-K/10-K-A for the
  same (cik, report_date) exists. Superseded passages stay in silver; the flag
  lets default retrieval exclude them.
#}
{% macro select_retrieval_passages(passages_relation, filings_relation, embeddings_relation) %}
with filings_superseded as (
    select
        f.*,
        exists (
            select 1
            from {{ filings_relation }} newer
            where newer.cik = f.cik
              and newer.report_date is not distinct from f.report_date
              and newer.filing_date > f.filing_date
        ) as is_superseded
    from {{ filings_relation }} f
),

joined as (
    select
        p.block_id as passage_id,
        p.cik,
        p.accession,
        p.manifest_id,
        p.passage_hash,
        p.processing_version,
        p.section,
        p.heading,
        p.block_ordinal,
        p.text,
        p.url,
        f.form,
        f.filing_date,
        f.report_date,
        f.is_superseded,
        e.model_version,
        e.dim,
        e.embedding
    from {{ passages_relation }} p
    join filings_superseded f on f.manifest_id = p.manifest_id
    join {{ embeddings_relation }} e
      on e.passage_hash = p.passage_hash
     and e.processing_version = p.processing_version
     and e.model_version = '{{ var("embedding_model_version") }}'
    where p.processing_version = '{{ var("active_processing_version") }}'
)

select * from joined
{% endmacro %}
