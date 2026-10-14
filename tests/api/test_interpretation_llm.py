"""Release v0.2 stage 2 (T010): LLM prompt interpretation.

Offline: the model is an injected fake, so no network or credential is used.
"""
import json

import pytest

from api.answering.client import ChatResult, LLMError
from api.interpretation import (
    MALFORMED,
    PROVIDER,
    Interpretation,
    InterpretationError,
    build_messages,
    interpret,
    interpret_and_validate,
)
from api.router import plan

METRICS = ["net_income", "operating_cash_flow", "revenue"]
CIKS = {"AAPL": 320193}


class FakeClient:
    model = "fake-model"

    def __init__(self, content="", refusal=None):
        self.content = content
        self.refusal = refusal
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        return ChatResult(self.content, self.model, prompt_tokens=10,
                          completion_tokens=5, refusal=self.refusal)


class FailingClient:
    model = "configured-model"

    def complete(self, messages):
        raise LLMError("endpoint down", model="returned-model")


def _reply(metric, years, clarifications=None):
    payload = {"metric": metric, "fiscal_years": list(years)}
    if clarifications is not None:
        payload["clarifications"] = clarifications
    return json.dumps(payload)


def _interpret(content, prompt="x"):
    return interpret(prompt, client=FakeClient(content), allowed_metrics=METRICS)


def test_interpret_extracts_metric_and_years():
    client = FakeClient(_reply("revenue", [2023, 2024]))
    result = interpret("what drove the revenue change between 2023 and 2024?",
                       client=client, allowed_metrics=METRICS)
    assert result.candidates.metric == "revenue"
    assert result.candidates.fiscal_years == (2023, 2024)
    assert result.candidates.company is None and result.candidates.operation is None
    assert result.clarifications == ()
    assert len(client.calls) == 1


def test_interpret_qualitative_prompt_has_no_metric():
    result = _interpret(_reply(None, []))
    assert result.candidates.metric is None
    assert result.candidates.fiscal_years == ()


def test_build_messages_lists_supported_metrics_and_the_prompt():
    messages = build_messages("why did revenue change?", METRICS)
    system, user = messages[0]["content"], messages[1]["content"]
    assert messages[0]["role"] == "system" and messages[1]["role"] == "user"
    assert all(metric in system for metric in METRICS)
    assert "strict json" in system.lower()
    assert "untrusted" in system.lower()
    assert user == "why did revenue change?"


def test_clear_typo_prompt_is_passed_through_verbatim():
    # The model resolves the typo; the original prompt must survive for retrieval.
    prompt = "wat drove revenue between 2023 and 2024?"
    client = FakeClient(_reply("revenue", [2023, 2024]))
    interpret(prompt, client=client, allowed_metrics=METRICS)
    assert client.calls[0][1]["content"] == prompt


def test_interpret_ignores_unknown_fields_and_never_emits_a_tool():
    content = json.dumps({
        "metric": "revenue", "fiscal_years": [2024],
        "tool": "get_metric", "sql": "drop table gold.annual_metrics",
    })
    result = _interpret(content)
    assert result.candidates.metric == "revenue"
    assert result.candidates.fiscal_years == (2024,)
    assert result.candidates.operation is None


def test_fenced_json_reply_is_accepted():
    content = "```json\n" + _reply("net_income", [2024]) + "\n```"
    assert _interpret(content).candidates.metric == "net_income"


@pytest.mark.parametrize("content", [
    "",                                                          # empty
    "not json at all",                                           # non-JSON
    json.dumps({"metric": "revenue"}),                           # missing years
    json.dumps({"fiscal_years": [2024]}),                        # missing metric
    json.dumps({"metric": 123, "fiscal_years": [2024]}),         # metric wrong type
    json.dumps({"metric": "revenue", "fiscal_years": "2024"}),   # years wrong type
    json.dumps({"metric": "revenue", "fiscal_years": [2023, "x"]}),
    json.dumps({"metric": "revenue", "fiscal_years": [True]}),
    json.dumps(["revenue", 2024]),                               # not an object
    json.dumps({"metric": "revenue", "fiscal_years": [2024],
                "clarifications": "nope"}),                      # clarifications not a list
    json.dumps({"metric": "revenue", "fiscal_years": [2024],
                "clarifications": [{"field": "fiscal_years"}]}),  # missing reason
    json.dumps({"metric": "revenue", "fiscal_years": [2024],
                "clarifications": [{"field": "", "reason": "x"}]}),  # blank field
])
def test_malformed_replies_raise_explicitly(content):
    with pytest.raises(InterpretationError) as excinfo:
        _interpret(content)
    assert excinfo.value.kind == MALFORMED


def test_deeply_nested_reply_uses_the_malformed_error_channel():
    # F053: json.loads raises RecursionError before the shape guards; it must be
    # converted to the documented malformed error, not escape as a server error.
    content = ('{"metric":"revenue","fiscal_years":[2024],"extra":'
               + "[" * 15000 + "0" + "]" * 15000 + "}")
    with pytest.raises(InterpretationError) as excinfo:
        _interpret(content)
    assert excinfo.value.kind == MALFORMED


def test_refusal_is_a_malformed_error():
    with pytest.raises(InterpretationError) as excinfo:
        interpret("x", client=FakeClient("", refusal="I cannot help."),
                  allowed_metrics=METRICS)
    assert excinfo.value.kind == MALFORMED


def test_provider_failure_maps_to_a_provider_error():
    with pytest.raises(InterpretationError) as excinfo:
        interpret("x", client=FailingClient(), allowed_metrics=METRICS)
    assert excinfo.value.kind == PROVIDER
    assert excinfo.value.model == "returned-model"
    assert isinstance(excinfo.value.__cause__, LLMError)


def test_build_messages_preserves_invalid_requests_for_the_server():
    # F052: the model must not silently truncate years or null an unsupported metric.
    system = build_messages("q", METRICS)[0]["content"]
    assert "at most two" not in system.lower()
    assert "every fiscal year" in system.lower()
    assert "even if it is not one of the supported metrics" in system.lower()


def test_build_messages_requests_clarification_for_unresolved_choices():
    system = build_messages("q", METRICS)[0]["content"]
    assert "clarifications" in system
    assert "not chosen between alternatives" in system


def test_model_declared_ambiguity_is_not_executed():
    # F051: an unresolved year choice must become a clarification, not a query.
    content = _reply("revenue", [], clarifications=[
        {"field": "fiscal_years", "reason": "Please choose 2023 or 2024."},
    ])
    result = interpret_and_validate(
        "What was revenue in 2023 or 2024? I am unsure which fiscal year.",
        client=FakeClient(content), company_ciks=CIKS, allowed_metrics=METRICS,
        selected=Interpretation(company="AAPL"),
    )
    assert result.request is None
    assert [(c.field, c.reason) for c in result.clarifications] == [
        ("fiscal_years", "Please choose 2023 or 2024."),
    ]


def test_unresolved_metric_ambiguity_is_honored_without_a_selection():
    content = _reply(None, [2024], clarifications=[
        {"field": "metric", "reason": "Revenue or net income?"},
    ])
    result = interpret_and_validate(
        "how did it change in 2024?", client=FakeClient(content),
        company_ciks=CIKS, allowed_metrics=METRICS,
        selected=Interpretation(company="AAPL"),
    )
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["metric"]


def test_explicit_selection_resolves_a_model_ambiguity():
    content = _reply("revenue", [2023, 2024], clarifications=[
        {"field": "fiscal_years", "reason": "Which year?"},
    ])
    result = interpret_and_validate(
        "compare revenue", client=FakeClient(content),
        company_ciks=CIKS, allowed_metrics=METRICS,
        selected=Interpretation(company="AAPL", fiscal_years=[2023, 2024]),
    )
    assert result.clarifications == []
    assert result.request is not None
    assert result.request.fiscal_years == [2023, 2024]


def test_explicit_metric_selection_resolves_a_model_ambiguity():
    content = _reply(None, [2024], clarifications=[
        {"field": "metric", "reason": "Revenue or net income?"},
    ])
    result = interpret_and_validate(
        "how did it change in 2024?", client=FakeClient(content),
        company_ciks=CIKS, allowed_metrics=METRICS,
        selected=Interpretation(company="AAPL", metric="net_income"),
    )
    assert result.clarifications == []
    assert result.request is not None
    assert result.request.metric == "net_income"


@pytest.mark.parametrize("blank", ["   ", "\t\n"])
def test_whitespace_only_metric_selection_does_not_resolve_ambiguity(blank):
    # F051 (continued): a blank selection is absent under T009's policy, so the
    # model's clarification must survive and no query may run.
    content = _reply("revenue", [2024], clarifications=[
        {"field": "metric", "reason": "Revenue or net income?"},
    ])
    result = interpret_and_validate(
        "how did it change in 2024?", client=FakeClient(content),
        company_ciks=CIKS, allowed_metrics=METRICS,
        selected=Interpretation(company="AAPL", metric=blank),
    )
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["metric"]


@pytest.mark.parametrize("blank", ["   ", "\t\n"])
def test_whitespace_only_year_selection_does_not_resolve_ambiguity(blank):
    content = _reply("revenue", [], clarifications=[
        {"field": "fiscal_years", "reason": "Please choose 2023 or 2024."},
    ])
    result = interpret_and_validate(
        "what was revenue in 2023 or 2024?", client=FakeClient(content),
        company_ciks=CIKS, allowed_metrics=METRICS,
        selected=Interpretation(company="AAPL", fiscal_years=blank),
    )
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["fiscal_years"]


@pytest.mark.parametrize("years", [None, "", []])
def test_absent_year_selection_does_not_resolve_ambiguity(years):
    content = _reply("revenue", [], clarifications=[
        {"field": "fiscal_years", "reason": "Please choose 2023 or 2024."},
    ])
    result = interpret_and_validate(
        "what was revenue in 2023 or 2024?", client=FakeClient(content),
        company_ciks=CIKS, allowed_metrics=METRICS,
        selected=Interpretation(company="AAPL", fiscal_years=years),
    )
    assert result.request is None
    assert [c.field for c in result.clarifications] == ["fiscal_years"]


def test_interpret_and_validate_applies_selection_precedence():
    result = interpret_and_validate(
        "why did revenue change?",
        client=FakeClient(_reply("revenue", [2024])),
        company_ciks=CIKS, allowed_metrics=METRICS,
        selected=Interpretation(company="AAPL", metric="net_income"),
    )
    assert result.clarifications == []
    assert result.request is not None
    assert result.request.company == "AAPL"
    assert result.request.metric == "net_income"
    assert result.request.question == "why did revenue change?"


def test_interpret_and_validate_leaves_tool_unset_and_runs_both_tools():
    result = interpret_and_validate(
        "why did revenue change in 2024?",
        client=FakeClient(_reply("revenue", [2024])),
        company_ciks=CIKS, allowed_metrics=METRICS,
        selected=Interpretation(company="AAPL"),
    )
    assert result.request is not None
    assert result.request.tool is None
    clarifications, calls = plan(result.request, company_ciks=CIKS,
                                 allowed_metrics=METRICS)
    assert clarifications == []
    assert {call.tool.value for call in calls} == {"get_metric", "search_passages"}


def test_interpret_and_validate_qualitative_prompt_is_valid():
    result = interpret_and_validate(
        "what risks are described?",
        client=FakeClient(_reply(None, [])),
        company_ciks=CIKS, allowed_metrics=METRICS,
        selected=Interpretation(company="AAPL"),
    )
    assert result.clarifications == []
    assert result.request is not None
    assert result.request.metric is None
    assert result.request.question == "what risks are described?"


@pytest.mark.parametrize("content,field", [
    (_reply("ebitda", [2024]), "metric"),
    (_reply("revenue", [1800]), "fiscal_years"),
    (_reply("revenue", [2022, 2023, 2024]), "fiscal_years"),
])
def test_wellformed_but_invalid_values_become_clarifications(content, field):
    result = interpret_and_validate(
        "q", client=FakeClient(content),
        company_ciks=CIKS, allowed_metrics=METRICS,
        selected=Interpretation(company="AAPL"),
    )
    assert result.request is None
    assert [c.field for c in result.clarifications] == [field]


def test_interpret_and_validate_propagates_interpretation_error():
    with pytest.raises(InterpretationError):
        interpret_and_validate(
            "q", client=FailingClient(),
            company_ciks=CIKS, allowed_metrics=METRICS,
            selected=Interpretation(company="AAPL"),
        )
