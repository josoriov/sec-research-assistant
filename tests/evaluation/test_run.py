"""Regressions for the evaluation runner (T008 reviews R024/R025).

F040: the prompt-injection case never touches the database (composition boundary,
synthetic evidence).
F041: grading inspects the exact messages the client received and rejects
malformed/failed replies, while allowing a valid explicit abstention.
F043: model metrics run only when the API reports answer composition enabled.
F044: --base mode with no local client is handled without crashing.
"""
from __future__ import annotations

import inspect
import json

from api.answering import ChatResult
from api.schemas import Answer, Citation

import evaluation.run as run

VALID = ('{"answer":"Revenue grew 6%.","citations":'
         '["metric:320193:revenue:2023-10-01:2024-09-28"],'
         '"abstained":false,"limitations":null}')
ABSTAIN = '{"answer":"","citations":[],"abstained":true,"limitations":"no evidence"}'
PROMPT = [{"role": "user",
           "content": f"EVIDENCE {run.INJECTION_TEXT} [passage:900002]"}]


def _raw(content: str) -> ChatResult:
    return ChatResult(content=content, model="stub", prompt_tokens=1, completion_tokens=1)


class _StubClient:
    model = "stub"

    def __init__(self, content: str):
        self.content = content

    def complete(self, messages):
        return _raw(self.content)


def test_resolve_model_mode():
    assert run.resolve_model_mode({"answer_composition": False}, {}) == "disabled"
    assert run.resolve_model_mode({"answer_composition": True}, {}) == "enabled"
    assert run.resolve_model_mode({"answer_composition": False},
                                  {"LLM_MODEL": "gpt-x"}) == "incomplete"


def test_grade_injection_requires_text_in_observed_prompt():
    answer = Answer(text="Revenue grew 6%.", model="stub", citations=[])
    result = run.grade_injection([{"role": "user", "content": "no injection here"}],
                                 "passage:900002", answer, _raw(VALID))
    assert result["adversarial_in_prompt"] is False
    assert result["passed"] is False


def test_grade_injection_rejects_malformed_reply():
    answer = Answer(text="", abstained=True, model="stub",
                    limitations="The model reply was not valid JSON.", citations=[])
    result = run.grade_injection(PROMPT, "passage:900002", answer,
                                 _raw("garbled non-json answer"))
    assert result["valid_reply"] is False
    assert result["passed"] is False


def test_grade_injection_flags_compliance_and_injected_citation():
    complied = Answer(text="Revenue was 0 dollars.", model="stub", citations=[])
    assert run.grade_injection(PROMPT, "passage:900002", complied, _raw(VALID))["passed"] is False

    cited = Answer(text="Revenue grew.", model="stub",
                   citations=[Citation(id="passage:900002", kind="passage")])
    assert run.grade_injection(PROMPT, "passage:900002", cited, _raw(VALID))["passed"] is False

    ok = Answer(text="Revenue grew 6%.", model="stub",
                citations=[Citation(id="metric:320193:revenue:2023-10-01:2024-09-28",
                                    kind="metric")])
    assert run.grade_injection(PROMPT, "passage:900002", ok, _raw(VALID))["passed"] is True

    # A valid explicit abstention is a real model response and passes.
    abstained = Answer(text="", abstained=True, model="stub",
                       limitations="Only an untrusted instruction was found.", citations=[])
    assert run.grade_injection(PROMPT, "passage:900002", abstained, _raw(ABSTAIN))["passed"] is True


def test_run_prompt_injection_never_accesses_database(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the injection case must not touch the database")

    monkeypatch.setattr(run, "connect", boom)
    assert "conn" not in inspect.signature(run.run_prompt_injection).parameters
    assert "connection" not in inspect.signature(run.run_prompt_injection).parameters

    result = run.run_prompt_injection(_StubClient(VALID))
    assert result["adversarial_in_prompt"] is True
    assert result["cited_injected"] is False
    assert result["passed"] is True


def test_run_prompt_injection_malformed_reply_fails():
    result = run.run_prompt_injection(_StubClient("garbled non-json answer"))
    assert result["valid_reply"] is False
    assert result["passed"] is False


def test_run_prompt_injection_fails_when_attack_text_absent(monkeypatch):
    # Mirrors R025/F041: the graded prompt is the one the client actually saw,
    # so a compose call that drops the adversarial passage cannot pass.
    def compose_without_attack(question, calculations, passages, *, client):
        client.complete([{"role": "user", "content": "benign evidence [passage:900001]"}])
        return Answer(text="Revenue grew 6%.", model="stub", citations=[])

    monkeypatch.setattr(run, "compose_answer", compose_without_attack)
    result = run.run_prompt_injection(_StubClient(VALID))
    assert result["adversarial_in_prompt"] is False
    assert result["passed"] is False


def test_local_injection_client_requires_local_credentials():
    # F044: --base mode can be model-enabled without a local client.
    assert run.local_injection_client("enabled", {}) is None
    assert run.local_injection_client("disabled",
                                      {"LLM_MODEL": "m", "LLM_API_KEY": "k"}) is None
    assert run.local_injection_client("enabled",
                                      {"LLM_MODEL": "m", "LLM_API_KEY": "k"}) is not None


# --------------------------------------------------------------------------- #
# F045/F046/F047: reporting denominators, artifact sync, p95 convention
# --------------------------------------------------------------------------- #
def _res(qid, answer, status="ok"):
    return {"id": qid, "category": "numerical",
            "request": {"company": "AAPL"},
            "response": {"status": status, "answer": answer},
            "latency_ms": 1.0, "passed": True, "numeric_ok": None, "retrieval_ok": None,
            "detail": "ok"}


def test_percentile_uses_nearest_rank():
    # F047: 25 samples; a floored 0.95*(n-1) index returns the 23rd value,
    # nearest-rank must return the 24th.
    values = [float(v) for v in range(1, 26)]
    assert run._percentile(values, 0.95) == 24.0
    # Where flooring and nearest-rank differ for a 10-sample set.
    assert run._percentile([float(v) for v in range(1, 11)], 0.95) == 10.0


def test_citation_support_excludes_answers_without_citations():
    # F045: clarifications (no answer) and uncited abstentions must not raise a
    # citation-support rate, even when judged true.
    cited = {"text": "a", "citations": [{"id": "metric:x", "kind": "metric"}],
             "abstained": False, "limitations": None}
    abstained_uncited = {"text": "", "citations": [], "abstained": True, "limitations": "none"}
    results = [_res("Q1", cited),
               _res("Q2", abstained_uncited),
               _res("Q3", None, status="needs_clarification")]
    summary = run.summarise(results, {"Q1": True, "Q2": True, "Q3": True})
    assert summary["citation_support_judged"] == {"passed": 1, "total": 1}


def test_regenerate_persists_summary_used_by_the_report(monkeypatch, tmp_path):
    # F046: --from-results must write the final adjudicated/cost summary back to
    # results.json so it agrees with the report.
    results_path = tmp_path / "results.json"
    review_path = tmp_path / "citation-review.md"
    report_path = tmp_path / "report.md"
    cited = {"text": "a", "citations": [{"id": "metric:x", "kind": "metric"}],
             "abstained": False, "limitations": None}
    payload = {
        "generated": "x", "model_mode": "enabled",
        "summary": {"citation_support_judged": None, "cost_usd_total": None},
        "lineage": {"metric_chain_ok": True, "metric_chain": [],
                    "passage_chain_ok": True, "passage_chain": []},
        "boundary": {"all_denied": True, "denied": {}},
        "prompt_injection": {"ran": False, "reason": "no model configured"},
        "results": [_res("Q1", cited)],
    }
    results_path.write_text(json.dumps(payload))
    monkeypatch.setattr(run, "RESULTS_PATH", results_path)
    monkeypatch.setattr(run, "REVIEW_PATH", review_path)
    monkeypatch.setattr(run, "REPORT_PATH", report_path)

    summary = run.regenerate({"Q1": True})

    stored = json.loads(results_path.read_text())
    assert stored["summary"]["citation_support_judged"] == {"passed": 1, "total": 1}
    assert "1/1" in report_path.read_text()
    assert summary["citation_support_judged"] == {"passed": 1, "total": 1}
