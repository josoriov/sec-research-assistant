# Local environment setup

Task T001 stands up the local stack: PostgreSQL with pgvector, MinIO object
storage, and a placeholder for the Python application. This document is the
setup and verification guide for that environment.

The `compose.yaml` at the repository root follows the Compose specification, so
it runs under **Docker Compose** or **Podman Compose**. Every credential is read
from the environment; nothing secret is committed.

## Prerequisites

- Docker with the Compose plugin (`docker compose version`), **or** Podman with
  `podman-compose` (`podman-compose version`).
- Network access to pull container images on first start.

## 1. Configure the environment

```sh
cp .env.example .env
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
| `app` | `python:3.12-slim` | Python pipeline. Installs `requirements.txt` from the repo mount at start, then idles so commands can be run with `docker compose exec` (no Dockerfile yet). |

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
app service's Compose-resolved environment, including quoted `.env` values and
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
docker compose exec app python -m ingestion --company AAPL --years 3
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

The dbt installed here is **dbt Fusion 2.0.6**; its PostgreSQL adapter is
experimental, so the build command enables it. Connection details come from the
same `.env` variables as the rest of the stack (`dbt/profiles.yml`).

```sh
set -a; . ./.env; set +a
export DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true
dbt build --project-dir dbt --profiles-dir dbt
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

- **revenue** → `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`
  (Apple reports this from FY2017; earlier years exist only under legacy tags
  the MVP mapping does not include).
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
these checks pass; publishing gold atomically so a failed build leaves the
previous dataset available is task T007.

Inspect the result and re-run the checks on their own:

```sh
docker compose exec postgres psql -U sec_admin -d sec_research \
  -c 'SELECT metric, fiscal_year, value, accession FROM gold.annual_metrics ORDER BY metric, fiscal_year' \
  -c 'SELECT count(*) FROM silver.financial_facts_quarantine'
dbt test --project-dir dbt --profiles-dir dbt
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
set -a; . ./.env; set +a
export DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true

docker compose exec app python -m extraction
dbt build --select silver --indirect-selection cautious --project-dir dbt --profiles-dir dbt
docker compose exec app python -m embeddings
dbt build --project-dir dbt --profiles-dir dbt
```

The `--indirect-selection cautious` on the silver step keeps cross-layer tests
(which reference not-yet-built gold) out of that build; the final full `dbt build`
runs them once gold exists. With Podman, substitute `podman-compose exec app` and
`podman-compose`, as above.
The `app` image now installs `sentence-transformers` (and its CPU PyTorch
dependency) on first start, so the first `up` takes longer and needs network; the
model weights are downloaded and cached on first embedding run.
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
docker compose exec app python -m embeddings.search \
  "how did revenue change and why?" --cik 320193 --limit 5
# add --include-superseded to search amended/superseded filings too
```

```sh
docker compose exec postgres psql -U sec_admin -d sec_research \
  -c 'SELECT count(*) FROM silver.passages' \
  -c 'SELECT is_superseded, count(*) FROM gold.retrieval_passages GROUP BY 1' \
  -c 'SELECT count(*) FROM silver.passages_quarantine'
```

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

| Role | Source | Access |
| --- | --- | --- |
| `POSTGRES_USER` (default `sec_admin`) | `.env` | Superuser; bootstraps the database. |
| `PIPELINE_DB_USER` (default `pipeline`) | `.env` | Writes `bronze`, `silver`, and `gold` (ingestion and dbt). |
| `GOLD_API_DB_USER` (default `gold_api`) | `.env` | Read-only on `gold` only; no access to `bronze` or `silver`. |

Tables the pipeline creates later in `gold` are automatically readable by the
API role through default privileges, without a further grant.

## MinIO image note

MinIO removed its own public images from Docker Hub and Quay in 2025-2026. The
defaults therefore point at Chainguard's maintained builds:

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
