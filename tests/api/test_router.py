"""Deterministic routing: tool selection, validation, and clarification.

Pure logic: no database or model is touched.
"""
import pytest
from pydantic import ValidationError

from api.router import Call, plan, resolve_company
from api.schemas import QuestionRequest, Tool

CIKS = {"AAPL": 320193}
METRICS = ["net_income", "operating_cash_flow", "revenue"]


def route(**kwargs):
    return plan(QuestionRequest(**kwargs), company_ciks=CIKS, allowed_metrics=METRICS)


def test_resolve_company_accepts_ticker_and_numeric_cik():
    assert resolve_company("aapl", CIKS) == 320193
    assert resolve_company(" 320193 ", CIKS) == 320193
    assert resolve_company("MSFT", CIKS) is None


def test_infers_compare_for_two_years():
    clarifications, calls = route(company="AAPL", metric="revenue", fiscal_years=[2025, 2023])
    assert clarifications == []
    assert calls == [
        Call(Tool.compare_periods, {"cik": 320193, "metric": "revenue",
                                   "year_a": 2023, "year_b": 2025})
    ]


def test_infers_get_metric_for_one_year_and_no_years():
    _, calls = route(company="AAPL", metric="net_income", fiscal_years=[2024])
    assert calls[0].tool is Tool.get_metric
    assert calls[0].args["fiscal_years"] == [2024]
    _, calls = route(company="AAPL", metric="net_income")
    assert calls[0].args["fiscal_years"] is None


def test_metric_plus_question_runs_both_approved_tools():
    _, calls = route(company="AAPL", metric="revenue", question="why did it change?")
    assert {call.tool for call in calls} == {Tool.get_metric, Tool.search_passages}


def test_question_only_searches_passages():
    _, calls = route(company="AAPL", question="supply chain risks")
    assert calls[0].tool is Tool.search_passages
    assert calls[0].args["cik"] == 320193


def test_search_call_carries_requested_years():
    _, calls = route(company="AAPL", question="why did it change?", fiscal_years=[2023])
    assert calls[0].args["fiscal_years"] == [2023]


def test_non_ascii_digit_company_is_clarified_not_crashed():
    # "²" is a Unicode digit to str.isdigit() but not parseable by int().
    clarifications, calls = route(company="\u00b2", metric="revenue")
    assert calls == []
    assert clarifications[0].field == "company"


def test_out_of_range_numeric_company_is_clarified():
    # F029: exceeds the persisted PostgreSQL integer CIK representation.
    clarifications, calls = route(company="2147483648", metric="revenue")
    assert calls == []
    assert clarifications[0].field == "company"


def test_overlong_digit_company_is_clarified_not_crashed():
    # F029: a huge digit string would raise on int() conversion otherwise.
    clarifications, calls = route(company="1" * 4301, metric="revenue")
    assert calls == []
    assert clarifications[0].field == "company"


def test_supported_numeric_ciks_still_resolve():
    assert resolve_company("0000320193", CIKS) == 320193
    assert resolve_company("2147483647", CIKS) == 2_147_483_647


def test_explicit_tool_overrides_inference():
    _, calls = route(company="AAPL", metric="revenue", fiscal_years=[2023, 2024],
                     tool=Tool.get_metric)
    assert [call.tool for call in calls] == [Tool.get_metric]


def test_unknown_company_is_clarified():
    clarifications, calls = route(company="MSFT", metric="revenue")
    assert calls == []
    assert [c.field for c in clarifications] == ["company"]


def test_unknown_metric_is_clarified_with_allowed_values():
    clarifications, calls = route(company="AAPL", metric="ebitda")
    assert calls == []
    assert clarifications[0].field == "metric"
    assert "net_income" in clarifications[0].reason


def test_empty_request_asks_for_a_metric_or_question():
    clarifications, calls = route(company="AAPL")
    assert calls == []
    assert clarifications[0].field == "question"


def test_compare_with_one_year_is_clarified():
    clarifications, calls = route(company="AAPL", metric="revenue",
                                  fiscal_years=[2024], tool=Tool.compare_periods)
    assert calls == []
    assert clarifications[0].field == "fiscal_years"


def test_more_than_two_years_is_clarified():
    clarifications, _ = route(company="AAPL", metric="revenue",
                              fiscal_years=[2022, 2023, 2024])
    assert clarifications[0].field == "fiscal_years"


def test_explicit_search_without_question_is_clarified():
    clarifications, calls = route(company="AAPL", tool=Tool.search_passages)
    assert calls == []
    assert clarifications[0].field == "question"


def test_request_model_rejects_structurally_invalid_input():
    with pytest.raises(ValidationError):
        QuestionRequest(company="")
    with pytest.raises(ValidationError):
        QuestionRequest(company="AAPL", fiscal_years=[1800])
    with pytest.raises(ValidationError):
        QuestionRequest(company="AAPL", limit=0)
