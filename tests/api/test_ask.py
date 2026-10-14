"""Release v0.2 stage 3 (T011): orchestration behind POST /ask.

Offline: the model is an injected fake and the database is a stub connection, so
no network, credential, or live gold data is used. The orchestration interprets
the prompt (T010), validates it (T009), and executes the validated request
through the same handler as POST /answer.
"""
import json

import pytest

from api.answering.client import ChatResult, LLMError
from api.ask import ask_question
from api.schemas import AskRequest

CATALOG = [("net_income",), ("operating_cash_flow",), ("revenue",)]
CIKS = {"AAPL": 320193}


class Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class QueuedConn:
    """Returns canned rows in call order and records every statement."""

    def __init__(self, *results):
        self._results = list(results)
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append((sql, params))
        return Cursor(self._results.pop(0))


class Encoder:
    model_version = "stub"
    dim = 2

    def encode(self, texts):
        return [[0.25, 0.5]]


class ScriptedClient:
    """Returns queued replies in call order (interpretation, then composition)."""

    model = "fake-model"

    def __init__(self, *contents):
        self._contents = list(contents)
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        return ChatResult(self._contents.pop(0), self.model, prompt_tokens=10,
                          completion_tokens=5)


class FailingClient:
    model = "configured-model"

    def complete(self, messages):
        raise LLMError("endpoint down", model="returned-model")


def _metric_row(metric="revenue", value=391035000000.0, year=2024):
    return (320193, metric, "USD", "2023-10-01", "2024-09-28", year, value,
            False, 1, 2, "0000320193-24-000123", "10-K", "2024-11-01")


def _compare_row():
    return (
        1, "2022-10-01 to 2023-09-30", 1, "2023-10-01 to 2024-09-28",
        383285000000.0, "2022-10-01", "2023-09-30", False, 3, 2,
        "0000320193-23-000106", "10-K", "2023-11-03",
        391035000000.0, "2023-10-01", "2024-09-28", False, 1, 2,
        "0000320193-24-000123", "10-K", "2024-11-01",
        7750000000.0, 0.0202,
    )


def _ambiguous_compare_row():
    # count_a = 2 => the tool must clarify rather than guess between periods.
    return (
        2, "2022-09-30 to 2023-09-30, 2022-10-01 to 2023-09-30", 1,
        "2023-10-01 to 2024-09-28",
        100.0, "2022-10-01", "2023-09-30", False, 1, 2, "acc-2023", "10-K", "2023-11-01",
        150.0, "2023-10-01", "2024-09-28", False, 3, 4, "acc-2024", "10-K", "2024-11-01",
        50.0, 0.5,
    )


def _passage():
    return (12, 320193, "0000320193-24-000123", "Item 7.", "Item 7.",
            "https://www.sec.gov/x.htm", "revenue rose", 0.87)


def _interp(metric, years, clarifications=None):
    payload = {"metric": metric, "fiscal_years": list(years)}
    if clarifications is not None:
        payload["clarifications"] = clarifications
    return json.dumps(payload)


def _answer(citations=("metric:320193:revenue:2023-10-01:2024-09-28",),
            text="Revenue rose.", abstained=False, limitations=None):
    return json.dumps({"answer": text, "citations": list(citations),
                       "abstained": abstained, "limitations": limitations})


def test_ask_comparison_question_returns_the_complete_package():
    client = ScriptedClient(_interp("revenue", [2023, 2024]), _answer())
    conn = QueuedConn(CATALOG, CATALOG, [_compare_row()], [_passage()])
    response = ask_question(
        AskRequest(company="AAPL",
                   question="What drove the revenue change between 2023 and 2024?"),
        conn=conn, company_ciks=CIKS, client=client, encoder=Encoder(),
    )
    assert response.status == "ok"
    assert response.error is None
    assert response.request is not None
    assert response.request.company == "AAPL"
    assert response.request.metric == "revenue"
    assert response.request.fiscal_years == [2023, 2024]
    assert response.request.question == "What drove the revenue change between 2023 and 2024?"
    assert response.calculations[0]["tool"] == "compare_periods"
    assert response.passages  # both tools ran (combined request)
    assert response.answer is not None and response.answer.citations
    assert len(client.calls) == 2  # interpretation + composition


def test_ask_qualitative_question_needs_no_metric():
    client = ScriptedClient(_interp(None, []),
                            _answer(citations=["passage:12"], text="Risks are described."))
    conn = QueuedConn(CATALOG, CATALOG, [_passage()])
    response = ask_question(
        AskRequest(company="AAPL", question="What risks are described?"),
        conn=conn, company_ciks=CIKS, client=client, encoder=Encoder(),
    )
    assert response.status == "ok"
    assert response.request is not None and response.request.metric is None
    assert response.calculations == []
    assert response.passages[0]["passage_id"] == 12


def test_ask_explicit_metric_overrides_interpretation():
    client = ScriptedClient(_interp("revenue", [2024]),
                            _answer(citations=["metric:320193:net_income:2023-10-01:2024-09-28"]))
    conn = QueuedConn(CATALOG, CATALOG, [_metric_row(metric="net_income")], [_passage()])
    response = ask_question(
        AskRequest(company="AAPL", metric="net_income", question="how did it change?"),
        conn=conn, company_ciks=CIKS, client=client, encoder=Encoder(),
    )
    assert response.request is not None and response.request.metric == "net_income"
    assert response.calculations[0]["metric"] == "net_income"


def test_ask_model_declared_ambiguity_is_not_executed():
    content = _interp(None, [], clarifications=[
        {"field": "metric", "reason": "Revenue or net income?"},
    ])
    conn = QueuedConn(CATALOG)
    response = ask_question(
        AskRequest(company="AAPL", question="how did it change in 2024?"),
        conn=conn, company_ciks=CIKS, client=ScriptedClient(content),
    )
    assert response.status == "needs_clarification"
    assert [c.field for c in response.clarifications] == ["metric"]
    assert response.request is None and response.error is None
    assert len(conn.queries) == 1  # only the metric catalog; no tool ran


def test_ask_invalid_candidate_becomes_a_clarification():
    conn = QueuedConn(CATALOG)
    response = ask_question(
        AskRequest(company="AAPL", question="what was ebitda in 2024?"),
        conn=conn, company_ciks=CIKS,
        client=ScriptedClient(_interp("ebitda", [2024])),
    )
    assert response.status == "needs_clarification"
    assert [c.field for c in response.clarifications] == ["metric"]
    assert response.request is None


def test_ask_preserves_a_tool_level_clarification():
    # The endpoint can still ask for clarification after validation (F027):
    # the validated request is returned alongside it.
    conn = QueuedConn(CATALOG, CATALOG, [_ambiguous_compare_row()])
    response = ask_question(
        AskRequest(company="AAPL", question="compare revenue 2023 and 2024"),
        conn=conn, company_ciks=CIKS,
        client=ScriptedClient(_interp("revenue", [2023, 2024])), encoder=Encoder(),
    )
    assert response.status == "needs_clarification"
    assert [c.field for c in response.clarifications] == ["fiscal_years"]
    assert response.request is not None and response.request.metric == "revenue"


def test_ask_provider_failure_is_an_error():
    conn = QueuedConn(CATALOG)
    response = ask_question(
        AskRequest(company="AAPL", question="why did revenue change?"),
        conn=conn, company_ciks=CIKS, client=FailingClient(),
    )
    assert response.status == "error"
    assert response.error is not None and "endpoint down" in response.error
    assert response.request is None


def test_ask_malformed_reply_is_an_error():
    conn = QueuedConn(CATALOG)
    response = ask_question(
        AskRequest(company="AAPL", question="why did revenue change?"),
        conn=conn, company_ciks=CIKS, client=ScriptedClient("not json"),
    )
    assert response.status == "error"
    assert response.error


def test_ask_without_a_configured_model_is_an_error():
    conn = QueuedConn()  # never touched
    response = ask_question(
        AskRequest(company="AAPL", question="why did revenue change?"),
        conn=conn, company_ciks=CIKS, client=None,
    )
    assert response.status == "error"
    assert response.error is not None and "LLM_MODEL" in response.error
    assert conn.queries == []


def test_ask_response_status_includes_an_error_state():
    # AskResponse adds an explicit error state; the /answer contract does not.
    from pydantic import ValidationError

    from api.schemas import AskResponse, QuestionResponse

    assert AskResponse(status="error").status == "error"
    with pytest.raises(ValidationError):
        QuestionResponse.model_validate({"status": "error"})
