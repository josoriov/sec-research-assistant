# Run

Requires Docker with Docker Compose, or Podman with `podman-compose`; plus Bash,
curl, internet, and a checkout of this repo.
Run from the repository root, in order, in one terminal. Stop if a command fails.
First startup downloads several GB; no host Python or existing containers needed.

## Configure

Open Bash first; the `$COMPOSE` commands below require its word splitting:

```sh
bash
```

```sh
test -f .env || cp .env.example .env
```

Edit `.env`: set your contact email in `SEC_USER_AGENT` and replace the local
`change-me-*` passwords. Keep an existing configured file. Set `LLM_MODEL`,
`LLM_BASE_URL`, and a real `LLM_API_KEY` for generated answers (local providers
may not need a key). Leave `LLM_MODEL` empty for evidence-only responses.

```sh
chmod 600 .env
```

Compose reads host ports from `.env` automatically. Change them there if busy;
adjust the URLs below to match. Choose your engine below; all later commands
are identical. Both use the `sec-research-assistant` project:

```sh
export COMPOSE="docker compose -p sec-research-assistant"
# For Podman, use this instead:
# export COMPOSE="podman-compose -p sec-research-assistant"
$COMPOSE ps
$COMPOSE config -q
```

## Start

```sh
$COMPOSE build app airflow
$COMPOSE up -d
curl --fail --retry 180 --retry-all-errors --retry-delay 2 http://localhost:18000/health
curl --fail --retry 180 --retry-all-errors --retry-delay 2 http://localhost:18080/api/v2/monitor/health
COMPOSE="$COMPOSE" ./db/verify.sh
```

With an LLM configured, `/health` reports `"answer_composition":true` and
`POST /answer` includes the generated reply in `answer.text` with citations.
After changing LLM settings in `.env`, recreate only the API:

```sh
$COMPOSE up -d --no-deps --force-recreate app airflow
curl --fail --retry 180 --retry-all-errors --retry-delay 2 http://localhost:18000/health
```

## Load data

Load AAPL's latest three annual filings, build/test the tables, and embed passages.
Allow several minutes for the model download. Wait for `state=success`.

You can also trigger runs and set parameters in the Airflow UI.

```sh
$COMPOSE exec -T airflow airflow dags test sec_research_pipeline
```

Supported companies: `AAPL` (Apple), `MSFT` (Microsoft), `GOOGL` (Alphabet),
`AMZN` (Amazon), and `META` (Meta). Run once per company; the default is `AAPL`
for three years.

To choose another company in Airflow, trigger `sec_research_pipeline` with:

```json
{"company": "MSFT", "years": 3}
```

The DAG has no schedule: unpausing it alone does not start a run.


## Inspect

```sh
curl --fail http://localhost:18000/docs -o /dev/null
curl --fail http://localhost:18000/openapi.json -o /dev/null
curl --fail http://localhost:19001 -o /dev/null
curl --fail http://localhost:18000/answer \
  -H 'Content-Type: application/json' \
  -d '{"company":"AAPL","metric":"revenue","fiscal_years":[2024]}'
$COMPOSE ps
$COMPOSE exec -T airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

With the configured ports, open:

- API docs: <http://localhost:18000/docs> (try `POST /answer`).
- Airflow: <http://localhost:18080>. Use the username/password printed by the
  last command; standalone generates them.
- MinIO: <http://localhost:19001> (login with `.env`'s `MINIO_ROOT_USER` and
  `MINIO_ROOT_PASSWORD`).
- PostgreSQL: `localhost:15432`, with the database and credentials from `.env`.

For startup errors:

```sh
$COMPOSE logs --tail=100 app airflow minio-init
```

The API image is separate from the preparation environment. Manual ingestion,
extraction, embedding, and dbt commands run in `airflow`; the API has no pipeline
or storage credentials. Rebuild `app` after changing API code because its source
is copied into the image. See [setup](setup.md) for evaluation and recovery.

## Stop or delete data

Stop containers and keep the stored filings, database, and logs:

```sh
$COMPOSE down
```

Permanently delete the `sec-research-assistant` containers, network, and data volumes. The
checkout, `.env`, and images remain. Repeat Start, Load data, and Inspect to rerun.

```sh
$COMPOSE down -v
$COMPOSE ps
```
