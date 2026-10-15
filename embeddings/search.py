"""Exact similarity search over published gold retrieval passages.

Embeds the question with the same model/version used for the stored vectors and
runs one parameterized nearest-neighbor query against gold only. Default
retrieval excludes superseded filings and can be narrowed by company and
accession. The question API uses this same query and result mapping, with an
injected gold-only connection and optional fiscal-year filters.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from embeddings import db
from embeddings.encoder import SentenceTransformerEncoder
from embeddings.pipeline import to_vector_literal

SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "search_passages.sql"
_COLUMNS = ("passage_id", "cik", "accession", "section", "heading", "url",
            "text", "similarity")


def search(question: str, *, cik: int | None = None, accession: str | None = None,
           fiscal_years=None, include_superseded: bool = False, limit: int = 5,
           encoder=None, conn=None) -> list[dict]:
    encoder = encoder or SentenceTransformerEncoder()
    owns_connection = conn is None
    conn = conn or db.connect()
    try:
        literal = to_vector_literal(encoder.encode([question])[0])
        rows = conn.execute(
            SQL_PATH.read_text(),
            {"query_vector": literal, "model_version": encoder.model_version,
             "cik": cik, "accession": accession,
             "fiscal_years": sorted(set(fiscal_years)) if fiscal_years else None,
             "include_superseded": include_superseded, "limit": limit},
        ).fetchall()
        hits = [dict(zip(_COLUMNS, row)) for row in rows]
        for hit in hits:
            hit["similarity"] = float(hit["similarity"])
        return hits
    finally:
        if owns_connection:
            conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exact similarity search over gold.retrieval_passages"
    )
    parser.add_argument("question")
    parser.add_argument("--cik", type=int, default=None)
    parser.add_argument("--accession", default=None)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--include-superseded", action="store_true")
    args = parser.parse_args()
    hits = search(
        args.question, cik=args.cik, accession=args.accession,
        include_superseded=args.include_superseded, limit=args.limit,
    )
    if not hits:
        print("no matching passages")
        return
    for hit in hits:
        print(f"{hit['similarity']:.3f}  {hit['accession']}  {hit['section']}  {hit['url']}")
        print(f"    {hit['text'][:160]}")


if __name__ == "__main__":
    main()
