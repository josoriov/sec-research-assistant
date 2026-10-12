"""Pipeline steps and the atomic gold publisher used by the Airflow DAG (T007).

This module deliberately has no Airflow import: the DAG imports it, and the
steps/publish logic can be exercised by `tests/airflow` without an Airflow
install. The heavy steps run the same CLIs documented in `docs/setup.md` as
subprocesses, so Airflow task logs show exactly what the manual pipeline runs.

Atomic publication
------------------
dbt builds the three gold models under an ``__candidate`` alias (the
``gold_candidate_suffix`` var in ``dbt/models/gold/*.sql``). ``publish_gold``
then swaps the candidates into the served names inside a single PostgreSQL
transaction: a failed build or test never runs the swap, and a crash inside the
swap rolls back, so the API always sees the last good publication. RENAME keeps
each relation's object identity, so the ``gold_api`` SELECT grant (and the
pipeline's default privileges) follow the candidate into the published name.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parent
DBT_DIR = REPO_ROOT / "dbt"

CANDIDATE_SUFFIX = "__candidate"
GOLD_SCHEMA = "gold"
# Kept in one tuple so a new gold model only needs registering here.
GOLD_RELATIONS = ("metric_concepts", "annual_metrics", "retrieval_passages")


def metadata_url(env=None) -> str:
    """Airflow metadata SQLAlchemy URL with percent-encoded credentials (F037).

    Compose cannot paste a raw password into a URL: characters such as ``@``
    break parsing, so a valid PostgreSQL password can stop Airflow from starting.
    """
    env = os.environ if env is None else env
    user = quote(env["POSTGRES_USER"], safe="")
    password = quote(env["POSTGRES_PASSWORD"], safe="")
    host = env.get("AIRFLOW_DB_HOST", "postgres")
    port = env.get("AIRFLOW_DB_PORT", "5432")
    name = env.get("AIRFLOW_DB_NAME", "airflow")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def _run(cmd: list[str]) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    env = dict(os.environ)
    # Harmless for dbt-core, required by the host dbt Fusion adapter.
    env.setdefault("DBT_ALLOW_EXPERIMENTAL_ADAPTERS", "true")
    subprocess.run(cmd, check=True, env=env)


def _dbt(*args: str) -> None:
    _run([
        os.environ.get("DBT_EXECUTABLE", "dbt"), *args,
        "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR),
    ])


def ingest_bronze(company: str = "AAPL", years: int = 3) -> None:
    """Fetch bronze snapshots for one company (no-op target when skipped)."""
    _run([sys.executable, "-m", "ingestion", "--company", company, "--years", str(years)])


def extract_documents(processing_version: str | None = None) -> None:
    cmd = [sys.executable, "-m", "extraction"]
    if processing_version:
        cmd += ["--processing-version", processing_version]
    _run(cmd)


def build_silver() -> None:
    """Validate bronze into silver; cautious selection avoids unbuilt gold tests."""
    _dbt("build", "--select", "silver", "--indirect-selection", "cautious")


def embed_passages() -> None:
    _run([sys.executable, "-m", "embeddings"])


def build_gold_candidate() -> None:
    """Build and test the gold models under the candidate alias (not served)."""
    _dbt("build", "--select", "gold", "--vars",
         f"{{gold_candidate_suffix: {CANDIDATE_SUFFIX}}}")


def _table_names(conn, schema: str) -> set[str]:
    rows = conn.execute(
        "select tablename from pg_catalog.pg_tables where schemaname = %s", (schema,)
    ).fetchall()
    return {row[0] for row in rows}


def publish_gold(connection=None, *, schema: str = GOLD_SCHEMA,
                 relations=GOLD_RELATIONS, api_role: str | None = None) -> dict:
    """Atomically swap ``<rel>__candidate`` into ``<rel>`` for every gold relation.

    Returns a small summary (counts) suitable for an XCom; raises without
    touching the served relations if any candidate is missing.

    The swap, the SELECT grant on the newly served tables, and the row counts all
    happen in one transaction, so a failure anywhere (including the counts) rolls
    everything back and leaves the previous publication in place.

    ``connection`` (not ``conn``) is the parameter name on purpose: Airflow's task
    context has a ``conn`` key and would otherwise inject it into this callable.
    """
    from ingestion.db import connect  # pipeline credentials, local import

    if api_role is None:
        api_role = os.environ.get("GOLD_API_DB_USER", "gold_api")
    owns_connection = connection is None
    conn = connection or connect()
    try:
        with conn.transaction():
            existing = _table_names(conn, schema)
            missing = [r for r in relations if f"{r}{CANDIDATE_SUFFIX}" not in existing]
            if missing:
                raise RuntimeError(
                    f"cannot publish: missing candidate tables in {schema}: "
                    + ", ".join(f"{r}{CANDIDATE_SUFFIX}" for r in missing)
                )
            summary = {}
            for relation in relations:
                candidate = f"{relation}{CANDIDATE_SUFFIX}"
                conn.execute(f'drop table if exists {schema}."{relation}"')
                conn.execute(f'alter table {schema}."{candidate}" rename to "{relation}"')
                # Candidates are revoked from the API role (see api_grants.sql);
                # grant SELECT back on the table that is now served.
                if api_role:
                    conn.execute(f'grant select on {schema}."{relation}" to "{api_role}"')
                summary[relation] = _count(conn, schema, relation)
        return summary
    finally:
        if owns_connection:
            conn.close()


def _count(conn, schema: str, relation: str) -> int:
    return conn.execute(f'select count(*) from {schema}."{relation}"').fetchone()[0]


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m airflow_pipeline")
    sub = parser.add_subparsers(dest="step", required=True)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--company", default="AAPL")
    ingest.add_argument("--years", type=int, default=3)
    sub.add_parser("extract")
    sub.add_parser("silver")
    sub.add_parser("embed")
    sub.add_parser("gold")
    sub.add_parser("publish")
    sub.add_parser("metadata-url")
    args = parser.parse_args()
    if args.step == "ingest":
        ingest_bronze(args.company, args.years)
    elif args.step == "extract":
        extract_documents()
    elif args.step == "silver":
        build_silver()
    elif args.step == "embed":
        embed_passages()
    elif args.step == "gold":
        build_gold_candidate()
    elif args.step == "publish":
        print(publish_gold())
    elif args.step == "metadata-url":
        print(metadata_url())


if __name__ == "__main__":
    main()
