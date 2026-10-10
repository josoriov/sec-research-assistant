"""Financial tool tests: parameterized SQL, SQL-side change, zero/missing/ambiguous.

A stub connection captures the SQL and parameters; no database is touched. One
live-DB regression for the nullable-array crash lives in test_gold_integration.py.
"""
from pathlib import Path

import pytest

from api.schemas import NeedsClarification
from api.tools.financials import compare_periods, get_metric

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


class Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class RecordingConn:
    def __init__(self, *results):
        self._results = list(results)
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params
        return Cursor(self._results.pop(0))


def _metric_row(value, fiscal_year=2024, is_ambiguous=False):
    return (320193, "revenue", "USD", "2023-10-01", "2024-09-28", fiscal_year,
            value, is_ambiguous, 1, 2, "0000320193-24-000123", "10-K", "2024-11-01")


def _compare_row(value_a=100.0, value_b=150.0, *, amb_a=False, amb_b=False,
                 count_a=1, count_b=1, periods_a=None, periods_b=None):
    if value_a in (None, 0) or value_b is None:
        change_percent = None
    else:
        change_percent = (value_b - value_a) / value_a
    change_absolute = None if value_a is None or value_b is None else value_b - value_a
    return (count_a, periods_a, count_b, periods_b,
            value_a, "2022-10-01", "2023-09-30", amb_a, 1, 2, "acc-2023", "10-K", "2023-11-01",
            value_b, "2023-10-01", "2024-09-28", amb_b, 3, 4, "acc-2024", "10-K", "2024-11-01",
            change_absolute, change_percent)


def test_get_metric_sql_lets_postgres_infer_the_nullable_array():
    # F024: without the ::integer[] cast, a NULL array parameter is ambiguous
    # and PostgreSQL raises AmbiguousParameter even for a successful request.
    text = (SQL_DIR / "get_metric.sql").read_text()
    assert "%(fiscal_years)s::integer[] is null" in text
    assert "any(%(fiscal_years)s::integer[])" in text


def test_get_metric_binds_values_and_never_interpolates_them():
    conn = RecordingConn([_metric_row(391035000000)])
    result = get_metric(conn, cik=320193, metric="revenue", fiscal_years=[2024])
    assert result["values"][0]["value"] == 391035000000.0
    assert result["values"][0]["period_end"] == "2024-09-28"
    assert result["notes"] == []
    assert "gold.annual_metrics" in conn.sql
    assert "%(cik)s" in conn.sql and "%(fiscal_years)s" in conn.sql
    assert "320193" not in conn.sql
    assert conn.params == {"cik": 320193, "metric": "revenue", "unit": "USD",
                           "fiscal_years": [2024]}


def test_get_metric_reports_missing_requested_years_and_ambiguity():
    conn = RecordingConn([_metric_row(391035000000, fiscal_year=2024, is_ambiguous=True)])
    result = get_metric(conn, cik=320193, metric="revenue", fiscal_years=[2020, 2024])
    assert result["notes"][0] == "no annual value for fiscal_year=2020"
    assert any("ambiguous" in note for note in result["notes"])
    assert conn.params["fiscal_years"] == [2020, 2024]


def test_compare_periods_uses_sql_change_and_carries_provenance():
    conn = RecordingConn([_compare_row(100_000.0, 150_000.0)])
    result = compare_periods(conn, cik=320193, metric="revenue",
                             year_a=2023, year_b=2024)
    assert result["change_absolute"] == 50_000.0
    assert result["change_percent"] == 0.5
    assert result["notes"] == []
    # F025: each side links to its selected gold source and period.
    assert result["source_a"]["accession"] == "acc-2023"
    assert result["source_b"]["accession"] == "acc-2024"
    assert result["source_a"]["period_end"] == "2023-09-30"
    assert "gold.annual_metrics" in conn.sql
    assert "320193" not in conn.sql and "2023" not in conn.sql
    assert conn.params == {"cik": 320193, "metric": "revenue", "unit": "USD",
                           "year_a": 2023, "year_b": 2024}


def test_compare_periods_surfaces_ambiguous_inputs():
    conn = RecordingConn([_compare_row(amb_a=True)])
    result = compare_periods(conn, cik=320193, metric="revenue",
                             year_a=2023, year_b=2024)
    assert result["source_a"]["is_ambiguous"] is True
    assert any("ambiguous" in note for note in result["notes"])


def test_compare_periods_handles_zero_base_and_missing_years():
    zero_base = compare_periods(RecordingConn([_compare_row(0.0, 150.0)]),
                                cik=1, metric="revenue", year_a=2023, year_b=2024)
    assert zero_base["change_percent"] is None
    assert "zero" in zero_base["notes"][0]

    missing = compare_periods(
        RecordingConn([_compare_row(value_a=None, count_a=0)]),
        cik=1, metric="revenue", year_a=2023, year_b=2024)
    assert missing["value_a"] is None and missing["source_a"] is None
    assert any("2023" in note for note in missing["notes"])

    both_missing = compare_periods(
        RecordingConn([_compare_row(value_a=None, value_b=None, count_a=0, count_b=0)]),
        cik=1, metric="revenue", year_a=2023, year_b=2024)
    assert len(both_missing["notes"]) == 2


def test_compare_periods_clarifies_when_a_year_has_multiple_periods():
    # F027: gold's grain is the period, not the fiscal-year label; two distinct
    # annual periods can share a year and must not be reduced to a guessed result.
    conn = RecordingConn([_compare_row(
        count_a=2, periods_a="2022-09-30 to 2023-09-30, 2022-10-01 to 2023-09-30")])
    with pytest.raises(NeedsClarification) as excinfo:
        compare_periods(conn, cik=320193, metric="revenue", year_a=2023, year_b=2024)
    assert excinfo.value.field == "fiscal_years"
    assert "2023" in excinfo.value.reason
    assert "2022-10-01 to 2023-09-30" in excinfo.value.reason
