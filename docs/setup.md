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
| `app` | `python:3.12-slim` | Placeholder for the Python application; real source arrives in T002. |

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
