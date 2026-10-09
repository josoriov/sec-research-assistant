"""Embed validated silver passages into silver.passage_embeddings.

Runs after the silver build (dbt) and before the gold build. Vectors are reused
when (passage_hash, processing_version, model_version) already match, so a rerun
re-embeds nothing.
"""
from __future__ import annotations

from embeddings import db
from embeddings.encoder import SentenceTransformerEncoder
from extraction import PROCESSING_VERSION

BATCH_SIZE = 64


def embedding_input(passage: dict) -> str:
    """Passage text for the model, prefixed with its section for context."""
    section = passage.get("section")
    text = passage.get("text") or ""
    return f"{section}\n{text}" if section else text


def select_missing(passages: list[dict], existing: set[tuple[str, str]]) -> list[dict]:
    """Passages with no stored vector for the current processing+model version."""
    return [
        passage for passage in passages
        if (passage["passage_hash"], passage["processing_version"]) not in existing
    ]


def verify_complete(passages: list[dict], existing: set[tuple[str, str]]) -> None:
    """Refuse to finish if any passage still lacks a vector (publication gate)."""
    remaining = select_missing(passages, existing)
    if remaining:
        raise RuntimeError(
            f"{len(remaining)} silver passages have no embedding for this model version"
        )


def to_vector_literal(vector) -> str:
    return "[" + ",".join(repr(float(value)) for value in vector) + "]"


def run(encoder=None, conn=None):
    """Embed passages that need a vector; return a small summary dict."""
    encoder = encoder or SentenceTransformerEncoder()
    owns_connection = conn is None
    conn = conn or db.connect()
    try:
        db.ensure_schema(conn)
        passages = db.load_passages(conn, PROCESSING_VERSION)
        existing = db.existing_keys(conn, encoder.model_version)
        missing = select_missing(passages, existing)
        embedded = 0
        for start in range(0, len(missing), BATCH_SIZE):
            batch = missing[start:start + BATCH_SIZE]
            vectors = encoder.encode([embedding_input(p) for p in batch])
            db.insert_embeddings(conn, [
                (p["passage_hash"], p["processing_version"], encoder.model_version,
                 encoder.dim, to_vector_literal(vector))
                for p, vector in zip(batch, vectors)
            ])
            embedded += len(batch)
        verify_complete(passages, db.existing_keys(conn, encoder.model_version))
        return {
            "total": len(passages),
            "reused": len(passages) - len(missing),
            "embedded": embedded,
            "model_version": encoder.model_version,
            "dim": encoder.dim,
        }
    finally:
        if owns_connection:
            conn.close()
