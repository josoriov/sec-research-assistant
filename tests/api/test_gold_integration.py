"""Real-PostgreSQL regressions for the nullable-array crash (F024) and the
multiple-period ambiguity path (F027).

These run against the gold database when it is reachable with the API's
read-only credentials (PGHOST/PGPORT, PGDATABASE or POSTGRES_DB,
GOLD_API_DB_USER/GOLD_API_DB_PASSWORD) and are skipped otherwise, so the default
offline suite is unaffected. They never write to the database.
"""
from __future__ import annotations

import pytest

from api import db
from api.schemas import NeedsClarification
from api.tools.financials import compare_periods, get_metric


def _connect():
    try:
        return db.connect()
    except Exception as exc:  # missing credentials or database unreachable
        pytest.skip(f"no live gold database: {exc}")


def test_get_metric_without_or_with_empty_years_executes():
    # F024: a NULL array parameter used to raise AmbiguousParameter, breaking the
    # advertised "metric with no fiscal-year restriction" request.
    conn = _connect()
    try:
        row = conn.execute("select min(cik), min(metric) from gold.annual_metrics").fetchone()
        if row is None or row[0] is None:
            pytest.skip("gold.annual_metrics is empty")
        cik, metric = int(row[0]), row[1]
        for years in (None, []):
            result = get_metric(conn, cik=cik, metric=metric, fiscal_years=years)
            assert isinstance(result["values"], list)
    finally:
        conn.close()


def test_compare_periods_returns_provenance_on_real_data():
    conn = _connect()
    try:
        row = conn.execute(
            """select cik, metric, unit, fiscal_year from gold.annual_metrics
                group by 1,2,3,4 having count(*) = 1
                order by fiscal_year desc limit 1"""
        ).fetchone()
        if row is None:
            pytest.skip("gold.annual_metrics is empty")
        cik, metric, unit, year = int(row[0]), row[1], row[2], int(row[3])
        result = compare_periods(conn, cik=cik, metric=metric, unit=unit,
                                 year_a=year, year_b=year)
        assert result["source_a"] is not None
        assert result["source_a"]["accession"]
        assert result["source_a"]["period_end"]
    finally:
        conn.close()


def test_compare_periods_clarifies_on_real_multiple_periods():
    # F027: executes only when the live gold actually holds two eligible annual
    # periods under one fiscal-year label (otherwise there is nothing to detect).
    conn = _connect()
    try:
        duplicate = conn.execute(
            """select cik, metric, unit, fiscal_year from gold.annual_metrics
                group by 1,2,3,4 having count(*) > 1 limit 1"""
        ).fetchone()
    finally:
        conn.close()
    if duplicate is None:
        pytest.skip("no fiscal year with multiple annual periods in this database")
    cik, metric, unit, year = int(duplicate[0]), duplicate[1], duplicate[2], int(duplicate[3])
    conn = _connect()
    try:
        with pytest.raises(NeedsClarification):
            compare_periods(conn, cik=cik, metric=metric, unit=unit,
                            year_a=year, year_b=year)
    finally:
        conn.close()
