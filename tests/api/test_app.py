"""Endpoint wiring: route registration and the handler's evidence/clarification flow.

No HTTP client (decision H007): the route's handler logic is exercised directly
through `answer_question` with a stub connection.
"""
import pytest
from fastapi.routing import APIRoute

from api.app import app
from api.router import answer_question
from api.schemas import QuestionRequest

CATALOG = [("net_income",), ("operating_cash_flow",), ("revenue",)]


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


def _annual_row():
    return (320193, "revenue", "USD", "2023-10-01", "2024-09-28", 2024,
            391035000000, False, 1, 2, "0000320193-24-000123", "10-K", "2024-11-01")


def test_questions_route_is_registered():
    assert any(
        isinstance(route, APIRoute)
        and route.path == "/questions"
        and route.methods is not None
        and "POST" in route.methods
        for route in app.routes
    )


def test_answer_question_returns_a_metric_calculation():
    conn = QueuedConn(CATALOG, [_annual_row()])
    response = answer_question(
        QuestionRequest(company="AAPL", metric="revenue", fiscal_years=[2024]),
        conn=conn, company_ciks={"AAPL": 320193},
    )
    assert response.status == "ok"
    assert response.calculations[0]["values"][0]["value"] == 391035000000.0
    assert len(conn.queries) == 2  # catalog lookup + one metric query


def test_answer_question_returns_passage_evidence():
    hits = [("12", 320193, "0000320193-24-000123", "Item 7.", "Item 7.",
             "https://www.sec.gov/x.htm", "revenue rose", 0.87)]

    class Encoder:
        model_version = "stub"
        dim = 2

        def encode(self, texts):
            return [[0.25, 0.5]]

    conn = QueuedConn(CATALOG, hits)
    response = answer_question(
        QuestionRequest(company="AAPL", question="why did revenue change?"),
        conn=conn, company_ciks={"AAPL": 320193}, encoder=Encoder(),
    )
    assert response.status == "ok"
    assert response.passages[0]["url"] == "https://www.sec.gov/x.htm"
    assert response.passages[0]["cik"] == 320193


def test_answer_question_clarifies_without_running_tools():
    conn = QueuedConn(CATALOG)
    response = answer_question(
        QuestionRequest(company="MSFT", metric="revenue"),
        conn=conn, company_ciks={"AAPL": 320193},
    )
    assert response.status == "needs_clarification"
    assert response.clarifications[0].field == "company"
    assert len(conn.queries) == 1  # only the metric catalog; no tool SQL


def test_get_metric_rejects_metric_outside_gold_mapping():
    conn = QueuedConn(CATALOG)
    response = answer_question(
        QuestionRequest(company="AAPL", metric="ebitda"),
        conn=conn, company_ciks={"AAPL": 320193},
    )
    assert response.status == "needs_clarification"
    assert response.clarifications[0].field == "metric"


@pytest.mark.parametrize("company", ["2147483648", "1" * 4301])
def test_answer_question_clarifies_on_unrepresentable_numeric_company(company):
    # F029: request-level regression for both reproduced inputs; no tool runs.
    conn = QueuedConn(CATALOG)
    response = answer_question(
        QuestionRequest(company=company, question="factory"),
        conn=conn, company_ciks={"AAPL": 320193},
    )
    assert response.status == "needs_clarification"
    assert response.clarifications[0].field == "company"
    assert len(conn.queries) == 1


def test_answer_question_clarifies_when_a_year_has_multiple_periods():
    compare_row = (
        2, "2022-09-30 to 2023-09-30, 2022-10-01 to 2023-09-30", 1, "2023-10-01 to 2024-09-28",
        100.0, "2022-10-01", "2023-09-30", False, 1, 2, "acc-2023", "10-K", "2023-11-01",
        150.0, "2023-10-01", "2024-09-28", False, 3, 4, "acc-2024", "10-K", "2024-11-01",
        50.0, 0.5,
    )
    conn = QueuedConn(CATALOG, [compare_row])
    response = answer_question(
        QuestionRequest(company="AAPL", metric="revenue", fiscal_years=[2023, 2024]),
        conn=conn, company_ciks={"AAPL": 320193},
    )
    assert response.status == "needs_clarification"
    assert response.clarifications[0].field == "fiscal_years"
    assert response.calculations == []
