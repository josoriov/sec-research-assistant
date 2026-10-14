# Local environment setup

Start with the [quickstart](run.md). This reference explains the implemented
pipeline, manual stages, API contract, evaluation, and recovery. Planned UI and
question interpretation work is listed in the public [roadmap](../TODO.md).

The `compose.yaml` at the repository root follows the Compose specification, so
it runs under **Docker Compose** or **Podman Compose**. Every credential is read
from the environment; nothing secret is committed.

## Prerequisites

- Docker with the Compose plugin (`docker compose version`), **or** Podman with
  `podman-compose` (`podman-compose version`).
- Network access to pull container images on first start.

### CPU Python dependencies

This is optional for host development and evaluation; the container quickstart
does not require host Python. For this section, install Python 3.12 first.

The API and Airflow images install CPU-only PyTorch before the locked
shared dependencies at build time; startup never installs packages. For a local Python 3.12 virtual environment, run the same
two steps from the repository root:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --no-deps --index-url https://download.pytorch.org/whl/cpu -r requirements-cpu.txt
python -m pip install -r requirements.lock
python -m pip check
```

`requirements-cpu.txt` pins the CPU wheel and is also a constraint included by
`requirements.txt`, so later project installs cannot replace it with a GPU build.
Only PyTorch is installed from the official CPU index; the remaining packages
come from PyPI. The locks target Python 3.12 on Linux x86-64. Install the CPU
wheel first in a fresh virtual environment. dbt is installed in the Airflow
image from `airflow/requirements.lock`; no host dbt installation is needed.

The encoder explicitly uses CPU. To verify the package build (even on a machine
without a GPU), check `python -c 'import torch; print(torch.version.cuda)'`:
the CPU build prints `None`. `torch.cuda.is_available()` alone cannot distinguish
a CPU wheel from a CUDA wheel running without a GPU.

## 1. Configure the environment

```sh
test -f .env || cp .env.example .env
chmod 600 .env
```

Edit `.env` and replace every `change-me-*` value with a local password. `.env`
is git-ignored and must never be committed.

Also set `SEC_USER_AGENT` to a descriptive value with your contact details, for
example `sec-research-assistant you@example.com`. SEC requires an identifying
agent and may block requests without one; the ingester refuses to start if it is
missing or has no `@`.

`docker compose config` fails if a required variable is missing, which keeps a
partly configured environment from starting silently.

## 2. Start the stack

```sh
docker compose build app airflow
docker compose up -d
```

With Podman, use `podman-compose up -d` (or `podman compose up -d`). All other
commands below work with either engine; substitute `podman-compose` for
`docker compose`.

## 3. Services

| Service | Image | Purpose |
| --- | --- | --- |
| `postgres` | `pgvector/pgvector:pg16` | Shared database with the `bronze`, `silver`, and `gold` schemas. |
| `minio` | Chainguard MinIO | S3-compatible archive; holds the `bronze/` bucket. |
| `minio-init` | Chainguard `mc` client | One-shot: creates the `bronze` bucket, then exits. |
| `app` | API image (`api/Dockerfile`) | API only; non-root, read-only filesystem, no checkout mount or pipeline/storage credentials. |
| `airflow-db-init` | `postgres:16` | One-shot: creates the `airflow` metadata database if missing, then exits. |
| `airflow` | Airflow image (`airflow/Dockerfile`) | Airflow 3 pipeline scheduler/UI (section 10). Installs the pipeline dependencies and `dbt-postgres`; the repo is mounted read-only. |

`postgres` and `minio` write to the named volumes `pgdata` and `minio-data`, so
database contents and downloaded files survive `docker compose restart` and
`docker compose down`. Use `docker compose down -v` to delete them.

## 4. Verify

Run the bundled check:

```sh
COMPOSE="docker compose" ./db/verify.sh     # Docker
COMPOSE="podman-compose" ./db/verify.sh     # Podman
```

It asserts that pgvector is installed and usable, the schemas and roles exist,
the API role is read-only and restricted to `gold`, and the configured bucket is
reachable, and exits non-zero on the first failure. The bucket comes from the
Airflow service's Compose-resolved environment, including quoted `.env` values and
shell overrides; the one-shot Python command needs no installed packages.
Equivalent manual checks:

```sh
docker compose exec postgres psql -U sec_admin -d sec_research -c '\dx' -c '\dn' -c '\du'
docker compose run --rm --no-deps minio-init ls local/bronze
```

## 5. Ingest bronze

The ingester fetches one company's SEC submission history (following older
history files when the recent list does not reach the requested years), Company
Facts, and the primary documents for each requested annual report and all of its
10-K/A amendments. It saves the original bytes to the `bronze` MinIO bucket and
records them in `bronze.manifest` and `bronze.source_facts`. It does not write to
silver or gold.

```sh
docker compose exec -T airflow python -m ingestion --company AAPL --years 3
```

`--years` must be positive; invalid counts fail before any network or storage access.

Company/ticker → CIK mappings live in `ingestion/mappings/companies.json`. The
ingester applies `ingestion/schema.sql` on each run, so the bronze tables are
created idempotently on fresh and pre-existing volumes (initialization hooks do
not rerun). Objects are keyed by company, source, and content hash
(`<cik>/<source>/<sha256>.<ext>`); an unchanged rerun skips the object and the
manifest row, and a changed response is stored as a new object without
overwriting the old one. A download that exhausts its retries is recorded as a
`failed` manifest row (with the URL, accession, and error, but no object) so the
source is visible for retry; a later successful fetch marks that failure
`resolved` without duplicating the stored object.

Inspect what was ingested:

```sh
docker compose exec postgres psql -U sec_admin -d sec_research \
  -c 'SELECT source, accession, status, retrieved_at FROM bronze.manifest ORDER BY retrieved_at' \
  -c 'SELECT count(*) FROM bronze.source_facts'
docker compose run --rm --no-deps minio-init ls --recursive local/bronze
```

Run the ingestion tests (no network needed):

```sh
pytest tests/ingestion
```

## 6. Build silver and gold with dbt

Silver and gold are built from persisted bronze with dbt; the models live under
`dbt/`. Run the ingestion first (section 5) so `bronze.source_facts` has data.

dbt-core and its PostgreSQL adapter run in the Airflow container. Connection
details come from Compose (`dbt/profiles.yml`); the working directory is the
repository root inside that container.

The image disables dbt's automatic `.env` loading. Compose supplies the required
variables directly; the host `.env` stays mode `600` and need not be readable by
the container user.

```sh
docker compose exec -T airflow dbt build --project-dir dbt --profiles-dir dbt
```

`dbt build` runs the models in dependency order and then their tests; any failed
test marks the build failed (nonzero exit).

| Model | Layer | Grain |
| --- | --- | --- |
| `stg_source_facts` | silver (view) | one bronze fact, typed, with a quarantine reason |
| `financial_fact_disclosures` | silver (table) | one row per valid disclosure, retaining every accession/form/filed_date |
| `financial_facts` | silver (table) | the above deduplicated to one row per exact disclosure: `(cik, concept, unit, period_start, period_end, value)` |
| `financial_facts_quarantine` | silver (table) | invalid facts plus the reason and bronze reference |
| `metric_concepts` | gold (table) | metric → XBRL tag/unit mapping |
| `annual_metrics` | gold (table) | one annual value per `(cik, metric, fiscal period, unit)` |
| `filings` | silver (table) | one validated filing per bronze filing manifest |
| `filings_quarantine` | silver (table) | invalid filings plus the reason |
| `passages` | silver (table) | validated, heading-aware passages with section, hash, processing version |
| `passages_quarantine` | silver (table) | invalid passages plus the reason |
| `retrieval_passages` | gold (table) | eligible silver passages joined to their embeddings, with citation metadata and a supersession flag |

Schemas are provisioned by `db/init/01-init.sh`. `dbt/macros/schema_routing.sql`
pins models to exactly `silver` and `gold` and suppresses dbt's own
`CREATE SCHEMA`, which keeps the pipeline role at schema-level (not
database-level) `CREATE` privileges.

### Metric mapping and annual selection

Implemented in `dbt/models/gold/metric_concepts.sql` and
`dbt/macros/annual_metrics.sql`:

- **revenue** → `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`,
  or `us-gaap:Revenues` when a filing reports total revenue under that more
  general tag (Apple reports the former from FY2017; Alphabet switched to
  `Revenues` in its FY2025 10-K; both tags carry the same total when present).
- **net_income** → `us-gaap:NetIncomeLoss`
- **operating_cash_flow** → `us-gaap:NetCashProvidedByUsedInOperatingActivities`

Only durational facts of about one year (350–380 days, covering 52/53-week
fiscal years) from 10-K/10-K/A filings with fiscal period FY, in the metric's
mapped unit (USD), qualify. Quarterly and year-to-date values therefore never
enter the mart and units are never mixed. Candidates come from the full
disclosure history (`silver.financial_fact_disclosures`), not the deduplicated
facts, so a restatement that reverts or an earlier ineligible form cannot hide
the latest eligible value. The latest `filed_date` wins; earlier disclosures stay
in `silver.financial_fact_disclosures`, and `annual_metrics.is_ambiguous` flags
periods with more than one distinct value across filings.

`financial_facts` deduplicates exact disclosures (the same value repeated as a
prior-year comparative) to one row that keeps the earliest filing as its bronze
reference; a restated, different value is kept as a separate row. Invalid facts
are quarantined with a reason and never reach gold; malformed dates and
out-of-range numerics are recognised with PostgreSQL's `pg_input_is_valid` so
they quarantine instead of aborting the build. `dbt/models/**/schema.yml`
and `dbt/tests/` assert required fields, grain uniqueness, the unit/period/annual
guards, every record's bronze and silver references, and staging/gold
regressions run the same macros the models use. A candidate is accepted only once
these checks pass; the Airflow DAG (section 10) builds these models under an
`__candidate` alias and publishes them atomically, so a failed build leaves the
previous gold dataset served. A manual `dbt build` at this point writes the
served gold relations directly.

Inspect the result and re-run the checks on their own:

```sh
docker compose exec postgres psql -U sec_admin -d sec_research \
  -c 'SELECT metric, fiscal_year, value, accession FROM gold.annual_metrics ORDER BY metric, fiscal_year' \
  -c 'SELECT count(*) FROM silver.financial_facts_quarantine'
docker compose exec -T airflow dbt test --project-dir dbt --profiles-dir dbt
```

The bronze ingestion tests are unaffected: `pytest tests/ingestion`.

## 7. Extract passages and build gold retrieval data

The document branch mirrors the financial branch but runs in four steps, because
dbt cannot parse HTML or compute embeddings:

1. **Extract** (`extraction/`, Python): read the stored filing HTML from bronze
   and write raw, heading-aware passages to `bronze.filing_documents` and
   `bronze.document_blocks`.
2. **Validate to silver** (dbt): build and test `silver.filings` and
   `silver.passages` (plus their quarantine tables).
3. **Embed** (`embeddings/`, Python): read `silver.passages` and write
   `silver.passage_embeddings`.
4. **Build and check gold** (dbt): build and test `gold.retrieval_passages`.

```sh
docker compose exec -T airflow python -m extraction
docker compose exec -T airflow dbt build --select silver --indirect-selection cautious --project-dir dbt --profiles-dir dbt
docker compose exec -T airflow python -m embeddings
docker compose exec -T airflow dbt build --project-dir dbt --profiles-dir dbt
```

The `--indirect-selection cautious` on the silver step keeps cross-layer tests
(which reference not-yet-built gold) out of that build; the final full `dbt build`
runs them once gold exists. With Podman, substitute `podman-compose exec -T airflow` and
`podman-compose`, as above.
Both images include the locked embedding dependencies. Model weights are
downloaded on first use; the API keeps its cache in writable temporary storage,
so a recreated API container downloads them again.
The embedding step must run between the silver and gold builds: gold joins each
silver passage to its vector, and the full build fails if any passage still lacks
one for the pinned model (`retrieval_passages_covers_all_passages`), so partial
retrieval data is never accepted.

### Extraction and retrieval selection

- Extraction walks block elements in document order, tracks the nearest
  `Item N.` / `PART N` heading as the passage's `section`, renders each whole
  table as row text (`a | b ; c | d`, including div/p-wrapped cells, preserving
  empty-cell positions and rendering nested rows once), and groups blocks into
  passages of at most 1500 characters (the joining spaces count toward the
  bound). Each passage's hash covers its text, section, and the processing
  version, so a re-extraction is idempotent and a new version is stored alongside
  the old rows. Text held directly in mixed-content containers (a block that also
  holds nested blocks) is not emitted; SEC prose and tables render as leaf blocks,
  so coverage is high.
- Only the active extraction version is served: `dbt/dbt_project.yml`
  `active_processing_version` (matching `extraction.PROCESSING_VERSION`) filters
  `gold.retrieval_passages` and the search, and embeddings are generated only for
  it. Older processing versions stay in bronze/silver for lineage but are never
  in default results, so a parser upgrade does not leave damaged text in serving.
  Bump the version when the parser changes.
- A stored document that yields no usable text records `extraction_error`
  (`no_usable_text`) in `bronze.filing_documents` and quarantines as a filing;
  it is never counted as a successful, evidence-free filing.
- Accession metadata is merged from every preserved submissions/history snapshot
  (NULL, empty, and whitespace-only newer fields count as missing and never erase
  a known value), so an older report whose accession has aged out of the newest
  `filings.recent` list keeps its form and dates. Filing company/accession are
  validated against `bronze.manifest`, and passage company/accession against the
  cited filing; inconsistent rows quarantine (`cik_manifest_mismatch`,
  `accession_manifest_mismatch`, `cik_mismatch`, `accession_mismatch`).
- `gold.retrieval_passages` is built only from validated silver passages joined
  to `silver.passage_embeddings`. A filing is flagged `is_superseded` when a
  later-filed 10-K or 10-K/A exists for the same `(cik, report_date)`; superseded
  passages stay in silver and in gold, and default retrieval filters
  `is_superseded = false`. Empty results must not be treated as no evidence
  without checking this flag.
- Vectors come from `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions,
  L2-normalized). `embeddings/` reuses a stored vector when
  `(passage_hash, processing_version, model_version)` already match, so a rerun
  re-embeds nothing; the model version and dimension are pinned in
  `dbt/dbt_project.yml` and checked by `dbt/tests/retrieval_passages_dimension.sql`.

### Search published gold passages

`embeddings/search.py` embeds a question with the same model and runs one
parameterized exact nearest-neighbor query against `gold.retrieval_passages`
only. It filters by company and/or accession and, by default, excludes
superseded filings and serves only the active processing version; it returns the
carried citation metadata and the full bounded passage text (the CLI prints a
short preview of that text).

```sh
docker compose exec -T airflow python -m embeddings.search \
  "how did revenue change and why?" --cik 320193 --limit 5
# add --include-superseded to search amended/superseded filings too
```

```sh
docker compose exec postgres psql -U sec_admin -d sec_research \
  -c 'SELECT count(*) FROM silver.passages' \
  -c 'SELECT is_superseded, count(*) FROM gold.retrieval_passages GROUP BY 1' \
  -c 'SELECT count(*) FROM silver.passages_quarantine'
```

## 8. Ask questions (FastAPI)

`api/` serves `POST /answer` over the published gold datasets only. It
connects with the read-only `GOLD_API_DB_USER` role, so the database — not just
the application — denies access to `silver` and `bronze`. Routing is
deterministic: the request is resolved and validated, then mapped to approved
tools. The LLM composes answers after retrieval; natural-language interpretation
of metric and year selections is planned work.

Compose starts the API automatically at `http://localhost:18000` with the example
ports. Use `/docs`, `/health`, or `POST /answer`; do not start a second API
process inside `app`.

For optional host development, install the lock above and source `.env`. Use a
separate port if the container API is running:

```sh
set -a; . ./.env; set +a
PGHOST=127.0.0.1 PGPORT="$POSTGRES_PORT" API_PORT=8901 python -m api
```

`API_HOST` and `API_PORT` control the host process. Compose fixes the container
port at 8000 and maps `.env`'s `API_PORT` to it on localhost.

### Request

```jsonc
POST /answer
{
  "company": "AAPL",          // ticker or numeric CIK (≤10 digits; required)
  "metric": "revenue",        // revenue | net_income | operating_cash_flow
  "fiscal_years": [2023, 2024], // one year for a value, two to compare
  "question": "why did revenue change?", // optional; retrieves passages
  "tool": "compare_periods",  // optional; inferred otherwise
  "limit": 5,                 // passages to return (1–20)
  "include_superseded": false // include superseded filings
}
```

The tool is inferred when omitted: a metric with two fiscal years compares them,
a metric alone (or with one year) reads values, and a `question` searches
passages. Both a metric and a question run both tools. `fiscal_years` are bounded
to 1900–2100; structurally invalid input returns HTTP 422. When `fiscal_years`
is supplied, passage retrieval is restricted to filings whose report date falls
in those years, so a FY2023 request cannot return a FY2025 passage.

### Response

`status` is `ok` with an evidence package, or `needs_clarification` with the
fields the client must resolve:

```jsonc
{ "status": "needs_clarification",
  "clarifications": [{"field": "company", "reason": "unknown company 'MSFT'"}],
  "calculations": [], "passages": [] }
```

```jsonc
{ "status": "ok",
  "calculations": [{
    "tool": "compare_periods", "cik": 320193, "metric": "revenue", "unit": "USD",
    "year_a": 2023, "year_b": 2024,
    "value_a": 383285000000.0, "value_b": 391035000000.0,
    "source_a": {"period_start": "2022-10-01", "period_end": "2023-09-30",
                  "is_ambiguous": false, "source_fact_id": 1, "manifest_id": 2,
                  "accession": "0000320193-23-000106", "form": "10-K",
                  "filed_date": "2023-11-03"},
    "source_b": {"period_start": "2023-10-01", "period_end": "2024-09-28",
                  "is_ambiguous": false, "accession": "0000320193-24-000123", "…": "…"},
    "change_absolute": 7750000000.0, "change_percent": 0.0202,
    "notes": []   // missing year, zero-base, or ambiguous-input notes
  }],
  "passages": [{ "passage_id": 12, "cik": 320193, "accession": "0000320193-24-000123",
                 "section": "Item 8.", "heading": "Item 8.", "url": "https://…",
                 "text": "…", "similarity": 0.72 }] }
```

When a requested fiscal year matches more than one eligible annual period
(gold's grain is the period, not the year label), the API returns
`needs_clarification` naming the candidate periods instead of guessing; the
comparison carries each side's gold source and flags an ambiguous (restated or
conflicting) input in `notes`.

```sh
curl -s localhost:8000/answer -H 'content-type: application/json' -d '{
  "company": "AAPL", "metric": "revenue", "fiscal_years": [2023, 2024],
  "question": "why did revenue change?"}'
```

- `GET /health` returns `{"status": "ok"}`.
- Metric queries run parameterized SQL templates from `sql/` against
  `gold.annual_metrics`; changes are computed in SQL, and missing periods, a
  zero base, and ambiguous inputs are reported in `notes`.
- Passage evidence comes from `gold.retrieval_passages` using the citation
  metadata carried there (parameterized exact search, restricted to the
  requested company and report years; superseded filings excluded by default).
- Run the API tests with `pytest tests/api`. The live-database regressions in
  `tests/api/test_gold_integration.py` run only when the gold database is
  reachable with the API credentials and otherwise skip.
- When a language model is configured, an `answer` object is added to `ok`
  responses (section 9); otherwise the response is exactly as above.

## 9. Compose cited answers (LLM)

The answer composer sends the evidence package to an OpenAI-compatible chat model and
attaches a cited `answer` to the `POST /answer` response. No SDK is used: the
client is a standard-library `urllib` call to `<LLM_BASE_URL>/chat/completions`,
so the project adds no dependency and works with OpenAI, a compatible gateway, or
a local server (Ollama/LM Studio/vLLM).

Configuration (`.env`):

| Variable | Purpose |
| --- | --- |
| `LLM_MODEL` | Model name; answer composition is enabled only when this is set. |
| `LLM_BASE_URL` | Endpoint base (default `https://api.openai.com/v1`). |
| `LLM_API_KEY` | Bearer token for a hosted provider; omit it for a local server with an explicit base URL. |
| `LLM_INPUT_COST_PER_1K` / `LLM_OUTPUT_COST_PER_1K` | Optional USD per-1K-token prices; cost is logged as `null` when unset. |

Restart the Compose API after configuring these variables (command below).

When configured, each `ok` response gains an `answer` object; the
`calculations`/`passages` are unchanged:

```jsonc
{ "status": "ok",
  "calculations": [ /* … */ ], "passages": [ /* … */ ],
  "answer": {
    "text": "Revenue rose 2.0%, driven by Services.",
    "citations": [
      {"id": "metric:320193:revenue:2023-10-01:2024-09-28", "kind": "metric",
       "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/",
       "accession": "0000320193-24-000123", "section": null,
       "label": "revenue (2023-10-01 to 2024-09-28)"},
      {"id": "passage:12", "kind": "passage", "url": "https://…/aapl-20240928.htm",
       "accession": "0000320193-24-000123", "section": "Item 7.", "label": "Item 7."}
    ],
    "abstained": false, "limitations": null, "model": "gpt-4o-mini",
    "usage": {"prompt_tokens": 1234, "completion_tokens": 88},
    "latency_ms": 812, "cost_usd": null
  } }
```

- Source ids are stable and content-based
  (`metric:<cik>:<metric>:<period_start>:<period_end>` and `passage:<passage_id>`;
  the full period distinguishes two annual periods that share an end date). The
  model cites ids and the API maps each to its own URL/section. Citation ids that
  were not supplied are rejected and noted in `limitations`.
- Passage text is presented as untrusted data, with an instruction to ignore any
  instruction inside it (prompt injection is treated as data). The model's
  internal URL/section fields are ignored; citations come only from the app.
- The model is told to distinguish reported explanations from inference and to
  set `abstained` (with `limitations`) for missing or conflicting evidence.
  `GET /health` reports `answer_composition` true/false.
- Redirects from the completion endpoint are refused, so the API key is never
  sent to another origin.
- Malformed, empty, non-JSON, or refused model replies become an abstained
  `answer` with a limitation — never an error or a false success. A request with
  no evidence abstains without calling the model; a model outage keeps the
  evidence package and marks the answer abstained.
- Usage, latency, and cost are logged as structured fields by the `api.answering`
  logger (configured at app startup so it emits under Uvicorn); credentials and
  prompt/document text are never logged.
- With no model configured (no `LLM_MODEL`), the `answer` field is omitted and
  the endpoint returns exactly the section 8 response shape.
- Run the answer tests with `pytest tests/api`.

The Compose `app` service forwards the LLM settings from `.env`. After editing
them, run `docker compose up -d --no-deps --force-recreate app` (or the Podman
equivalent). `/health` reports `answer_composition: true` when configured;
`POST /answer` then includes the generated reply in `answer.text`.

## 10. Schedule the pipeline (Airflow)

The custom pipeline image is named `localhost/sec-research-assistant_airflow:cpu:cpu`. The Compose
service is still named `airflow`, so the commands below use that service name.

Airflow wraps the manual stages in an Airflow DAG that runs both medallion branches
and publishes gold atomically. Airflow runs as a Compose service built from
`airflow/Dockerfile` uses Apache's slim image, without unrelated provider extras;
the pipeline dependencies from `requirements.txt` and
`dbt-postgres` are installed from the locks in that image. Both manual commands and the DAG use the same dbt-core environment. The repo
is mounted read-only, so dbt writes its `target/` and
`logs/` under `/tmp` inside the container.

Start it:

```sh
docker compose up -d airflow      # or: podman-compose up -d airflow
```

After changing the dependency policy, rebuild with
`docker compose build app airflow` before recreating the containers with
`docker compose up -d`. Installing
or removing packages in an existing container does not shrink its original image.

`airflow-db-init` creates a dedicated `airflow` metadata database in the
existing PostgreSQL (idempotent, so it also covers volumes initialized earlier),
and `airflow` runs `airflow db migrate` then `airflow standalone` (scheduler, DAG
processor, API server, and triggerer). The metadata connection URL is built with
percent-encoded credentials by `airflow/bin/airflow`, which wraps the CLI on
`PATH`, so a database password containing `@`, `:`, `%`, or a space works and the
same wrapper backs `docker compose exec airflow ...`. Once it is up, confirm the
DAG parsed:

```sh
docker compose exec airflow airflow dags list
docker compose exec airflow airflow dags list-import-errors
```

### The DAG

`airflow/dags/sec_research_pipeline.py` runs one linear graph; both branches feed
the same silver and gold builds:

| Task | Step |
| --- | --- |
| `ingest_bronze` | `python -m ingestion --company AAPL --years 3` (skipped when `skip_ingestion=true`) |
| `extract_documents` | `python -m extraction` (bronze filing HTML → bronze blocks) |
| `build_silver` | `dbt build --select silver --indirect-selection cautious` |
| `embed_passages` | `python -m embeddings` |
| `build_gold_candidate` | `dbt build --select gold --vars '{gold_candidate_suffix: __candidate}'` |
| `publish_gold` | atomic swap of the candidates into `gold` (below) |

Retries are configured (`default_args.retries = 2`), and each task's command
output and any failure appear in the Airflow task logs. Tasks exchange only small
summaries (row counts), never documents.

### Atomic publication

The three gold models build under an `__candidate` alias **in the same `gold`
schema**, and their tests run against the candidates. `publish_gold`
(`airflow_pipeline.py`) then swaps each `gold.<name>__candidate` into
`gold.<name>` inside one PostgreSQL transaction (drop the served relation,
rename the candidate into its place, grant SELECT on the served table, count the
rows). Consequences:

- A failed build or test never runs the swap, so the previous gold publication
  stays served by the API.
- A crash or error during the swap — including a count query — rolls the whole
  transaction back and leaves the previous publication in place.
- The API role cannot read candidates: `db/init` grants the API role SELECT on
  every gold table the pipeline creates, so each gold model's post-hook revokes
  that grant on its candidate at creation time, and `publish_gold` grants SELECT
  back on the newly served tables in the same transaction. `gold_api` therefore
  only ever reads published data.
- `embeddings/search.py` and the API keep reading `gold.annual_metrics` /
  `gold.retrieval_passages` unchanged.

Only the DAG publishes atomically; a manual `dbt build` (section 6) writes the
served relations directly.

### Demo scenarios

Run the DAG synchronously to see the task logs, or trigger it normally:

```sh
docker compose exec airflow airflow dags test sec_research_pipeline
docker compose exec airflow airflow dags trigger sec_research_pipeline
```

- **Duplicate rerun:** run it twice. Ingestion is idempotent (no new objects or
  facts) and the rebuilt gold is identical, so a rerun adds and changes nothing.
- **Bronze-only rebuild:** rebuild silver and gold from preserved bronze with no
  SEC downloads:

  ```sh
  docker compose exec airflow airflow dags test sec_research_pipeline \
    -c '{"skip_ingestion": true}'
  ```

- **Recovery from download failures:** an exhausted SEC download is recorded as a
  `failed` `bronze.manifest` row and the `ingest_bronze` task fails after its
  retries; a later run marks the row `resolved` and stores the missing object.
  Inspect with
  `SELECT source, status, error FROM bronze.manifest WHERE status <> 'stored'`.
- **Recovery from validation failures:** if a gold test fails,
  `build_gold_candidate` fails, `publish_gold` does not run, and the API keeps
  serving the previous gold. Fixing the input and rerunning publishes the new
  candidate.

Inspect the published gold (no `__candidate` rows should remain):

```sh
docker compose exec postgres psql -U sec_admin -d sec_research \
  -c "SELECT tablename FROM pg_tables WHERE schemaname='gold' ORDER BY 1"
```

With `.env.example`'s ports, the Airflow UI is at `http://localhost:18080` and
API docs at `http://localhost:18000/docs`. Change `AIRFLOW_PORT` / `API_PORT` in
`.env` to use other host ports. See [run.md](run.md) for the short container-only
startup guide.

## 11. Expand and evaluate

The sample scope is five companies (`ingestion/mappings/companies.json`): AAPL,
MSFT, GOOGL, AMZN, and META. Each is ingested for its three most recent 10-K
years and served end to end. `revenue` maps two XBRL tags (section 6), because
Alphabet switched to `us-gaap:Revenues` in its FY2025 10-K.

From a fresh checkout (stack up and `.env` sourced, as in sections 1–2), run:

```sh
for c in AAPL MSFT GOOGL AMZN META; do
  docker compose exec -T airflow python -m ingestion --company "$c" --years 3
done
docker compose exec -T airflow python -m extraction
docker compose exec -T airflow dbt build --select silver --indirect-selection cautious --project-dir dbt --profiles-dir dbt
docker compose exec -T airflow python -m embeddings
docker compose exec -T airflow dbt build --project-dir dbt --profiles-dir dbt
```

With Podman, substitute `podman-compose exec -T airflow`/`podman-compose`. Reruns are
idempotent. `evaluation/smoke.sh` runs this same sequence and then the
evaluation.

### Evaluate

`evaluation/run.py` runs the 25-question set in `evaluation/questions.json`
through the real `POST /answer` endpoint (use `--base` for the running API), checks
each answer against hand-checked ground truth from published gold, verifies
gold → silver → bronze lineage and that the API role is denied the lower layers,
and writes `evaluation/results.json` and `docs/evaluation-report.md`:

Evaluation runs on the host so it can save `evaluation/results.json`,
`evaluation/citation-review.md`, and `docs/evaluation-report.md`. Install the
shared lock in a host virtual environment first (CPU dependencies above):

```sh
set -a; . ./.env; set +a
PGHOST=127.0.0.1 PGPORT="$POSTGRES_PORT" .venv/bin/python -m evaluation.run \
  --base "http://127.0.0.1:$API_PORT"
```

New answers need fresh manual judgements. Review `evaluation/citation-review.md`,
update `evaluation/citation-judgements.json`, then score the saved results without
another model or database call:

```sh
.venv/bin/python -m evaluation.run --from-results \
  --support-judgements evaluation/citation-judgements.json
```

Use the same command with the committed results to recompute the historical
citation-support score. Do not reuse old judgements for newly generated answers.

Composed-answer metrics (citation support, model latency, cost) and the
prompt-injection case need a language model: set `LLM_MODEL` (plus
`LLM_BASE_URL`/`LLM_API_KEY` for a hosted provider, or an explicit local
`LLM_BASE_URL`) in `.env` first (section 9). Without a model the runner records
those metrics as not measured rather than inventing them.

## pgvector

`db/init/01-init.sh` runs `CREATE EXTENSION vector` during database bootstrap,
so a fresh stack has pgvector ready.

Initialization hooks run only when the data volume is first created. An existing
volume created before this change will not pick it up; enable it once:

```sh
docker compose exec postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS vector;"'
```

`docker compose down -v` deletes the volume and lets the next start initialize it
from scratch.

## Credentials and roles

Created once, when the database volume is first initialized, by
`db/init/01-init.sh`:

All published service ports bind to localhost. The API container has only gold
and optional LLM credentials, a non-root user, and no host checkout mount.
Preparation commands run in Airflow, which has pipeline and storage credentials.
See [SECURITY.md](../SECURITY.md) before adapting this stack for public hosting.

| Role | Source | Access |
| --- | --- | --- |
| `POSTGRES_USER` (default `sec_admin`) | `.env` | Superuser; bootstraps the database. |
| `PIPELINE_DB_USER` (default `pipeline`) | `.env` | Writes `bronze`, `silver`, and `gold` (ingestion and dbt). |
| `GOLD_API_DB_USER` (default `gold_api`) | `.env` | Read-only on `gold` only; no access to `bronze` or `silver`. |

Tables the pipeline creates later in `gold` are automatically readable by the
API role through default privileges, without a further grant.

## MinIO image note

The default images are Chainguard builds:

```text
cgr.dev/chainguard/minio:latest
cgr.dev/chainguard/minio-client:latest
```

To pin a digest or use another registry, set `MINIO_IMAGE` and
`MINIO_CLIENT_IMAGE` in `.env`.

## Tear down

```sh
docker compose down        # stop, keep volumes
docker compose down -v     # stop and delete volumes and all data
```

## Maintain dependencies

`requirements.txt` and `airflow/requirements.txt` declare supported ranges;
`requirements.lock` and `airflow/requirements.lock` record the resolved packages.
Each image has its own complete lock so Airflow's dependency bounds are respected.
Regenerate with uv after intentionally changing a range:

```sh
uv pip compile requirements.txt --python-version 3.12 --python-platform x86_64-unknown-linux-gnu --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match --output-file requirements.lock --no-header
uv pip compile requirements.txt airflow/requirements.txt --python-version 3.12 --python-platform x86_64-unknown-linux-gnu --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match --output-file airflow/requirements.lock --no-header
```

The resolver consults PyPI and the official PyTorch index; installation still
fetches only the pinned CPU wheel from the PyTorch index. Rebuild both images,
run the tests, check a real encoder output, and audit both locks before accepting
an upgrade. The 2026-10-12 evaluation remains historical evidence and should not
be relabelled as a measurement of upgraded dependencies.

The CPU wheel's `+cpu` version suffix is not indexed by PyPI advisories. CI also
queries the upstream PyTorch version without that suffix; this checks published
advisories, not the provenance or operating-system contents of the wheel.
