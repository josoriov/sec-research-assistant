"""Focused tests for bronze ingestion (no network, database, or MinIO needed)."""
import json
import urllib.error
from email.message import Message

import pytest
from minio.error import S3Error
from urllib3.response import HTTPResponse

from ingestion import db, pipeline
from ingestion.pipeline import (
    _download,
    _original_years,
    filing_records,
    load_mapping,
    select_10ks,
)
from ingestion.sec_client import SecClient
from ingestion.storage import BronzeStore, object_key


class _Response:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeMinio:
    def __init__(self):
        self.buckets = set()
        self.objects = {}

    def bucket_exists(self, bucket):
        return bucket in self.buckets

    def make_bucket(self, bucket):
        self.buckets.add(bucket)

    def stat_object(self, bucket, key):
        if (bucket, key) not in self.objects:
            raise S3Error(HTTPResponse(status=404), "NoSuchKey", "missing", key, "req", "host")

    def put_object(self, bucket, key, data, length, content_type):
        self.objects[(bucket, key)] = data.read()


class FakeCursor:
    def __init__(self):
        self.rows = []

    def executemany(self, sql, rows):
        self.rows.extend(rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


# --- mapping and object keys -------------------------------------------------

def test_mapping_resolves_apple():
    assert int(load_mapping()["AAPL"]["cik"]) == 320193


def test_object_key_is_company_source_hash():
    assert object_key(320193, "filing", "abc123", ".htm") == "320193/filing/abc123.htm"


def test_store_never_overwrites_existing_object():
    store = BronzeStore(FakeMinio(), "bronze")
    store.ensure_bucket()
    assert store.put_if_absent("320193/filing/x.html", b"original", "text/html") is True
    assert store.put_if_absent("320193/filing/x.html", b"changed", "text/html") is False
    assert store.client.objects[("bronze", "320193/filing/x.html")] == b"original"


# --- SEC client --------------------------------------------------------------

def test_client_requires_identifying_user_agent():
    with pytest.raises(ValueError):
        SecClient("")
    with pytest.raises(ValueError):
        SecClient("no-contact-here")


def test_client_rejects_negative_retries_without_a_request():
    def opener(request, timeout=None):
        pytest.fail("negative retries must not make a request")

    client = SecClient("bot you@example.com", min_interval=0, opener=opener)
    with pytest.raises(ValueError, match="retries must be non-negative"):
        client.get("https://example.test/f", retries=-1)


def test_client_retries_temporary_http_errors(monkeypatch):
    calls = []

    def opener(request, timeout=None):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 503, "busy", Message(), None)
        return _Response(b"ok")

    monkeypatch.setattr("ingestion.sec_client.time.sleep", lambda seconds: None)
    client = SecClient("bot you@example.com", min_interval=0, opener=opener)
    assert client.get("https://example.test/f") == b"ok"
    assert len(calls) == 2


def test_client_retries_body_read_timeout(monkeypatch):
    class FlakyResponse:
        def __init__(self):
            self.reads = 0

        def read(self):
            self.reads += 1
            if self.reads == 1:
                raise TimeoutError("body download timed out")
            return b"ok"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    calls = []
    response = FlakyResponse()

    def opener(request, timeout=None):
        calls.append(request.full_url)
        return response

    monkeypatch.setattr("ingestion.sec_client.time.sleep", lambda seconds: None)
    client = SecClient("bot you@example.com", min_interval=0, opener=opener)
    assert client.get("https://example.test/big") == b"ok"
    assert len(calls) == 2


def test_client_body_timeout_exhausts_exact_attempts(monkeypatch):
    class AlwaysTimingOut:
        def read(self):
            raise TimeoutError("body download timed out")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    calls = []

    def opener(request, timeout=None):
        calls.append(request.full_url)
        return AlwaysTimingOut()

    monkeypatch.setattr("ingestion.sec_client.time.sleep", lambda seconds: None)
    client = SecClient("bot you@example.com", min_interval=0, opener=opener)
    with pytest.raises(TimeoutError):
        client.get("https://example.test/big", retries=3)
    assert len(calls) == 4


def test_client_throttles_requests(monkeypatch):
    slept = []
    monkeypatch.setattr("ingestion.sec_client.time.sleep", slept.append)
    client = SecClient("bot you@example.com", min_interval=0.5,
                       opener=lambda request, timeout=None: _Response(b"x"))
    client.get("https://example.test/a")
    client.get("https://example.test/b")
    assert slept and slept[0] > 0


# --- filing selection and history coverage ----------------------------------

@pytest.mark.parametrize("years", [0, -1])
def test_run_rejects_nonpositive_years_before_fetching(monkeypatch, years):
    def unexpected_mapping():
        pytest.fail("invalid years must fail before loading configuration or fetching")

    monkeypatch.setattr(pipeline, "load_mapping", unexpected_mapping)
    with pytest.raises(SystemExit, match="years must be positive"):
        pipeline.run("AAPL", years=years)


def test_select_10ks_keeps_original_reports_and_amendments():
    records = [
        {"form": "10-K", "reportDate": "2022-09-24", "filingDate": "2022-10-28",
         "accessionNumber": "a22"},
        {"form": "10-K/A", "reportDate": "2022-09-24", "filingDate": "2023-01-01",
         "accessionNumber": "a22a"},
        {"form": "10-K/A", "reportDate": "2022-09-24", "filingDate": "2023-03-01",
         "accessionNumber": "a22b"},
        {"form": "10-K", "reportDate": "2023-09-30", "filingDate": "2023-11-03",
         "accessionNumber": "a23"},
        {"form": "10-K", "reportDate": "2024-09-28", "filingDate": "2024-11-01",
         "accessionNumber": "a24"},
        {"form": "10-Q", "reportDate": "2024-06-29", "filingDate": "2024-08-02",
         "accessionNumber": "q"},
    ]
    selected = select_10ks(records, years=3)
    assert [r["accessionNumber"] for r in selected] == ["a24", "a23", "a22", "a22a", "a22b"]
    assert len(_original_years(selected)) == 3


def test_filing_records_follows_older_history_until_covered(monkeypatch):
    submissions = {
        "filings": {
            "recent": {
                "accessionNumber": ["r2025"],
                "form": ["10-K"],
                "reportDate": ["2025-09-27"],
                "filingDate": ["2025-11-01"],
                "primaryDocument": ["r2025.htm"],
            },
            "files": [
                {"name": "old-001.json", "filingTo": "2015-09-15"},
                {"name": "old-002.json", "filingTo": "2005-09-15"},
            ],
        }
    }
    older = {
        "accessionNumber": ["r2024", "r2023"],
        "form": ["10-K", "10-K"],
        "reportDate": ["2024-09-28", "2023-09-30"],
        "filingDate": ["2024-11-01", "2023-11-03"],
        "primaryDocument": ["r2024.htm", "r2023.htm"],
    }
    requested = []

    def fake_download(client, store, conn, *, cik, source, accession, url):
        requested.append(url)
        return json.dumps(older).encode(), 1

    monkeypatch.setattr(pipeline, "_download", fake_download)
    records = filing_records(None, None, None, 320193, submissions, years=3)

    assert len(_original_years(records)) == 3
    assert len(requested) == 1  # stops as soon as coverage is reached
    assert requested[0].endswith("old-001.json")


# --- download failure recording ---------------------------------------------

def test_download_records_exhausted_failure_and_reraises(monkeypatch):
    recorded = {}

    def fake_record_failure(conn, **kwargs):
        recorded.update(kwargs)
        return 42

    class AlwaysFailing:
        def get(self, url, **kwargs):
            raise urllib.error.HTTPError(url, 503, "busy", Message(), None)

    monkeypatch.setattr(pipeline.db, "record_failure", fake_record_failure)
    store = BronzeStore(FakeMinio(), "bronze")
    with pytest.raises(urllib.error.HTTPError):
        _download(AlwaysFailing(), store, None, cik=320193,
                  source="filing", accession="0000320193-25-000079",
                  url="https://www.sec.gov/Archives/x.htm")

    assert recorded["source"] == "filing"
    assert recorded["accession"] == "0000320193-25-000079"
    assert "HTTPError" in recorded["error"]


def test_filing_records_propagates_history_failure(monkeypatch):
    submissions = {
        "filings": {
            "recent": {
                "accessionNumber": ["r2025"],
                "form": ["10-K"],
                "reportDate": ["2025-09-27"],
                "filingDate": ["2025-11-01"],
                "primaryDocument": ["r2025.htm"],
            },
            "files": [{"name": "old-001.json", "filingTo": "2015-09-15"}],
        }
    }

    def failing_download(*args, **kwargs):
        raise TimeoutError("history download timed out")

    monkeypatch.setattr(pipeline, "_download", failing_download)
    with pytest.raises(TimeoutError):
        filing_records(None, None, None, 320193, submissions, years=3)


def test_run_fails_when_required_report_download_fails(monkeypatch):
    submissions = {
        "filings": {
            "recent": {
                "accessionNumber": ["a2025"],
                "form": ["10-K"],
                "reportDate": ["2025-09-27"],
                "filingDate": ["2025-11-01"],
                "primaryDocument": ["r2025.htm"],
            },
            "files": [],
        }
    }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, url, **kwargs):
            if url.endswith("api/xbrl/companyfacts/CIK0000320193.json"):
                return b'{"facts": {}}'
            if url.endswith("submissions/CIK0000320193.json"):
                return json.dumps(submissions).encode()
            raise urllib.error.HTTPError(url, 503, "busy", Message(), None)

    class FakeStore:
        bucket = "bronze"

        def __init__(self, *args, **kwargs):
            pass

        def ensure_bucket(self):
            pass

        def put_if_absent(self, *args, **kwargs):
            return True

    class FakeConnection:
        def close(self):
            pass

    monkeypatch.setattr(pipeline, "SecClient", FakeClient)
    monkeypatch.setattr(pipeline, "BronzeStore", FakeStore)
    monkeypatch.setattr(pipeline, "_minio_client", lambda: None)
    monkeypatch.setattr(pipeline.db, "connect", lambda: FakeConnection())
    monkeypatch.setattr(pipeline.db, "ensure_schema", lambda conn: None)
    monkeypatch.setattr(pipeline.db, "unpack_facts", lambda *args, **kwargs: 0)
    monkeypatch.setattr(pipeline.db, "record_manifest", lambda conn, **kwargs: 1)
    monkeypatch.setattr(pipeline.db, "record_failure", lambda conn, **kwargs: 2)
    monkeypatch.setattr(pipeline.db, "resolve_failures", lambda conn, **kwargs: None)

    with pytest.raises(urllib.error.HTTPError):
        pipeline.run("AAPL", years=3)


def test_download_resolves_failure_on_success(monkeypatch):
    events = []
    store = BronzeStore(FakeMinio(), "bronze")
    store.ensure_bucket()

    class Working:
        def get(self, url, **kwargs):
            return b"<html>annual report</html>"

    monkeypatch.setattr(pipeline.db, "record_manifest", lambda conn, **kwargs: 7)
    monkeypatch.setattr(pipeline.db, "resolve_failures",
                        lambda conn, **kwargs: events.append("resolved"))

    data, manifest_id = _download(Working(), store, None, cik=320193, source="filing",
                                  accession="acc", url="https://example.test/a.htm")

    assert data == b"<html>annual report</html>" and manifest_id == 7
    assert events == ["resolved"]


# --- fact unpacking ---------------------------------------------------------

def test_unpack_facts_keeps_every_fact_and_hashes_them():
    company_facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"start": "2023-01-01", "end": "2023-12-31", "val": 100,
                             "fy": 2023, "fp": "FY", "form": "10-K", "accn": "x"},
                            {"start": "2022-01-01", "end": "2022-12-31", "val": 90,
                             "fy": 2022, "fp": "FY", "form": "10-K", "accn": "y"},
                        ]
                    }
                }
            }
        }
    }
    conn = FakeConn()
    count = db.unpack_facts(conn, manifest_id=1, cik=320193, company_facts=company_facts)
    assert count == 2
    rows = conn.cursor_obj.rows
    assert {row[9] for row in rows} == {"100", "90"}
    assert rows[0][3] == "us-gaap:Revenues"
    assert len({row[2] for row in rows}) == 2  # distinct fact hashes
