"""Bronze ingestion for one company.

Fetches SEC submission history (following older-history references as needed),
Company Facts, and the primary 10-K documents plus their amendments. Stores the
original bytes in MinIO (hash-addressed, write-once) and records
bronze.manifest / bronze.source_facts. Reruns are idempotent and exhausted
download failures are recorded for retry.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from ingestion import db
from ingestion.sec_client import SecClient
from ingestion.storage import BronzeStore, object_key

MAPPING_PATH = Path(__file__).resolve().parent / "mappings" / "companies.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
HISTORY_URL = "https://data.sec.gov/submissions/{name}"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
ANNUAL_FORMS = ("10-K", "10-K/A")


def load_mapping(path=MAPPING_PATH) -> dict:
    return json.loads(Path(path).read_text())


def _rows(section: dict) -> list:
    """Columnar SEC JSON (parallel lists) -> list of record dicts."""
    return [dict(zip(section.keys(), values)) for values in zip(*section.values())]


def _report_year(record) -> int | None:
    report = record.get("reportDate") or record.get("filingDate")
    return int(report[:4]) if report else None


def _original_years(records) -> set:
    return {
        year for record in records
        if record.get("form") == "10-K"
        for year in [_report_year(record)]
        if year is not None
    }


def select_10ks(records, years: int):
    """Select the original 10-K for each of the last `years` fiscal years and
    every associated 10-K/A amendment, preserving separate accessions.

    Business supersession is decided later (silver/gold); bronze keeps both the
    original report and its amendments.
    """
    originals = {}
    amendments = {}
    for record in records:
        form = record.get("form")
        if form not in ANNUAL_FORMS:
            continue
        year = _report_year(record)
        if year is None:
            continue
        if form == "10-K":
            current = originals.get(year)
            if current is None or record["filingDate"] < current["filingDate"]:
                originals[year] = record
        else:
            amendments.setdefault(year, []).append(record)
    selected = []
    for year in sorted(originals, reverse=True)[:years]:
        selected.append(originals[year])
        selected.extend(sorted(amendments.get(year, []), key=lambda r: r["filingDate"]))
    return selected


def _suffix(url: str) -> str:
    return Path(url.split("?", 1)[0]).suffix or ".bin"


def _content_type(suffix: str) -> str:
    if suffix == ".json":
        return "application/json"
    if suffix in (".htm", ".html"):
        return "text/html"
    return "application/octet-stream"


def _minio_client():
    from minio import Minio

    endpoint = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
    host = endpoint.split("://", 1)[-1]
    return Minio(
        host,
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        secure=endpoint.startswith("https://"),
    )


def _download(client, store, conn, *, cik, source, accession, url):
    """Fetch a URL and archive it.

    When retries are exhausted, a durable ``failed`` manifest row is recorded and
    the error is re-raised, so a missing required source cannot be mistaken for a
    successful run. Returns (bytes, manifest_id) on success.
    """
    try:
        data = client.get(url)
    except Exception as error:
        db.record_failure(
            conn, cik=cik, source=source, accession=accession, url=url,
            bucket=store.bucket, error=f"{type(error).__name__}: {error}",
        )
        raise
    digest = hashlib.sha256(data).hexdigest()
    suffix = _suffix(url)
    key = object_key(cik, source, digest, suffix)
    store.put_if_absent(key, data, _content_type(suffix))
    manifest_id = db.record_manifest(
        conn, cik=cik, source=source, accession=accession, url=url,
        bucket=store.bucket, object_key=key, content_hash=digest,
    )
    db.resolve_failures(conn, cik=cik, source=source, accession=accession, url=url)
    return data, manifest_id


def filing_records(client, store, conn, cik, submissions, years):
    """Merge recent submission history with referenced older-history files.

    Older files are fetched newest-first and only until the requested number of
    original annual reports is covered, per guide §2.2.
    """
    filings = submissions.get("filings", {})
    records = _rows(filings.get("recent", {}))
    for entry in sorted(filings.get("files", []), key=lambda e: e.get("filingTo", ""), reverse=True):
        if len(_original_years(records)) >= years:
            break
        url = HISTORY_URL.format(name=entry["name"])
        data, _ = _download(client, store, conn, cik=cik, source="history",
                            accession=None, url=url)
        records.extend(_rows(json.loads(data)))
    return records


def run(company: str, years: int = 3) -> None:
    if years < 1:
        raise SystemExit("years must be positive")
    mapping = load_mapping()
    entry = mapping.get(company.upper())
    if not entry:
        raise SystemExit(f"unknown company {company!r}; known: {', '.join(mapping)}")
    cik = int(entry["cik"])

    client = SecClient(os.environ.get("SEC_USER_AGENT", ""))
    store = BronzeStore(_minio_client(), os.environ.get("MINIO_BUCKET", "bronze"))
    store.ensure_bucket()
    conn = db.connect()
    try:
        db.ensure_schema(conn)

        submissions_url = SUBMISSIONS_URL.format(cik=cik)
        submissions_bytes, _ = _download(client, store, conn, cik=cik, source="submissions",
                                         accession=None, url=submissions_url)
        submissions = json.loads(submissions_bytes)

        facts_url = COMPANYFACTS_URL.format(cik=cik)
        facts_bytes, facts_manifest_id = _download(client, store, conn, cik=cik,
                                                   source="companyfacts", accession=None,
                                                   url=facts_url)
        db.unpack_facts(conn, facts_manifest_id, cik, json.loads(facts_bytes))

        records = filing_records(client, store, conn, cik, submissions, years)
        selected = select_10ks(records, years)
        for filing in selected:
            accession = filing["accessionNumber"]
            document = filing["primaryDocument"]
            url = ARCHIVE_URL.format(
                cik=cik, accession=accession.replace("-", ""), document=document
            )
            _download(client, store, conn, cik=cik, source="filing",
                      accession=accession, url=url)

        covered = len(_original_years(selected))
        if covered < years:
            raise SystemExit(
                f"only {covered} of {years} requested annual reports are available for {company}"
            )
    finally:
        conn.close()
