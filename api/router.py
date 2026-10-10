"""Deterministic routing from a validated request to the approved tools.

No model selects the tool or its arguments inside T005 (decision H007): the
request is resolved and validated, then mapped to get_metric, compare_periods
and/or search_passages. Unresolvable requests return clarifications instead of
guessing.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from api import tools
from api.schemas import (
    Clarification,
    NeedsClarification,
    QuestionRequest,
    QuestionResponse,
    Tool,
)

# Only the supported decimal CIK spelling: ASCII digits. `str.isdigit()` accepts
# some Unicode digits (e.g. "²") that int() cannot parse.
_CIK_DIGITS = re.compile(r"[0-9]+")
# SEC CIKs are at most 10 digits and the persisted columns are PostgreSQL
# `integer` (int4). Reject anything longer or larger before converting, so
# neither int() nor the database cast can raise on invalid input.
_CIK_MAX_DIGITS = 10
_CIK_MAX = 2_147_483_647


@dataclass(frozen=True)
class Call:
    tool: Tool
    args: dict = field(default_factory=dict)


def resolve_company(company: str, company_ciks: Mapping[str, int]) -> int | None:
    """A supported numeric CIK passes through; a ticker is looked up case-insensitively.

    An unsupported numeric identifier (too long, or outside the persisted integer
    range) is treated as unresolved rather than converted, so it becomes a
    clarification instead of a crash.
    """
    text = company.strip()
    if _CIK_DIGITS.fullmatch(text):
        if len(text) > _CIK_MAX_DIGITS:
            return None
        value = int(text)
        return value if value <= _CIK_MAX else None
    return company_ciks.get(text.upper())


def company_cik_map(mapping=None) -> dict[str, int]:
    """Ticker -> int CIK from the ingestion mapping (or an injected mapping)."""
    if mapping is None:
        from ingestion.pipeline import load_mapping

        mapping = load_mapping()
    return {ticker.upper(): int(meta["cik"]) for ticker, meta in mapping.items()}


def _infer_tools(request: QuestionRequest) -> list[Tool]:
    selected: list[Tool] = []
    if request.metric is not None:
        selected.append(
            Tool.compare_periods if len(request.fiscal_years) == 2 else Tool.get_metric
        )
    if request.question is not None:
        selected.append(Tool.search_passages)
    return selected


def plan(request: QuestionRequest, *, company_ciks: Mapping[str, int],
         allowed_metrics) -> tuple[list[Clarification], list[Call]]:
    """Resolve the request into clarifications and/or approved tool calls."""
    clarifications: dict[str, str] = {}

    def clarify(field: str, reason: str) -> None:
        clarifications.setdefault(field, reason)

    cik = resolve_company(request.company, company_ciks)
    if cik is None:
        clarify("company", f"unknown company {request.company!r}")

    metric = request.metric
    if metric is not None and metric not in allowed_metrics:
        clarify(
            "metric",
            f"unsupported metric {metric!r}; choose one of {sorted(allowed_metrics)}",
        )

    if len(request.fiscal_years) > 2:
        clarify("fiscal_years", "provide at most two fiscal years")
    years = sorted(set(request.fiscal_years))

    selected = [request.tool] if request.tool else _infer_tools(request)
    if not selected:
        clarify(
            "question",
            "provide a metric (with optional fiscal years) or a question to search filings",
        )

    calls: list[Call] = []
    for tool in selected:
        if tool is Tool.search_passages:
            if not request.question:
                clarify("question", "search_passages requires a question")
                continue
            calls.append(Call(tool, {
                "question": request.question, "cik": cik, "limit": request.limit,
                "fiscal_years": years, "include_superseded": request.include_superseded,
            }))
        elif tool is Tool.get_metric:
            if metric is None:
                clarify("metric", "get_metric requires a metric")
            if cik is not None and metric is not None:
                calls.append(Call(tool, {
                    "cik": cik, "metric": metric, "fiscal_years": years or None,
                }))
        elif tool is Tool.compare_periods:
            if metric is None:
                clarify("metric", "compare_periods requires a metric")
            if len(years) != 2:
                clarify("fiscal_years", "compare_periods requires exactly two fiscal years")
            if cik is not None and metric is not None and len(years) == 2:
                calls.append(Call(tool, {
                    "cik": cik, "metric": metric, "year_a": years[0], "year_b": years[1],
                }))

    ordered = [Clarification(field=name, reason=reason)
               for name, reason in clarifications.items()]
    # Either the request is fully resolved, or it needs clarification; never both,
    # so a partially resolved request cannot be executed by mistake.
    return (ordered, []) if ordered else ([], calls)


def answer_question(request: QuestionRequest, *, conn, company_ciks,
                    encoder=None) -> QuestionResponse:
    """Resolve, route, execute the approved tools, and return an evidence package."""
    allowed = tools.list_metrics(conn)
    clarifications, calls = plan(
        request, company_ciks=company_ciks, allowed_metrics=allowed
    )
    if clarifications:
        return QuestionResponse(status="needs_clarification", clarifications=clarifications,
                                calculations=[], passages=[])

    calculations: list[dict] = []
    passages: list[dict] = []
    try:
        for call in calls:
            if call.tool is Tool.get_metric:
                calculations.append(tools.financials.get_metric(conn, **call.args))
            elif call.tool is Tool.compare_periods:
                calculations.append(tools.financials.compare_periods(conn, **call.args))
            elif call.tool is Tool.search_passages:
                passages.extend(
                    tools.passages.search_passages(conn=conn, encoder=encoder, **call.args)
                )
    except NeedsClarification as exc:
        return QuestionResponse(
            status="needs_clarification",
            clarifications=[Clarification(field=exc.field, reason=exc.reason)],
            calculations=[], passages=[],
        )
    return QuestionResponse(status="ok", clarifications=[], calculations=calculations,
                            passages=passages)
