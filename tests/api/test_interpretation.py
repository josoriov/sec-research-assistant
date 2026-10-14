"""Release v0.2 stage 1: interpreted-request validation (pure logic).

No database or model is touched: the supported-metric catalog and company
mapping are injected, matching how stage 3 will supply them from gold.
"""
import pytest

from api.interpretation import Interpretation, validate_interpretation

CIKS = {"AAPL": 320193}
METRICS = ["net_income", "operating_cash_flow", "revenue"]


def validate(**kwargs):
    kwargs.setdefault("company_ciks", CIKS)
    kwargs.setdefault("allowed_metrics", METRICS)
    kwargs.setdefault("question", None)
    return validate_interpretation(**kwargs)


def test_valid_comparison_builds_the_existing_payload():
    result = validate(
        selected=Interpretation(company="AAPL"),
        interpreted=Interpretation(metric="revenue", fiscal_years=[2023, 2024]),
        question="what drove the revenue change between 2023 and 2024?",
    )
    assert result.clarifications == []
    assert result.request is not None
    assert result.request.company == "AAPL"
    assert result.request.metric == "revenue"
    assert result.request.fiscal_years == [2023, 2024]
    assert result.request.question == "what drove the revenue change between 2023 and 2024?"


def test_qualitative_question_needs_no_metric():
    result = validate(
        selected=Interpretation(company="AAPL"),
        question="what supply chain risks are described?",
    )
    assert result.clarifications == []
    assert result.request is not None
    assert result.request.metric is None


def test_explicit_metric_overrides_interpreted_metric():
    result = validate(
        selected=Interpretation(company="AAPL", metric="net_income"),
        interpreted=Interpretation(metric="revenue", fiscal_years=[2024]),
    )
    assert result.request is not None
    assert result.request.metric == "net_income"


def test_explicit_company_overrides_interpreted_company():
    result = validate(
        selected=Interpretation(company="AAPL"),
        interpreted=Interpretation(company="MSFT", metric="revenue"),
    )
    assert result.request is not None
    assert result.request.company == "AAPL"


def test_unsupported_metric_is_clarified():
    result = validate(selected=Interpretation(company="AAPL", metric="ebitda"))
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["metric"]
    assert "net_income" in result.clarifications[0].reason


def test_unsupported_operation_is_clarified():
    result = validate(
        selected=Interpretation(company="AAPL", metric="revenue"),
        interpreted=Interpretation(operation="drop_table"),
    )
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["tool"]


def test_out_of_range_year_is_clarified():
    result = validate(
        selected=Interpretation(company="AAPL", metric="revenue"),
        interpreted=Interpretation(fiscal_years=[1800]),
    )
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["fiscal_years"]


def test_non_numeric_year_is_clarified():
    result = validate(
        selected=Interpretation(company="AAPL", metric="revenue"),
        interpreted=Interpretation(fiscal_years=["twenty twenty four"]),
    )
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["fiscal_years"]


@pytest.mark.parametrize("years", [0, False, "", {}])
def test_malformed_falsey_years_are_clarified(years):
    # F048: a falsey malformed candidate must not become an empty (unfiltered)
    # year list; it reaches Pydantic and becomes a clarification.
    result = validate(
        selected=Interpretation(company="AAPL", metric="revenue"),
        interpreted=Interpretation(fiscal_years=years),
    )
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["fiscal_years"]


@pytest.mark.parametrize("prompt", [42, ["hello"]])
def test_non_string_prompt_is_clarified(prompt):
    # F048: non-string prompts must not crash or be silently discarded.
    result = validate(selected=Interpretation(company="AAPL", metric="revenue"),
                      question=prompt)
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["question"]


def test_more_than_two_years_is_clarified():
    result = validate(
        selected=Interpretation(company="AAPL", metric="revenue"),
        interpreted=Interpretation(fiscal_years=[2022, 2023, 2024]),
    )
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["fiscal_years"]


def test_missing_metric_and_question_is_clarified():
    result = validate(selected=Interpretation(company="AAPL"))
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["question"]


def test_missing_company_is_clarified():
    result = validate(interpreted=Interpretation(metric="revenue", fiscal_years=[2024]))
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["company"]


def test_unknown_company_is_clarified():
    result = validate(selected=Interpretation(company="ZZZZ", metric="revenue"))
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["company"]


def test_blank_prompt_keeps_a_metric_only_request_valid():
    result = validate(
        selected=Interpretation(company="AAPL", metric="revenue"), question="   "
    )
    assert result.clarifications == []
    assert result.request is not None
    assert result.request.question is None


def test_conflicting_selections_are_reported_together():
    result = validate(selected=Interpretation(company="ZZZZ", metric="ebitda"))
    assert result.request is None
    assert sorted(c.field for c in result.clarifications) == ["company", "metric"]
