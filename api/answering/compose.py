"""Compose a cited answer from the T005 evidence package (task T006).

Flow: build a prompt with stable source ids, call the model once, validate its
strict-JSON reply, keep only citations that resolve to application-supplied
sources (unknown ids are rejected), and record model/token/latency (and cost when
priced) as structured logs. Malformed, empty, or refused replies become an
abstained answer, never a 500 or a false success. No credentials or prompt text
are logged.
"""
from __future__ import annotations

import json
import logging
import os
import time

from api.answering.client import ChatResult, LLMError
from api.answering.prompt import build_messages, build_sources, calculation_summary
from api.router import answer_question
from api.schemas import Answer, Citation, QuestionRequest, QuestionResponse

logger = logging.getLogger("api.answering")

NO_EVIDENCE_TEXT = "No supporting evidence was found in the published gold datasets."
NO_EVIDENCE_LIMITATION = "No calculations or passages matched the request."


def configure_logging(level: int = logging.INFO) -> None:
    """Ensure completion metadata is emitted under the documented server launch.

    Uvicorn leaves `api.answering` at WARNING with no handler, which would drop
    the INFO audit records. Attach a stream handler once (it still propagates, so
    test capture keeps working).
    """
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(level)


def _log_completion(model, prompt_tokens, completion_tokens, latency_ms: int | None,
                    cost_usd: float | None, citations: int, status: str) -> None:
    # Only usage metadata: never the prompt, passage text, or API key.
    logger.info("llm.completion %s", json.dumps({
        "status": status,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "citations": citations,
    }))


def _usage(prompt_tokens, completion_tokens) -> dict:
    return {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}


def _cost(prompt_tokens, completion_tokens) -> float | None:
    in_price = os.environ.get("LLM_INPUT_COST_PER_1K")
    out_price = os.environ.get("LLM_OUTPUT_COST_PER_1K")
    if None in (in_price, out_price, prompt_tokens, completion_tokens):
        return None
    try:
        return round(
            prompt_tokens / 1000 * float(in_price)
            + completion_tokens / 1000 * float(out_price),
            6,
        )
    except (TypeError, ValueError):
        return None


def _loads(raw: str):
    """Parse strict JSON, tolerating a ```json fenced block; prose is rejected."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        first, _, rest = text.partition("\n")
        if first.strip().lower() in ("json", ""):
            text = rest
    try:
        return json.loads(text)
    except ValueError:
        return None


_REQUIRED_FIELDS = ("answer", "citations", "abstained", "limitations")


def _normalize_reply(result: ChatResult):
    """Return (fields, None) for a valid reply or (None, reason) otherwise.

    All four documented fields must be present with the right type; a blank
    answer is only acceptable as an explicit abstention.
    """
    if not result.content.strip():
        if result.refusal:
            return None, f"The model refused the request: {result.refusal}"
        return None, "The model returned an empty reply."
    data = _loads(result.content)
    if not isinstance(data, dict):
        return None, "The model reply was not valid JSON."
    missing = [field for field in _REQUIRED_FIELDS if field not in data]
    if missing:
        return None, "The model reply was missing field(s): " + ", ".join(missing) + "."
    if not isinstance(data["answer"], str):
        return None, "The model reply had no text answer."
    citations = data["citations"]
    if not isinstance(citations, list) or any(not isinstance(c, str) for c in citations):
        return None, "The model reply had malformed citations."
    abstained = data["abstained"]
    if not isinstance(abstained, bool):
        return None, "The model reply had a malformed abstention flag."
    limitations = data["limitations"]
    if limitations is not None and not isinstance(limitations, str):
        return None, "The model reply had malformed limitations."
    if not data["answer"].strip() and not abstained:
        return None, "The model reply had an empty answer."
    return (data["answer"], citations, abstained, limitations), None


def _citation(source: dict) -> Citation:
    return Citation(
        id=source["id"],
        kind=source["kind"],
        url=source.get("url"),
        accession=source.get("accession"),
        section=source.get("section"),
        label=source.get("label"),
    )


def compose_answer(question_text: str, calculations: list[dict],
                   passages: list[dict], *, client, clock=time.monotonic) -> Answer:
    sources = build_sources(calculations, passages)
    caveats = [note for calc in calculations for note in calc.get("notes", [])]
    if not sources:
        _log_completion(None, None, None, 0, None, 0, "no_evidence")
        return Answer(text=NO_EVIDENCE_TEXT, abstained=True,
                      limitations=NO_EVIDENCE_LIMITATION)

    messages = build_messages(question_text, sources, caveats,
                              calculation_summary(calculations))
    start = clock()
    try:
        result = client.complete(messages)
    except LLMError as exc:
        latency_ms = int((clock() - start) * 1000)
        # Retain any safe metadata the failure carried (model, billed tokens).
        model = exc.model or getattr(client, "model", None)
        cost = _cost(exc.prompt_tokens, exc.completion_tokens)
        _log_completion(model, exc.prompt_tokens, exc.completion_tokens,
                        latency_ms, cost, 0, "error")
        return Answer(text="", abstained=True, model=model,
                      usage=_usage(exc.prompt_tokens, exc.completion_tokens),
                      limitations=f"Answer composition failed: {exc}",
                      latency_ms=latency_ms, cost_usd=cost)
    latency_ms = int((clock() - start) * 1000)

    fields, problem = _normalize_reply(result)
    if fields is None:
        cost = _cost(result.prompt_tokens, result.completion_tokens)
        _log_completion(result.model, result.prompt_tokens, result.completion_tokens,
                        latency_ms, cost, 0, "invalid")
        return Answer(text="", abstained=True, model=result.model,
                      usage=_usage(result.prompt_tokens, result.completion_tokens),
                      limitations=problem, latency_ms=latency_ms, cost_usd=cost)

    text, requested, abstained, limitations = fields
    accepted = [c for c in requested if c in sources]
    rejected = [c for c in requested if c not in sources]
    citations = [_citation(sources[c]) for c in accepted]
    if rejected:
        note = "Rejected unknown citation id(s): " + ", ".join(rejected) + "."
        limitations = f"{limitations} {note}" if limitations else note

    cost = _cost(result.prompt_tokens, result.completion_tokens)
    _log_completion(result.model, result.prompt_tokens, result.completion_tokens,
                    latency_ms, cost, len(citations), "ok")
    return Answer(text=text, citations=citations, abstained=abstained,
                  limitations=limitations, model=result.model,
                  usage=_usage(result.prompt_tokens, result.completion_tokens),
                  latency_ms=latency_ms, cost_usd=cost)


def _describe_request(request: QuestionRequest) -> str:
    parts = [f"Report the requested figures for {request.company}"]
    if request.metric:
        parts.append(f"metric {request.metric}")
    if request.fiscal_years:
        years = ", ".join(str(year) for year in sorted(set(request.fiscal_years)))
        parts.append(f"fiscal years {years}")
    return " ".join(parts) + "."


def answer_question_with_citations(request: QuestionRequest, *, conn, company_ciks,
                                   encoder=None, client=None) -> QuestionResponse:
    """Answer, then (when a model is configured) attach a cited answer."""
    response = answer_question(
        request, conn=conn, company_ciks=company_ciks, encoder=encoder
    )
    if client is None or response.status != "ok":
        return response
    question_text = request.question or _describe_request(request)
    response.answer = compose_answer(
        question_text, response.calculations, response.passages, client=client
    )
    return response
