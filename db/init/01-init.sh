#!/bin/sh
# Creates the medallion schemas and the two application roles.
#
# Runs once, during first initialization of the postgres data volume, via the
# official image's /docker-entrypoint-initdb.d hook. Credentials are read from
# the environment, so no secrets live in this file.
set -eu

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v dbname="$POSTGRES_DB" \
  -v pipeline_user="$PIPELINE_DB_USER" \
  -v pipeline_password="$PIPELINE_DB_PASSWORD" \
  -v gold_api_user="$GOLD_API_DB_USER" \
  -v gold_api_password="$GOLD_API_DB_PASSWORD" <<'SQL'
-- pgvector: required for embeddings in gold.retrieval_passages (task T004).
CREATE EXTENSION IF NOT EXISTS vector;

-- Schemas.
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- Separate credentials: the pipeline writes bronze/silver/gold; the API role
-- only reads published gold.
CREATE ROLE :"pipeline_user" LOGIN PASSWORD :'pipeline_password';
CREATE ROLE :"gold_api_user" LOGIN PASSWORD :'gold_api_password';

GRANT CONNECT ON DATABASE :"dbname" TO :"pipeline_user", :"gold_api_user";

GRANT USAGE, CREATE ON SCHEMA bronze, silver, gold TO :"pipeline_user";

GRANT USAGE ON SCHEMA gold TO :"gold_api_user";
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO :"gold_api_user";

-- Gold objects created later by the pipeline (e.g. dbt) stay readable by the
-- API role without a further grant.
ALTER DEFAULT PRIVILEGES FOR ROLE :"pipeline_user" IN SCHEMA gold
  GRANT SELECT ON TABLES TO :"gold_api_user";
SQL
