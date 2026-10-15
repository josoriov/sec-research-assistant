"""PostgreSQL writes for extraction, using the shared pipeline credentials."""
from __future__ import annotations

from pathlib import Path

from ingestion.db import connect  # same pipeline role/credentials as ingestion

__all__ = [
    "connect",
    "ensure_schema",
    "load_filing_manifests",
    "load_submission_objects",
    "replace_blocks",
    "upsert_document",
]

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def ensure_schema(conn) -> None:
    """Create the extraction tables if missing. Idempotent."""
    conn.execute(SCHEMA_PATH.read_text())
    conn.commit()


def load_filing_manifests(conn) -> list[dict]:
    """Stored filing HTML objects, one per manifest row."""
    rows = conn.execute(
        """SELECT id, cik, accession, url, object_key
             FROM bronze.manifest
            WHERE source = 'filing' AND status = 'stored' AND object_key IS NOT NULL
            ORDER BY id"""
    ).fetchall()
    return [
        {"id": r[0], "cik": r[1], "accession": r[2], "url": r[3], "object_key": r[4]}
        for r in rows
    ]


def load_submission_objects(conn, cik: int) -> list[dict]:
    """Every stored submissions/history JSON for a company, newest first."""
    rows = conn.execute(
        """SELECT object_key
             FROM bronze.manifest
            WHERE cik = %s AND source IN ('submissions', 'history')
              AND status = 'stored' AND object_key IS NOT NULL
            ORDER BY id DESC""",
        (cik,),
    ).fetchall()
    return [{"object_key": r[0]} for r in rows]


def upsert_document(conn, *, manifest_id, cik, accession, form, filing_date,
                    report_date, primary_document, url, extraction_error=None) -> None:
    """Insert/update a filing document.

    Blank metadata is treated as missing (NULLIF), so neither a NULL nor an
    empty/whitespace value from a newer snapshot can erase a known field.
    """
    conn.execute(
        """INSERT INTO bronze.filing_documents
               (manifest_id, cik, accession, form, filing_date, report_date,
                primary_document, url, extraction_error)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (manifest_id) DO UPDATE
               SET cik = EXCLUDED.cik,
                   accession = EXCLUDED.accession,
                   form = COALESCE(NULLIF(btrim(EXCLUDED.form), ''), filing_documents.form),
                   filing_date = COALESCE(NULLIF(btrim(EXCLUDED.filing_date), ''), filing_documents.filing_date),
                   report_date = COALESCE(NULLIF(btrim(EXCLUDED.report_date), ''), filing_documents.report_date),
                   primary_document = COALESCE(NULLIF(btrim(EXCLUDED.primary_document), ''), filing_documents.primary_document),
                   url = EXCLUDED.url,
                   extraction_error = EXCLUDED.extraction_error""",
        (manifest_id, cik, accession, form, filing_date, report_date,
         primary_document, url, extraction_error),
    )
    conn.commit()


def replace_blocks(conn, *, manifest_id, cik, accession, processing_version,
                   blocks) -> int:
    """Insert this version's blocks, skipping hashes already stored.

    Rows are keyed by (manifest_id, block_hash, processing_version); a rerun of
    the same processing version is a no-op and keeps stable row ids. Bump the
    processing version when the parser changes.
    """
    if blocks:
        with conn.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO bronze.document_blocks
                       (manifest_id, cik, accession, block_ordinal, section,
                        heading, text, block_hash, processing_version)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (manifest_id, block_hash, processing_version)
                   DO NOTHING""",
                [
                    (manifest_id, cik, accession, block["block_ordinal"],
                     block["section"], block["heading"], block["text"],
                     block["block_hash"], processing_version)
                    for block in blocks
                ],
            )
        conn.commit()
    return len(blocks)
