#!/bin/sh
# Asserts the T001 prerequisites against a running stack: an installed and
# usable pgvector extension, the medallion schemas, the two roles, a read-only
# gold API role, and the configured object-storage bucket.
#
# Usage:
#   COMPOSE="docker compose" ./db/verify.sh     # Docker
#   COMPOSE="podman-compose" ./db/verify.sh     # Podman
#
# Exits non-zero and prints the first failed check.
set -eu

COMPOSE="${COMPOSE:-docker compose}"

echo '== PostgreSQL: pgvector, schemas, roles, and read-only gold grants =='
$COMPOSE exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 -q \
  -v pipeline_user="$PIPELINE_DB_USER" \
  -v gold_api_user="$GOLD_API_DB_USER"' <<'SQL'
-- pgvector must be installed and its vector type usable.
SELECT format('DO $do$ BEGIN RAISE EXCEPTION %L; END $do$;',
              'pgvector extension is not installed')
FROM (SELECT 1) AS one
WHERE NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
\gexec

DO $do$ BEGIN PERFORM '[1,2,3]'::vector; END $do$;

-- Required schemas.
SELECT format('DO $do$ BEGIN RAISE EXCEPTION %L; END $do$;',
              'missing schema: ' || want)
FROM (VALUES ('bronze'), ('silver'), ('gold')) AS s(want)
WHERE NOT EXISTS (
  SELECT 1 FROM information_schema.schemata WHERE schema_name = want
)
\gexec

-- Required roles.
SELECT format('DO $do$ BEGIN RAISE EXCEPTION %L; END $do$;',
              'missing role: ' || want)
FROM (VALUES (:'pipeline_user'), (:'gold_api_user')) AS r(want)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = want)
\gexec

-- Create a pipeline-owned gold table inside a transaction so we can prove the
-- API role reads it but cannot write it. Rolled back; nothing is left behind.
BEGIN;
SET ROLE :"pipeline_user";
CREATE TABLE gold.verify_probe(x int);
RESET ROLE;

SELECT format('DO $do$ BEGIN RAISE EXCEPTION %L; END $do$;', msg)
FROM (VALUES
  (has_schema_privilege(:'pipeline_user', 'bronze', 'CREATE') IS NOT TRUE,
   :'pipeline_user' || ' lacks CREATE on bronze'),
  (has_schema_privilege(:'gold_api_user', 'gold', 'USAGE') IS NOT TRUE,
   :'gold_api_user' || ' lacks USAGE on gold'),
  (has_table_privilege(:'gold_api_user', 'gold.verify_probe', 'SELECT') IS NOT TRUE,
   :'gold_api_user' || ' cannot read a pipeline-created gold table'),
  (has_schema_privilege(:'gold_api_user', 'gold', 'CREATE') IS TRUE,
   :'gold_api_user' || ' can create objects in schema gold'),
  (has_schema_privilege(:'gold_api_user', 'silver', 'USAGE') IS TRUE,
   :'gold_api_user' || ' must not access silver'),
  (has_schema_privilege(:'gold_api_user', 'bronze', 'USAGE') IS TRUE,
   :'gold_api_user' || ' must not access bronze')
) AS checks(failed, msg)
WHERE failed
\gexec

-- No gold relation (the probe just created, or any pre-existing table) may be
-- writable by the API role.
SELECT format('DO $do$ BEGIN RAISE EXCEPTION %L; END $do$;',
              :'gold_api_user' || ' can ' || p.priv || ' gold relation ' || c.relname)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN (VALUES ('INSERT'), ('UPDATE'), ('DELETE'), ('TRUNCATE')) AS p(priv)
WHERE n.nspname = 'gold'
  AND c.relkind IN ('r', 'p', 'f', 'v')
  AND has_table_privilege(:'gold_api_user', c.oid, p.priv)
\gexec

ROLLBACK;

\echo 'PostgreSQL checks passed: pgvector, schemas, roles, and read-only gold grants.'
SQL

# Let Compose resolve .env, overrides and defaults; the Python image needs no packages.
MINIO_BUCKET="$($COMPOSE run -T --rm --no-deps app python -c 'import os; print(os.environ["MINIO_BUCKET"])')"
echo "== MinIO: ${MINIO_BUCKET} bucket =="
$COMPOSE run -T --rm --no-deps minio-init ls "local/${MINIO_BUCKET}" >/dev/null
echo "MinIO checks passed: ${MINIO_BUCKET} bucket reachable."
