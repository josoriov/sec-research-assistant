"""Airflow DAG: bronze -> silver checks -> embeddings -> gold candidate -> publish.

Both medallion branches share this linear graph: ingestion preserves the raw
financial and filing snapshots, extraction turns filing HTML into bronze blocks,
one cautious silver build validates both, embeddings are generated, and the gold
candidate is built and swapped into the served ``gold`` relations only after its
tests pass (``airflow_pipeline.publish_gold``).

Operational notes:
- ``default_args.retries`` retries transient task failures; failures and full
  command output are visible in the Airflow task logs.
- Trigger with ``--conf '{"skip_ingestion": true}'`` to rebuild silver and gold
  from preserved bronze without any SEC downloads (bronze-only rebuild demo).
- Tasks pass only small summaries (row counts) through XCom; document bytes never
  leave the pipeline that produced them.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

# The repo root holds the pipeline packages; make it importable however the DAG
# file is discovered.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Airflow is installed only in the container (H009); host type analysis cannot
# resolve these imports, so the affected lines are ignored here rather than
# excluding the container-only module from analysis entirely.
from airflow import DAG  # pyright: ignore[reportAttributeAccessIssue]
from airflow_pipeline import (
    build_gold_candidate,
    build_silver,
    embed_passages,
    extract_documents,
    ingest_bronze,
    publish_gold,
)

from airflow.providers.standard.operators.python import PythonOperator  # pyright: ignore[reportMissingImports]


def _param(context, name, default):
    """DAG-run conf overrides the declared param, so demos can pass overrides."""
    conf = getattr(context.get("dag_run"), "conf", None) or {}
    params = dict(context.get("params") or {})
    return conf.get(name, params.get(name, default))


def ingest_bronze_task(**context) -> None:
    if _param(context, "skip_ingestion", False):
        print("skip_ingestion=true: rebuilding from existing bronze, no SEC downloads")
        return
    ingest_bronze(_param(context, "company", "AAPL"), int(_param(context, "years", 3)))


def publish_gold_task(**_context) -> dict:
    """No-arg wrapper: keeps Airflow's context keys out of publish_gold's args."""
    summary = publish_gold()
    print(f"published gold row counts: {summary}")
    return summary


with DAG(
    dag_id="sec_research_pipeline",
    description="Ingest SEC filings, validate silver, and publish gold atomically.",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(seconds=30)},
    max_active_runs=1,
    tags=["sec-research", "medallion"],
    params={"company": "AAPL", "years": 3, "skip_ingestion": False},
) as dag:
    ingest = PythonOperator(task_id="ingest_bronze", python_callable=ingest_bronze_task)
    extract = PythonOperator(task_id="extract_documents", python_callable=extract_documents)
    silver = PythonOperator(task_id="build_silver", python_callable=build_silver)
    embed = PythonOperator(task_id="embed_passages", python_callable=embed_passages)
    gold = PythonOperator(task_id="build_gold_candidate", python_callable=build_gold_candidate)
    publish = PythonOperator(task_id="publish_gold", python_callable=publish_gold_task)

    ingest >> extract >> silver >> embed >> gold >> publish  # pyright: ignore[reportUnusedExpression]
