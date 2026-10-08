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
reachable, and exits non-zero on the first failure. Equivalent manual checks:

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

```
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
