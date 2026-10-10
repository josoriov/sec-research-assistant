"""PostgreSQL reads/writes for embeddings, using the shared pipeline credentials."""
from __future__ import annotations

from pathlib import Path

from ingestion.db import connect  # same pipeline role/credentials as ingestion

__all__ = [
    "connect",
    "count_embeddings",
    "ensure_schema",
    "existing_keys",
    "insert_embeddings",
    "load_passages",
]

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def ensure_schema(conn) -> None:
    """Create the embeddings table if missing. Idempotent."""
    conn.execute(SCHEMA_PATH.read_text())
    conn.commit()


def load_passages(conn, processing_version: str) -> list[dict]:
    """Validated silver passages eligible for embedding (active version only)."""
    rows = conn.execute(
        """SELECT passage_hash, processing_version, section, text
             FROM silver.passages
            WHERE processing_version = %s""",
        (processing_version,),
    ).fetchall()
    return [
        {"passage_hash": r[0], "processing_version": r[1], "section": r[2], "text": r[3]}
        for r in rows
    ]


def existing_keys(conn, model_version: str) -> set[tuple[str, str]]:
    rows = conn.execute(
        """SELECT passage_hash, processing_version
             FROM silver.passage_embeddings
            WHERE model_version = %s""",
        (model_version,),
    ).fetchall()
    return {(r[0], r[1]) for r in rows}


def insert_embeddings(conn, rows) -> None:
    """rows: (passage_hash, processing_version, model_version, dim, vector literal)."""
    with conn.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO silver.passage_embeddings
                   (passage_hash, processing_version, model_version, dim, embedding)
               VALUES (%s, %s, %s, %s, %s::vector)
               ON CONFLICT (passage_hash, processing_version, model_version)
               DO NOTHING""",
            rows,
        )
    conn.commit()


def count_embeddings(conn, model_version: str) -> int:
    return conn.execute(
        "SELECT count(*) FROM silver.passage_embeddings WHERE model_version = %s",
        (model_version,),
    ).fetchone()[0]
