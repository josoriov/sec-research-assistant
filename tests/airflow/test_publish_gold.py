"""Atomic gold publication regression.

Exercises ``airflow_pipeline.publish_gold`` against a live PostgreSQL using a
throwaway schema, so the swap/guard logic is verified without touching the real
``gold`` relations. Skips when no administrative database connection is
available, mirroring ``tests/api/test_gold_integration.py``.
"""
from __future__ import annotations

import os

import psycopg
import pytest

import airflow_pipeline
from airflow_pipeline import CANDIDATE_SUFFIX, publish_gold

SCHEMA = "gold_publish_test"
RELATIONS = ("t1", "t2")


def _admin_connect():
    try:
        return psycopg.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT") or os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ.get("PGDATABASE") or os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        )
    except (KeyError, psycopg.OperationalError) as exc:
        pytest.skip(f"no live database: {exc}")


def _relation_exists(conn, relation: str) -> bool:
    row = conn.execute(
        "select 1 from pg_catalog.pg_tables where schemaname = %s and tablename = %s",
        (SCHEMA, relation),
    ).fetchone()
    return row is not None


def _seed(conn, *, with_candidates=True) -> None:
    conn.execute(f"create schema if not exists {SCHEMA}")
    conn.execute(f"drop schema if exists {SCHEMA} cascade")
    conn.execute(f"create schema {SCHEMA}")
    for relation in RELATIONS:
        conn.execute(f'create table {SCHEMA}."{relation}"(v text)')
        conn.execute(f'insert into {SCHEMA}."{relation}" values (\'published\')')
        if with_candidates:
            candidate = f"{relation}{CANDIDATE_SUFFIX}"
            conn.execute(f'create table {SCHEMA}."{candidate}"(v text)')
            conn.execute(f'insert into {SCHEMA}."{candidate}" values (\'candidate\')')
    conn.commit()


def _values(conn, relation: str) -> list[str]:
    return [row[0] for row in conn.execute(f'select v from {SCHEMA}."{relation}"').fetchall()]


def test_publish_gold_swaps_candidates_into_place():
    conn = _admin_connect()
    try:
        _seed(conn)
        summary = publish_gold(conn, schema=SCHEMA, relations=RELATIONS)
        assert summary == {relation: 1 for relation in RELATIONS}
        for relation in RELATIONS:
            assert _values(conn, relation) == ["candidate"]
            assert not _relation_exists(conn, f"{relation}{CANDIDATE_SUFFIX}")
    finally:
        conn.execute(f"drop schema if exists {SCHEMA} cascade")
        conn.commit()
        conn.close()


def test_publish_gold_missing_candidate_leaves_published_intact():
    conn = _admin_connect()
    try:
        # t2 has no candidate, so the whole publish must abort without swapping.
        _seed(conn, with_candidates=False)
        conn.execute(f'create table {SCHEMA}."t1{CANDIDATE_SUFFIX}"(v text)')
        conn.execute(f'insert into {SCHEMA}."t1{CANDIDATE_SUFFIX}" values (\'candidate\')')
        conn.commit()
        with pytest.raises(RuntimeError):
            publish_gold(conn, schema=SCHEMA, relations=RELATIONS)
        for relation in RELATIONS:
            assert _values(conn, relation) == ["published"]
    finally:
        conn.execute(f"drop schema if exists {SCHEMA} cascade")
        conn.commit()
        conn.close()


def test_publish_gold_count_failure_rolls_back(monkeypatch):
    # F038: the summary counts run inside the swap transaction, so a count error
    # rolls the swap back and leaves served tables and candidates intact.
    conn = _admin_connect()
    try:
        _seed(conn)

        def boom(*args, **kwargs):
            raise psycopg.OperationalError("synthetic count failure")

        original = airflow_pipeline._count
        monkeypatch.setattr(airflow_pipeline, "_count", boom)
        try:
            with pytest.raises(psycopg.OperationalError):
                publish_gold(conn, schema=SCHEMA, relations=RELATIONS)
        finally:
            monkeypatch.setattr(airflow_pipeline, "_count", original)
        for relation in RELATIONS:
            assert _values(conn, relation) == ["published"]
            assert _relation_exists(conn, f"{relation}{CANDIDATE_SUFFIX}")
        # An unpatched retry succeeds.
        assert publish_gold(conn, schema=SCHEMA, relations=RELATIONS) == {
            relation: 1 for relation in RELATIONS
        }
    finally:
        conn.execute(f"drop schema if exists {SCHEMA} cascade")
        conn.commit()
        conn.close()
