#!/usr/bin/env sh
# Fresh-checkout smoke: ingest the five-company sample, rebuild silver/gold, and
# run the evaluation. Requires the stack up (sections 1-2 of docs/setup.md) and
# .env available in the environment; run `set -a; . ./.env; set +a` first.
#
#   PYTHON=/path/to/venv/bin/python sh evaluation/smoke.sh        # host python + dbt
#   COMPOSE=podman-compose sh evaluation/smoke.sh                 # app container for python
#
# Reruns are idempotent.
set -eu

PYTHON="${PYTHON:-python}"
COMPOSE="${COMPOSE:-}"
export DBT_ALLOW_EXPERIMENTAL_ADAPTERS="${DBT_ALLOW_EXPERIMENTAL_ADAPTERS:-true}"
COMPANIES="${COMPANIES:-AAPL MSFT GOOGL AMZN META}"

run_python() {
  if [ -n "$COMPOSE" ]; then
    $COMPOSE exec -T app python "$@"
  else
    "$PYTHON" "$@"
  fi
}

for company in $COMPANIES; do
  echo "== ingest $company"
  run_python -m ingestion --company "$company" --years 3
done

echo "== extract"
run_python -m extraction

echo "== silver"
dbt build --select silver --indirect-selection cautious --project-dir dbt --profiles-dir dbt

echo "== embeddings"
run_python -m embeddings

echo "== gold"
dbt build --project-dir dbt --profiles-dir dbt

echo "== evaluation"
run_python -m evaluation.run
