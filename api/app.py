"""FastAPI application exposing POST /questions (tasks T005 and T006).

The route opens a read-only gold connection per request, runs the approved tools
(`api.router.answer_question`), and — when a language model is configured —
attaches a cited answer (`api.answering`). Without a configured model the
response is exactly the T005 evidence package.
"""
from __future__ import annotations

from fastapi import FastAPI

from api import db
from api.answering import (
    answer_question_with_citations,
    client_from_env,
    configure_logging,
)
from api.router import company_cik_map
from api.schemas import QuestionRequest, QuestionResponse


def create_app(client=None) -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="SEC Research Assistant",
        version="0.2.0",
        description="Question API over published gold datasets (revenue, net income, "
        "operating cash flow, and cited filing passages).",
    )
    llm_client = client if client is not None else client_from_env()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "answer_composition": llm_client is not None}

    # exclude_unset omits `answer` when composition is disabled, so the T005
    # response contract is preserved (H008); nested explicit NULLs are untouched.
    @app.post("/questions", response_model=QuestionResponse,
              response_model_exclude_unset=True)
    def questions(request: QuestionRequest) -> QuestionResponse:
        conn = db.connect()
        try:
            return answer_question_with_citations(
                request, conn=conn, company_ciks=company_cik_map(), client=llm_client
            )
        finally:
            conn.close()

    return app


app = create_app()
