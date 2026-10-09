"""Extraction pipeline: bronze filing HTML -> bronze.filing_documents + blocks.

Reads the stored filing HTML from MinIO and metadata from every preserved
submissions/history JSON for the company (so accessions that have aged out of the
newest snapshot keep their form/dates), then writes the raw extracted text into
bronze. dbt validates it into silver.
"""
from __future__ import annotations

import json
import os

from extraction import db
from extraction.parse import PROCESSING_VERSION, extract_blocks
from ingestion.pipeline import _minio_client

METADATA_FIELDS = ("form", "filingDate", "reportDate", "primaryDocument")


def _read_object(client, bucket: str, key: str) -> bytes:
    response = client.get_object(bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def submission_records(payload: dict) -> list[dict]:
    """Records from a root submissions payload or a columnar history file."""
    if isinstance(payload, dict) and "filings" in payload:
        section = payload.get("filings", {}).get("recent", {})
    else:
        section = payload
    if not isinstance(section, dict) or not section:
        return []
    if not all(isinstance(values, list) for values in section.values()):
        return []
    return [dict(zip(section.keys(), values)) for values in zip(*section.values())]


def merge_accession_metadata(payloads: list[dict]) -> dict:
    """Union accession -> record across snapshots, newest first.

    A field is only filled when it is currently unknown, so an older snapshot
    supplies metadata that a newer one no longer lists and never blanks it.
    Empty/whitespace-only values count as unknown.
    """
    merged: dict[str, dict] = {}
    for payload in payloads:
        for record in submission_records(payload):
            accession = record.get("accessionNumber")
            if isinstance(accession, str):
                accession = accession.strip()
            if not accession:
                continue
            slot = merged.setdefault(accession, {})
            for key, value in record.items():
                if isinstance(value, str):
                    value = value.strip() or None
                if value is not None and slot.get(key) is None:
                    slot[key] = value
    return merged


def run(processing_version: str = PROCESSING_VERSION):
    """Extract every stored filing. Idempotent per processing version."""
    conn = db.connect()
    client = _minio_client()
    bucket = os.environ.get("MINIO_BUCKET", "bronze")
    documents = 0
    passages = 0
    failures = 0
    try:
        db.ensure_schema(conn)
        metadata_by_cik: dict[int, dict] = {}
        for filing in db.load_filing_manifests(conn):
            cik = filing["cik"]
            if cik not in metadata_by_cik:
                objects = db.load_submission_objects(conn, cik)
                payloads = [
                    json.loads(_read_object(client, bucket, obj["object_key"]))
                    for obj in objects
                ]
                metadata_by_cik[cik] = merge_accession_metadata(payloads)
            metadata = metadata_by_cik[cik].get(filing["accession"], {})
            html = _read_object(client, bucket, filing["object_key"])
            blocks = extract_blocks(html, processing_version)
            # A stored document that yields no usable text is a source-linked
            # extraction failure, not a successful evidence-free filing.
            extraction_error = None if blocks else "no_usable_text"
            db.upsert_document(
                conn,
                manifest_id=filing["id"],
                cik=cik,
                accession=filing["accession"],
                form=metadata.get("form"),
                filing_date=metadata.get("filingDate"),
                report_date=metadata.get("reportDate"),
                primary_document=metadata.get("primaryDocument"),
                url=filing["url"],
                extraction_error=extraction_error,
            )
            db.replace_blocks(
                conn,
                manifest_id=filing["id"],
                cik=cik,
                accession=filing["accession"],
                processing_version=processing_version,
                blocks=blocks,
            )
            if extraction_error:
                failures += 1
            else:
                documents += 1
                passages += len(blocks)
    finally:
        conn.close()
    return documents, passages, failures
