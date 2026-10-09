# SEC Research Assistant — Implementation Guide

This guide expands the [project plan](sec-research-assistant.md) into practical implementation steps. It describes the intended build, not completed functionality.

Start with one company, then expand to five companies, three years of annual reports (10-K filings), and three metrics: revenue, net income, and operating cash flow.

The system has two workflows: **prepare data ahead of time**, then **retrieve evidence and answer questions on demand**. SQL calculates the numbers; filing passages provide supporting explanations; the language model writes the answer.

## Medallion contract

Use [bronze → silver → gold](https://docs.databricks.com/aws/en/lakehouse/medallion) as logical quality layers in the existing stack:

| Layer | Location | Contents |
| --- | --- | --- |
| Bronze: raw | MinIO `bronze/`; PostgreSQL `bronze` schema | Original JSON/HTML snapshots, `manifest`, and source-faithful `source_facts`. |
| Silver: validated | PostgreSQL `silver` schema | Typed `financial_facts`, normalized `filings`, and clean `passages`, retaining disclosure history. |
| Gold: serving | PostgreSQL `gold` schema | Selected `annual_metrics` and eligible `retrieval_passages` with embeddings and citations. |

Read each layer from its persisted predecessor. Carry source identifiers through every transformation. Quarantine invalid records with reasons and bronze references; publish gold only after checks pass. FastAPI reads only published gold. This applies to both financial data and document retrieval.

## 1. Set up the local environment

**Technology:** Python, [Docker Compose](https://docs.docker.com/compose/intro/compose-application-model/), PostgreSQL with pgvector, and MinIO.

1. Define PostgreSQL, MinIO, and the Python application in `compose.yaml`. Add Airflow after the pipeline works manually.
2. Configure persistent volumes so database contents and downloaded files survive container restarts.
3. Supply credentials through environment variables; keep local secrets out of Git.
4. Create `bronze`, `silver`, and `gold` PostgreSQL schemas and a MinIO `bronze/` prefix. Configure dbt models to write to their intended schemas and verify the actual relation names.
5. Verify database and object-storage access. Give the API role read-only access to published gold datasets; use separate pipeline credentials.

**Result:** a reproducible local environment. PostgreSQL is the shared database; MinIO is the archive of original files.

## 2. Ingest bronze: preserve the originals

**Technology:** Python, [SEC APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), and the [MinIO Python SDK](https://github.com/minio/minio-py).

1. Maintain a small mapping of company names and tickers to CIKs, the SEC's company identifiers.
2. Fetch submission history and Company Facts JSON. Follow older-history references when needed to find the requested years.
3. Select the relevant 10-K filings, identify associated amendments, and download their primary report documents from EDGAR.
4. Save original JSON/HTML bytes under `bronze/`, keyed by company, source, and content hash. Preserve changed responses as new objects. Track URL, accession number (filing identifier), retrieval time, hash, and processing status in `bronze.manifest`.
5. Identify the downloader, throttle requests, and retry temporary errors according to [SEC access guidance](https://www.sec.gov/about/developer-resources). Skip unchanged content and record failures for retry.

**Result:** preserved bronze snapshots. Downstream steps read these objects; ingestion never writes directly to silver or gold.

## 3. Build silver facts and gold financial marts

**Technology:** Python, PostgreSQL, and [dbt](https://docs.getdbt.com/docs/introduction).

1. Unpack persisted Company Facts JSON into `bronze.source_facts`, retaining source fields and the manifest reference without business filtering.
2. Use dbt models—SQL queries that build tables or views—to create `silver.financial_facts`: type values/dates, normalize units, and deduplicate exact disclosures. Keep distinct filings and restatement history.
3. Test required fields, fact grain uniqueness, units, periods, and bronze references. Quarantine invalid records; retain valid detailed facts beyond the selected annual metrics.
4. Derive `gold.annual_metrics` from silver. Map concepts to the supported metrics and document annual-value, amendment, and restatement selection rules. Flag unresolved ambiguity; distinguish fiscal periods from filing years.
5. Check gold uniqueness by company/metric/period/unit and retain selected silver fact IDs and SEC source metadata. Stage and validate candidate outputs before publication.

**Result:** SQL-ready financial data. Annual, quarterly, and year-to-date values must never be mixed in a comparison.

## 4. Build silver passages and gold retrieval data

**Technology:** Python, an HTML parser such as [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/), an embedding model, and [pgvector](https://github.com/pgvector/pgvector).

1. Read bronze HTML and populate `silver.filings` and `silver.passages`. Extract sections and bounded passages, preserving headings, meaningful table content, and context.
2. Store text, company, accession, section, URL, bronze object reference, passage hash, and processing version. Validate nonempty text and source relationships; quarantine extraction failures.
3. Build candidate `gold.retrieval_passages` from validated silver passages. Apply supersession rules and generate embeddings—numerical representations of meaning—for eligible content.
4. Retain silver passage IDs, citation metadata, and embedding model version. Reuse vectors only when content, processing version, and model version match; check dimensions and missing embeddings before publication.
5. Search published gold using an embedding of the question, filtering by company and relevant filings. Start with exact similarity search; add approximate indexes only if measured latency requires them.

**Result:** gold retrieval data backed by silver text and bronze originals. Keep superseded text in silver but exclude it from default gold retrieval. Similarity alone does not establish answer support.

## 5. Handle questions and calculate results

**Technology:** [FastAPI](https://fastapi.tiangolo.com/), request validation, and a PostgreSQL driver such as [Psycopg](https://www.psycopg.org/psycopg3/docs/basic/params.html).

1. Expose `POST /questions`, initially usable through an API client or a small web interface.
2. Resolve and validate company, metric, and requested periods. Request clarification when essential details are ambiguous.
3. Route requests to a small set of approved tools: get a metric, compare periods, and search passages. Validate any model-selected arguments.
4. Execute parameterized SQL templates against `gold.annual_metrics` using the gold-only API role. Calculate changes in SQL; handle missing values and zero denominators explicitly.
5. Retrieve supporting evidence from `gold.retrieval_passages`; use its carried citation metadata without querying lower layers.

**Result:** an evidence package containing calculations, source references, and relevant text. Arbitrary model-generated SQL is outside the MVP.

## 6. Compose an answer with citations

**Technology:** an existing language model accessed through an API; no model training is required.

1. Send the question, calculation results, and selected passages to the model with stable source identifiers.
2. Instruct it to use the supplied evidence, distinguish reported explanations from inference, and acknowledge missing or conflicting information.
3. Treat document text as evidence, never as instructions. Map citation identifiers to application-supplied URLs and sections, and reject unknown identifiers.
4. Return the answer with financial sources and passage citations. Record model usage, latency, and API cost without logging credentials.

**Result:** an answer combining verified calculations and cited explanations. This is retrieval-augmented generation (RAG): retrieve evidence first, then generate the response. Valid citation identifiers still require evaluation of whether the evidence supports the claim.

## 7. Schedule the preparation pipeline

**Technology:** [Apache Airflow](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html).

1. Wrap the working Python functions and dbt commands in an Airflow DAG, a graph of tasks and dependencies.
2. Enforce bronze ingestion → silver transformations/checks → gold candidate build/checks → publication for both financial and document branches.
3. Configure scheduling, retries, and visible failure logs. Pass file references between tasks instead of large documents.
4. Publish the validated gold build atomically using PostgreSQL transactions. A failed build leaves the previous gold publication available; dbt tests alone do not hide failed outputs from the API.
5. Demonstrate a duplicate rerun, a rebuild from bronze without SEC downloads, and recovery from download/validation failures. Use hashes and uniqueness constraints to prevent duplicates.

**Result:** repeatable background preparation. Airflow manages the pipeline; FastAPI handles questions independently.

## 8. Expand and evaluate

1. Expand the verified one-company workflow to the full sample scope.
2. Create 20–25 manually checked questions covering calculations, explanations, combined questions, and unsupported requests.
3. Measure numerical accuracy, retrieval recall, citation support, appropriate abstention, latency, and API cost. Include documents containing misleading instructions.
4. Verify gold → silver → bronze lineage for sample answers, rejection of invalid records, preservation of changed raw snapshots, and denial of API access to lower layers.
5. Document setup, ingestion, serving, and recovery commands. Verify the complete workflow from a fresh checkout.

**Done:** bronze is preserved; silver and gold rebuild with quality gates; the API serves only validated gold. Answers are traceable, reruns are safe, and an evaluation report records actual performance and limitations.
