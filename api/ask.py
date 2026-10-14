"""Server-side orchestration for POST /ask (release v0.2 stage 3, task T011).

Receives the user's company and optional metric selections plus a free-text
prompt, interprets the metric and fiscal years with the T010 interpreter,
validates them into the existing `QuestionRequest` (T009), and executes the
result through the same in-process handler as POST /answer
(`answer_question_with_citations`). The complete evidence/cited-answer package
is preserved; a provider or malformed-reply failure becomes `status="error"`,
and a request that cannot be resolved becomes `needs_clarification`. No second
HTTP hop and no new dependency are involved.
"""
from __future__ import annotations

from collections.abc import Mapping

from api.answering import answer_question_with_citations
from api.interpretation import (
    Interpretation,
    InterpretationError,
    interpret_and_validate,
)
from api.schemas import AskRequest, AskResponse
from api.tools import list_metrics


def ask_question(request: AskRequest, *, conn, company_ciks: Mapping[str, int],
                 client, encoder=None) -> AskResponse:
    """Interpret, validate, and answer a natural-language question.

    `client` is the configured model; interpretation needs it, so an
    unconfigured model is an explicit error rather than a silent fallback. The
    explicit company/metric win over the model's candidates, and the original
    prompt is kept as the request's `question` (T010/T009).
    """
    if client is None:
        return AskResponse(
            status="error",
            error="question interpretation is not configured (set LLM_MODEL)",
        )

    selected = Interpretation(company=request.company, metric=request.metric)
    allowed = list_metrics(conn)
    try:
        result = interpret_and_validate(
            request.question, client=client, company_ciks=company_ciks,
            allowed_metrics=allowed, selected=selected,
        )
    except InterpretationError as exc:
        return AskResponse(
            status="error", error=f"could not interpret the question: {exc}"
        )

    if result.request is None:
        return AskResponse(
            status="needs_clarification", clarifications=result.clarifications
        )

    # Submit the validated payload to the same handler as POST /answer; this
    # preserves ok and needs_clarification and every response field.
    response = answer_question_with_citations(
        result.request, conn=conn, company_ciks=company_ciks, encoder=encoder,
        client=client,
    )
    return AskResponse(
        status=response.status,
        clarifications=response.clarifications,
        calculations=response.calculations,
        passages=response.passages,
        answer=response.answer,
        request=result.request,
    )
