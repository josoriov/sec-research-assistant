"""F036/F039: the API role must not read candidate gold tables.

These tests exercise the **committed** gold models and the production revoke
macro: they run the real candidate build (`airflow_pipeline.build_gold_candidate`,
the same command the DAG uses) and then assert the API credentials are denied on
every ``gold.<name>__candidate`` table. A normal build must pass, and making the
``api_grants.sql`` macro a no-op must make it fail (F039) - so this is a real
regression for the candidate-isolation security fix.

The publisher's re-grant on served tables is checked separately on a throwaway
schema. All tests skip when no live database, no ``dbt`` executable, or no gold
build prerequisites (silver facts/passages/embeddings) are available.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import psycopg
import pytest
from psycopg import sql

import airflow_pipeline
from airflow_pipeline import CANDIDATE_SUFFIX, GOLD_RELATIONS, publish_gold

PROBE_SCHEMA = "gold_publish_test"
INJECTED_FACT_ID = 999999999


def _connect(user_var: str, password_var: str):
    try:
        return psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT") or os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ.get("PGDATABASE") or os.environ["POSTGRES_DB"],
            user=os.environ[user_var],
            password=os.environ[password_var],
        )
    except (KeyError, psycopg.OperationalError) as exc:
        pytest.skip(f"no live database credentials: {exc}")


def _build_prereqs_or_skip(conn) -> None:
    try:
        row = conn.execute(
            """select
                 (select count(*) from silver.financial_fact_disclosures),
                 (select count(*) from silver.passages),
                 (select count(*) from silver.passage_embeddings)"""
        ).fetchone()
    except psycopg.Error as exc:
        pytest.skip(f"gold build prerequisites missing: {exc}")
    conn.rollback()
    if not row or not all(int(value) > 0 for value in row):
        pytest.skip("gold build prerequisites missing (empty silver/embeddings)")


def _dbt_or_skip() -> None:
    for var in ("PIPELINE_DB_USER", "PIPELINE_DB_PASSWORD", "POSTGRES_DB"):
        if not os.environ.get(var):
            pytest.skip(f"{var} is not set")
    if shutil.which(os.environ.get("DBT_EXECUTABLE", "dbt")) is None:
        pytest.skip("dbt executable not available")


def _can_select(conn, schema: str, table: str) -> bool:
    try:
        conn.execute(f'select count(*) from {schema}."{table}"')
        conn.rollback()
        return True
    except psycopg.errors.InsufficientPrivilege:
        conn.rollback()
        return False


def _table_exists(conn, schema: str, table: str) -> bool:
    row = conn.execute(
        "select 1 from pg_catalog.pg_tables where schemaname = %s and tablename = %s",
        (schema, table),
    ).fetchone()
    return row is not None


def _drop_candidates(conn) -> None:
    for relation in GOLD_RELATIONS:
        conn.execute(f'drop table if exists gold."{relation}{CANDIDATE_SUFFIX}"')
    conn.commit()


def _assert_candidates_denied(pipeline, api) -> None:
    for relation in GOLD_RELATIONS:
        assert _table_exists(pipeline, "gold", f"{relation}{CANDIDATE_SUFFIX}"), relation
    for relation in GOLD_RELATIONS:
        assert _can_select(api, "gold", f"{relation}{CANDIDATE_SUFFIX}") is False, relation


def test_committed_candidate_build_is_denied_to_api_role():
    # F039: runs the real models + macro; a no-op macro makes this fail.
    _dbt_or_skip()
    pipeline = _connect("PIPELINE_DB_USER", "PIPELINE_DB_PASSWORD")
    _build_prereqs_or_skip(pipeline)
    api = _connect("GOLD_API_DB_USER", "GOLD_API_DB_PASSWORD")
    try:
        airflow_pipeline.build_gold_candidate()
        _assert_candidates_denied(pipeline, api)
    finally:
        _drop_candidates(pipeline)
        pipeline.close()
        api.close()


def test_candidates_denied_after_failed_validation():
    _dbt_or_skip()
    pipeline = _connect("PIPELINE_DB_USER", "PIPELINE_DB_PASSWORD")
    _build_prereqs_or_skip(pipeline)
    api = _connect("GOLD_API_DB_USER", "GOLD_API_DB_PASSWORD")
    try:
        inserted = pipeline.execute(
            """insert into silver.financial_fact_disclosures
                 (source_fact_id, manifest_id, cik, concept, taxonomy, tag, unit,
                  period_start, period_end, value, fiscal_year, fiscal_period, form,
                  accession, filed_date, frame)
               select %s, manifest_id, cik, concept, taxonomy, tag, unit,
                      period_start, period_end, value, fiscal_year, fiscal_period, form,
                      null, date '2099-01-01', frame
                 from silver.financial_fact_disclosures
                where tag = 'NetIncomeLoss' and fiscal_period = 'FY'
                order by period_end desc limit 1""",
            (INJECTED_FACT_ID,),
        ).rowcount
        pipeline.commit()
        if inserted == 0:
            pytest.skip("no eligible NetIncomeLoss FY disclosure to duplicate")
        with pytest.raises(subprocess.CalledProcessError):
            airflow_pipeline.build_gold_candidate()
        _assert_candidates_denied(pipeline, api)
    finally:
        pipeline.execute(
            "delete from silver.financial_fact_disclosures where source_fact_id = %s",
            (INJECTED_FACT_ID,),
        )
        pipeline.commit()
        _drop_candidates(pipeline)
        pipeline.close()
        api.close()


def test_publisher_grants_select_on_served_tables():
    admin = _connect("POSTGRES_USER", "POSTGRES_PASSWORD")
    api = _connect("GOLD_API_DB_USER", "GOLD_API_DB_PASSWORD")
    role = os.environ["GOLD_API_DB_USER"]
    relations = ("t1",)
    try:
        admin.execute(f"drop schema if exists {PROBE_SCHEMA} cascade")
        admin.execute(f"create schema {PROBE_SCHEMA}")
        admin.execute(sql.SQL("grant usage on schema {} to {}").format(
            sql.Identifier(PROBE_SCHEMA), sql.Identifier(role)))
        for relation in relations:
            admin.execute(f'create table {PROBE_SCHEMA}."{relation}"(v int)')
            admin.execute(f'insert into {PROBE_SCHEMA}."{relation}" values (1)')
            admin.execute(f'create table {PROBE_SCHEMA}."{relation}__candidate"(v int)')
            admin.execute(f'insert into {PROBE_SCHEMA}."{relation}__candidate" values (2)')
        admin.commit()
        # No default grant applies to an admin-owned throwaway schema, so the
        # publisher's explicit grant is what makes the served table readable.
        assert _can_select(api, PROBE_SCHEMA, "t1") is False
        publish_gold(admin, schema=PROBE_SCHEMA, relations=relations, api_role=role)
        assert _can_select(api, PROBE_SCHEMA, "t1") is True
        assert not _table_exists(admin, PROBE_SCHEMA, "t1__candidate")
    finally:
        admin.execute(f"drop schema if exists {PROBE_SCHEMA} cascade")
        admin.commit()
        admin.close()
        api.close()
