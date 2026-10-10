"""Passage retrieval over gold.retrieval_passages (carried citation metadata).

Runs one fixed, parameterized nearest-neighbor query against gold only, applying
the requested company and fiscal years (matched against each passage's filing
report_date) before ranking and limiting, so a request limited to FY2023 cannot
return a FY2025 passage. Superseded filings are excluded by default.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from embeddings.pipeline import to_vector_literal

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"

_COLUMNS = ("passage_id", "cik", "accession", "section", "heading", "url",
            "text", "similarity")


@lru_cache(maxsize=1)
def _default_encoder():
    from embeddings.encoder import SentenceTransformerEncoder

    return SentenceTransformerEncoder()


def search_passages(question: str, *, conn, cik: int | None = None,
                    fiscal_years=None, accession: str | None = None,
                    limit: int = 5, include_superseded: bool = False,
                    encoder=None) -> list[dict]:
    encoder = encoder or _default_encoder()
    years = sorted(set(fiscal_years)) if fiscal_years else None
    literal = to_vector_literal(encoder.encode([question])[0])
    rows = conn.execute(
        (SQL_DIR / "search_passages.sql").read_text(),
        {"query_vector": literal, "model_version": encoder.model_version,
         "cik": cik, "accession": accession, "fiscal_years": years,
         "include_superseded": include_superseded, "limit": limit},
    ).fetchall()
    hits = [{**dict(zip(_COLUMNS, row))} for row in rows]
    for hit in hits:
        hit["similarity"] = float(hit["similarity"])
    return hits
