"""Passage retrieval over gold.retrieval_passages (carried citation metadata).

Runs one fixed, parameterized nearest-neighbor query against gold only, applying
the requested company and fiscal years (matched against each passage's filing
report_date) before ranking and limiting, so a request limited to FY2023 cannot
return a FY2025 passage. Superseded filings are excluded by default.
"""
from __future__ import annotations

from functools import lru_cache

from embeddings.search import search


@lru_cache(maxsize=1)
def _default_encoder():
    from embeddings.encoder import SentenceTransformerEncoder

    return SentenceTransformerEncoder()


def search_passages(question: str, *, conn, cik: int | None = None,
                    fiscal_years=None, accession: str | None = None,
                    limit: int = 5, include_superseded: bool = False,
                    encoder=None) -> list[dict]:
    return search(
        question, conn=conn, encoder=encoder or _default_encoder(), cik=cik,
        fiscal_years=fiscal_years, accession=accession, limit=limit,
        include_superseded=include_superseded,
    )
