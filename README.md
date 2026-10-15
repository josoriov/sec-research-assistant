# SEC Research Assistant

A portfolio project for researching public companies through financial
calculations and cited evidence from SEC annual filings. The local prototype
covers Apple, Microsoft, Alphabet, Amazon, and Meta, with three recent annual
filings per company and three metrics: revenue, net income, and operating cash
flow.

The implementation combines Python, SQL, Airflow, dbt, PostgreSQL, pgvector,
MinIO, FastAPI, and a local embedding model. An optional language model composes
answers from calculated figures and retrieved passages and interprets
natural-language questions. The backend, question API, evaluation, and Astro web
interface are implemented and verified end to end. See the
[journey checks](evaluation/journey.py).

## Architecture

![SEC Research Assistant architecture: SEC filings and financial facts pass through Python, MinIO, dbt, and PostgreSQL Bronze → Silver → Gold layers. Airflow orchestrates preparation; FastAPI queries published metrics and pgvector passages, then optionally calls an LLM to compose a cited answer.](docs/architecture/sec-research-assistant.svg)

[Interactive architecture diagram](docs/architecture/sec-research-assistant.html)
— download the HTML and open it in a browser to explore source references,
switch between light and dark themes, and export images.
The [diagram specification](docs/architecture/sec-research-assistant.json)
is included for reproducibility.

Data preparation preserves SEC snapshots in bronze, validates facts and passages
in silver, and builds application-ready gold datasets with source lineage.
Airflow runs the preparation steps and publishes validated gold atomically; a
failed candidate build leaves the last successful publication available.

Question answering runs separately. FastAPI validates structured requests,
calculates figures through approved SQL tools, and retrieves filing passages
using local embeddings. Its database role reads only gold. When configured, the
LLM receives the evidence package and returns an answer whose citation IDs are
resolved to application-supplied sources.

Only hosted answer generation requires a provider key. Without a configured
model, the API returns calculations and evidence without making an LLM call.

## Workflows

| Workflow | What it does | Explore |
| --- | --- | --- |
| Data preparation | Archives SEC snapshots, validates financial facts and passages, generates embeddings, and publishes gold with quality checks. | [Run instructions](docs/run.md) · [Setup and recovery](docs/setup.md) |
| Question answering | Returns financial values, period comparisons, retrieved passages, and optional cited explanations with limitations or abstentions. | [API contract](docs/setup.md#8-ask-questions-fastapi) · [Example response](docs/example-response.json) |
| Question UI | An Astro form (company and optional metric selectors, prompt) submits a natural-language question and displays the cited answer with its citations, calculations, passages, limitations, and response metadata. | [Web UI](docs/setup.md#8c-web-ui-astro) |

## Example results

The [recorded evaluation](docs/evaluation-report.md) covers 25 questions over the
five-company dataset on October 12, 2026, using `mimo-v2.6-flash`:

- **Financial calculations:** 17/17 numerical checks passed.
- **Evidence and answers:** the expected filing appeared in retrieved results
  for 6/9 questions; manual review found support for 20/21 cited answers.
  Automated numeric grounding passed for 6/23 generated answers, and appropriate
  abstention or clarification passed for 3/3 unsupported requests.
- **Latency:** mean HTTP latency was 22.1 seconds, with a p95 of 69.3 seconds.

The [saved example response](docs/example-response.json) includes calculations,
passages, resolved citations, usage, and limitations. It explicitly abstains from
explaining a revenue change when the retrieved evidence does not support the
requested cause. Recorded outputs can be inspected without a provider key.

## Run locally

Install Docker Compose or Podman Compose. The first build downloads CPU PyTorch
and the locked dependencies; embedding and retrieval download model weights on
first use. Python 3.12 on Linux x86-64 is the locked and tested environment.
From the repository root:

```sh
test -f .env || cp .env.example .env
chmod 600 .env
```

Edit `.env` to set local passwords and your contact details in `SEC_USER_AGENT`,
then build, start, and load the default AAPL sample:

```sh
docker compose build app web airflow
docker compose up -d
docker compose exec -T airflow airflow dags test sec_research_pipeline
```

The [run guide](docs/run.md) includes readiness checks, Podman commands, loading
other companies, and stopping the stack. With the example ports, the question UI
is at <http://localhost:18001> and interactive API docs at
<http://localhost:18000/docs>. Once the pipeline succeeds:

```sh
curl --fail http://localhost:18000/answer \
  -H 'Content-Type: application/json' \
  -d '{"company":"AAPL","metric":"revenue","fiscal_years":[2024,2025],"question":"why did revenue change?"}'
```

For generated answers, set `LLM_MODEL` and the provider's
`LLM_API_KEY`/`LLM_BASE_URL` as described in [setup](docs/setup.md#9-compose-cited-answers-llm).
Hosted calls send the question and selected evidence to the provider and incur
API usage. The default configuration returns evidence only.

## Validation and scope

The tests cover ingestion recovery, passage extraction, embedding reuse,
financial tools, request validation, citation handling, and atomic publication.
Database integration tests exercise gold permissions and publication failures
against a disposable database; they skip when prerequisites are unavailable.
The [setup guide](docs/setup.md#cpu-python-dependencies) explains installing the
locked host dependencies before running:

```sh
.venv/bin/python -m pytest tests -q
```

CI runs tests, Compose validation, dependency auditing, and Git history secret
scanning. All published ports bind to localhost; the API runs as non-root with a
read-only filesystem and no pipeline or storage credentials.
See [security notes](SECURITY.md) for deployment boundaries and reporting.

This is a local prototype. Evaluation ground truth came from published gold,
not an independent re-extraction of the filings. Retrieval can miss relevant
filings, and valid citation IDs do not prove that a claim is supported. The
prompt-injection check covers one synthetic composition case. Recorded metrics
are historical results, not a benchmark of subsequent dependency upgrades.

The API accepts structured selections or a natural-language prompt for one
company per request, interpreted into a metric and fiscal years. Public hosting
requires authentication, request quotas, and spending controls. Investment
recommendations are outside the project scope.

## License

The original project code and documentation are released under the
[MIT License](LICENSE). SEC source documents, model weights, and third-party
dependencies retain their respective terms.
