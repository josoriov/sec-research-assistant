#!/usr/bin/env sh
# Fresh-checkout smoke: ingest the five-company sample, rebuild silver/gold, and
# run the evaluation. Requires the stack up (sections 1-2 of docs/setup.md) and
# .env available in the environment; run `set -a; . ./.env; set +a` first.
# Host Python needs requirements.lock; dbt runs in Airflow.
#
#   PYTHON=.venv/bin/python sh evaluation/smoke.sh
#   COMPOSE=podman-compose PYTHON=.venv/bin/python sh evaluation/smoke.sh
#
# Reruns are idempotent.
set -eu

PYTHON="${PYTHON:-python}"
COMPOSE="${COMPOSE:-docker compose}"
COMPANIES="${COMPANIES:-AAPL MSFT GOOGL AMZN META}"

run_python() {
  $COMPOSE exec -T airflow python "$@"
}

for company in $COMPANIES; do
  echo "== ingest $company"
  run_python -m ingestion --company "$company" --years 3
done

echo "== extract"
run_python -m extraction

echo "== silver"
$COMPOSE exec -T airflow dbt build --select silver --indirect-selection cautious --project-dir dbt --profiles-dir dbt

echo "== embeddings"
run_python -m embeddings

echo "== gold"
$COMPOSE exec -T airflow dbt build --project-dir dbt --profiles-dir dbt

echo "== evaluation"
PGHOST=127.0.0.1 PGPORT="${POSTGRES_PORT:-5432}" \
  "$PYTHON" -m evaluation.run --base "http://127.0.0.1:${API_PORT:-8000}"
