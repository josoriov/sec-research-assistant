"""PostgreSQL bronze writes, using the pipeline role."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def connect():
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PIPELINE_DB_USER"],
        password=os.environ["PIPELINE_DB_PASSWORD"],
    )


def ensure_schema(conn) -> None:
    """Create bronze tables if missing. Idempotent; safe on existing volumes."""
    conn.execute(SCHEMA_PATH.read_text())
    conn.commit()


def record_manifest(conn, *, cik, source, accession, url, bucket, object_key,
                    content_hash, status="stored", error=None):
    """Insert a manifest row, or return the existing one for the same object."""
    row = conn.execute(
        """INSERT INTO bronze.manifest
               (cik, source, accession, url, bucket, object_key, content_hash, status, error)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (bucket, object_key) DO NOTHING
           RETURNING id""",
        (cik, source, accession, url, bucket, object_key, content_hash, status, error),
    ).fetchone()
    conn.commit()
    if row:
        return row[0]
    return conn.execute(
        "SELECT id FROM bronze.manifest WHERE bucket = %s AND object_key = %s",
        (bucket, object_key),
    ).fetchone()[0]


def record_failure(conn, *, cik, source, accession, url, bucket, error):
    """Persist an exhausted download failure for retry, without bytes to hash.

    Keeps a single outstanding failure per source location, so repeated failed
    attempts update the error instead of accumulating rows.
    """
    row = conn.execute(
        """UPDATE bronze.manifest
              SET error = %s, retrieved_at = now(), status = 'failed'
            WHERE cik = %s AND source = %s AND url = %s
              AND accession IS NOT DISTINCT FROM %s AND status = 'failed'
        RETURNING id""",
        (error, cik, source, url, accession),
    ).fetchone()
    if row is None:
        row = conn.execute(
            """INSERT INTO bronze.manifest
                   (cik, source, accession, url, bucket, object_key, content_hash, status, error)
               VALUES (%s, %s, %s, %s, %s, NULL, NULL, 'failed', %s)
               RETURNING id""",
            (cik, source, accession, url, bucket, error),
        ).fetchone()
    conn.commit()
    return row[0]


def resolve_failures(conn, *, cik, source, accession, url) -> None:
    """Mark outstanding failures for a source resolved after a successful fetch."""
    conn.execute(
        """UPDATE bronze.manifest
              SET status = 'resolved'
            WHERE cik = %s AND source = %s AND url = %s
              AND accession IS NOT DISTINCT FROM %s AND status = 'failed'""",
        (cik, source, url, accession),
    )
    conn.commit()


def unpack_facts(conn, manifest_id: int, cik: int, company_facts: dict) -> int:
    """Unpack every fact from Company Facts JSON, with no business filtering.

    Returns the number of source facts seen (inserted or already present).
    """
    rows = []
    for taxonomy, tags in company_facts.get("facts", {}).items():
        for tag, info in tags.items():
            for unit, facts in info.get("units", {}).items():
                for fact in facts:
                    fact_hash = hashlib.sha256(
                        json.dumps([taxonomy, tag, unit, fact], sort_keys=True).encode()
                    ).hexdigest()
                    rows.append((
                        manifest_id, cik, fact_hash, f"{taxonomy}:{tag}", taxonomy, tag,
                        unit, fact.get("start"), fact.get("end"), str(fact.get("val")),
                        fact.get("fy"), fact.get("fp"), fact.get("form"), fact.get("accn"),
                        fact.get("frame"), fact.get("filed"), Jsonb(fact),
                    ))
    with conn.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO bronze.source_facts
                   (manifest_id, cik, fact_hash, concept, taxonomy, tag, unit,
                    start_date, end_date, value_text, fiscal_year, fiscal_period,
                    form, accession, frame, filed_date, source)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (manifest_id, fact_hash) DO NOTHING""",
            rows,
        )
    conn.commit()
    return len(rows)
