"""Search tests: parameterized gold-only SQL, default supersession filter, mapping.

No model or database is loaded (stub encoder and connection).
"""
from embeddings.search import search


class FakeEncoder:
    model_version = "fake-model"
    dim = 2

    def encode(self, texts):
        assert texts == ["how did revenue change?"]
        return [[0.25, -0.5]]


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        return FakeCursor(self.rows)


def _rows():
    return [("[0.0,0.0]", 320193, "0000320193-25-000079", "Item 7.", "Item 7.",
             "https://www.sec.gov/x.htm", "revenue rose", 0.9)]


def test_search_maps_hits_and_excludes_superseded_by_default():
    conn = FakeConn(_rows())
    hits = search("how did revenue change?", encoder=FakeEncoder(), conn=conn)
    assert hits == [{
        "passage_id": "[0.0,0.0]", "cik": 320193,
        "accession": "0000320193-25-000079", "section": "Item 7.",
        "heading": "Item 7.", "url": "https://www.sec.gov/x.htm",
        "text": "revenue rose", "similarity": 0.9,
    }]
    assert conn.sql is not None
    assert conn.params is not None
    assert "gold.retrieval_passages" in conn.sql
    assert "p.is_superseded = false" in conn.sql
    assert "<=>" in conn.sql
    assert "p.text" in conn.sql
    assert "left(" not in conn.sql.lower()
    assert conn.params["query_vector"] == "[0.25,-0.5]"
    assert conn.params["model_version"] == "fake-model"
    assert conn.params["include_superseded"] is False


def test_search_returns_the_full_passage_text():
    long_text = "x" * 600 + " The actual reason was an unexpected factory closure."
    conn = FakeConn([("[0.0,0.0]", 320193, "0000320193-25-000079", "Item 7.",
                     "Item 7.", "https://www.sec.gov/x.htm", long_text, 0.9)])
    hits = search("how did revenue change?", encoder=FakeEncoder(), conn=conn)
    assert hits[0]["text"] == long_text
    assert hits[0]["text"].endswith("unexpected factory closure.")


def test_search_filters_by_company_and_accession():
    conn = FakeConn([])
    search("how did revenue change?", encoder=FakeEncoder(), conn=conn,
           cik=320193, accession="0000320193-25-000079")
    assert conn.sql is not None
    assert conn.params is not None
    assert "p.cik = %(cik)s" in conn.sql
    assert "p.accession = %(accession)s" in conn.sql
    assert conn.params["cik"] == 320193
    assert conn.params["accession"] == "0000320193-25-000079"


def test_search_can_include_superseded():
    conn = FakeConn([])
    search("how did revenue change?", encoder=FakeEncoder(), conn=conn,
           include_superseded=True)
    assert conn.sql is not None
    assert "%(include_superseded)s or p.is_superseded = false" in conn.sql
    assert conn.params["include_superseded"] is True
