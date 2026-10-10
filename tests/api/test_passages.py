"""Passage tool: gold-only parameterized search with period/company filters."""
from pathlib import Path

from api.tools.passages import search_passages

SQL = (Path(__file__).resolve().parents[2] / "sql" / "search_passages.sql").read_text()


class StubEncoder:
    model_version = "stub-model"
    dim = 2

    def encode(self, texts):
        assert texts == ["how did revenue change?"]
        return [[0.25, 0.5]]


class Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class RecordingConn:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        return Cursor(self.rows)


def _rows():
    return [("12", 320193, "0000320193-24-000123", "Item 7.", "Item 7.",
             "https://www.sec.gov/x.htm", "revenue rose", 0.87)]


def test_search_passages_returns_carried_citation_metadata_and_binds_filters():
    conn = RecordingConn(_rows())
    hits = search_passages("how did revenue change?", conn=conn, cik=320193,
                           fiscal_years=[2023, 2024], limit=3, encoder=StubEncoder())
    assert hits == [{
        "passage_id": "12", "cik": 320193, "accession": "0000320193-24-000123",
        "section": "Item 7.", "heading": "Item 7.", "url": "https://www.sec.gov/x.htm",
        "text": "revenue rose", "similarity": 0.87,
    }]
    assert "gold.retrieval_passages" in conn.sql
    assert "silver." not in conn.sql and "bronze." not in conn.sql
    assert "p.is_superseded = false" in conn.sql
    # F026: fiscal years restrict the query against gold report_date metadata.
    assert "extract(year from p.report_date)" in conn.sql
    assert conn.params["fiscal_years"] == [2023, 2024]
    assert conn.params["cik"] == 320193
    assert conn.params["limit"] == 3


def test_search_passages_leaves_periods_unrestricted_when_omitted():
    conn = RecordingConn([])
    search_passages("how did revenue change?", conn=conn, encoder=StubEncoder())
    assert conn.params["fiscal_years"] is None
    assert conn.params["cik"] is None
    assert search_passages("how did revenue change?", conn=RecordingConn([]),
                           encoder=StubEncoder(), include_superseded=True) == []


def test_search_passages_sql_is_parameterized():
    assert "gold.retrieval_passages" in SQL
    # Only named placeholders; no interpolation of filter values.
    assert "%(query_vector)s" in SQL and "%(fiscal_years)s" in SQL
    assert "%(cik)s::integer" in SQL
