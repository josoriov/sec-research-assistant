"""FastAPI application exposing POST /questions (task T005).

The route opens a read-only gold connection per request and delegates to
`api.router.answer_question`. It handles no LLM answer composition (that is
T006); it returns the calculation and passage evidence package.
"""
from __future__ import annotations

from fastapi import FastAPI

from api import db
from api.router import answer_question, company_cik_map
from api.schemas import QuestionRequest, QuestionResponse


def create_app() -> FastAPI:
    app = FastAPI(
        title="SEC Research Assistant",
        version="0.1.0",
        description="Question API over published gold datasets (revenue, net income, "
        "operating cash flow, and cited filing passages).",
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/questions", response_model=QuestionResponse)
    def questions(request: QuestionRequest) -> QuestionResponse:
        conn = db.connect()
        try:
            return answer_question(request, conn=conn, company_ciks=company_cik_map())
        finally:
            conn.close()

    return app


app = create_app()
