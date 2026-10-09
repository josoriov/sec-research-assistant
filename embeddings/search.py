"""Exact similarity search over published gold retrieval passages.

Embeds the question with the same model/version used for the stored vectors and
runs one parameterized nearest-neighbor query against gold only. Default
retrieval excludes superseded filings and can be narrowed by company and
accession. No approximate index or HTTP API (that is T005).
"""
from __future__ import annotations

import argparse

from embeddings import db
from embeddings.encoder import SentenceTransformerEncoder
from embeddings.pipeline import to_vector_literal


def search(question: str, *, cik: int | None = None, accession: str | None = None,
           include_superseded: bool = False, limit: int = 5,
           encoder=None, conn=None) -> list[dict]:
    encoder = encoder or SentenceTransformerEncoder()
    owns_connection = conn is None
    conn = conn or db.connect()
    try:
        literal = to_vector_literal(encoder.encode([question])[0])
        filters = []
        params = [literal, encoder.model_version]
        if cik is not None:
            filters.append("p.cik = %s")
            params.append(cik)
        if accession is not None:
            filters.append("p.accession = %s")
            params.append(accession)
        if not include_superseded:
            filters.append("p.is_superseded = false")
        where = (" and " + " and ".join(filters)) if filters else ""
        params.extend([literal, limit])
        rows = conn.execute(
            f"""
            select p.passage_id, p.cik, p.accession, p.section, p.heading, p.url,
                   p.text,
                   1 - (p.embedding <=> %s::vector) as similarity
            from gold.retrieval_passages p
            where p.model_version = %s{where}
            order by p.embedding <=> %s::vector
            limit %s
            """,
            params,
        ).fetchall()
        return [
            {
                "passage_id": row[0], "cik": row[1], "accession": row[2],
                "section": row[3], "heading": row[4], "url": row[5],
                "text": row[6], "similarity": float(row[7]),
            }
            for row in rows
        ]
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
