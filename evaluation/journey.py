"""End-to-end journey check for the question UI (task T014).

Drives the browser-facing route — the web app's same-origin ``/api/ask`` proxy —
with real prompts and asserts the journey criteria: a comparison question's
metric/years/figures/sources, a qualitative question with no calculation, a
tolerated typo, an ambiguous prompt that needs clarification, and an explicit
metric selection that overrides the model's inference.

Requires the Compose stack up and the LLM configured (``.env``). It never
fabricates a result: a missing web/API/model is reported as an error and the
script exits non-zero.

Usage:
    WEB_BASE=http://127.0.0.1:18001 python evaluation/journey.py [--json PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def ask(base: str, *, company: str, question: str, metric: str | None = None,
        timeout: int = 180) -> dict:
    payload = {"company": company, "question": question}
    if metric:
        payload["metric"] = metric
    request = urllib.request.Request(
        f"{base.rstrip('/')}/api/ask",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{base}/api/ask returned HTTP {exc.code}: {exc.read()[:300]!r}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"cannot reach {base}/api/ask: {exc}")


def check(name: str, condition: bool, detail: str = "") -> dict:
    status = "pass" if condition else "fail"
    line = f"[{status}] {name}" + (f" — {detail}" if detail else "")
    print(line)
    return {"check": name, "status": status, "detail": detail}


def calc_tools(response: dict) -> list[str]:
    return [calc.get("tool") for calc in response.get("calculations", [])]


def run(base: str) -> tuple[list[dict], dict[str, dict]]:
    results: list[dict] = []
    responses: dict[str, dict] = {}

    def record(name: str, response: dict) -> dict:
        responses[name] = response
        return response

    # 1. Comparison question: expected metric, years, comparison figures, sources.
    comparison = record("comparison", ask(base, company="AAPL",
                     question="What drove the revenue change between 2023 and 2024?"))
    request = comparison.get("request") or {}
    results.append(check("comparison: ok", comparison.get("status") == "ok", comparison.get("status", "")))
    results.append(check("comparison: metric inferred", request.get("metric") == "revenue",
                         str(request.get("metric"))))
    results.append(check("comparison: two fiscal years", sorted(request.get("fiscal_years") or []) == [2023, 2024],
                         str(request.get("fiscal_years"))))
    results.append(check("comparison: compare_periods ran", "compare_periods" in calc_tools(comparison),
                         str(calc_tools(comparison))))
    comparison_calc = next((c for c in comparison.get("calculations", [])
                            if c.get("tool") == "compare_periods"), {})
    results.append(check("comparison: figures present",
                         comparison_calc.get("value_a") is not None
                         and comparison_calc.get("value_b") is not None
                         and comparison_calc.get("change_absolute") is not None,
                         f"{comparison_calc.get('value_a')} -> {comparison_calc.get('value_b')}"))
    sources = [comparison_calc.get("source_a"), comparison_calc.get("source_b")]
    results.append(check("comparison: source accessions present",
                         all(s and s.get("accession") for s in sources),
                         str([s and s.get("accession") for s in sources])))
    answer = comparison.get("answer") or {}
    results.append(check("comparison: cited answer with text",
                         isinstance(answer.get("text"), str) and bool(answer["text"].strip())
                         and bool(answer.get("citations")),
                         f"citations={len(answer.get('citations') or [])}"))
    results.append(check("comparison: passages retrieved", bool(comparison.get("passages")),
                         f"passages={len(comparison.get('passages') or [])}"))

    # 2. Qualitative question: explanations without a financial calculation.
    qualitative = record("qualitative", ask(base, company="AAPL",
                      question="What does the latest 10-K say about supply chain and manufacturing risks?"))
    qual_request = qualitative.get("request") or {}
    results.append(check("qualitative: ok", qualitative.get("status") == "ok", qualitative.get("status", "")))
    results.append(check("qualitative: no financial calculation", not calc_tools(qualitative),
                         str(calc_tools(qualitative))))
    results.append(check("qualitative: passages retrieved", bool(qualitative.get("passages")),
                         f"passages={len(qualitative.get('passages') or [])}"))
    results.append(check("qualitative: metric left unset", not qual_request.get("metric"),
                         str(qual_request.get("metric"))))

    # 3. Clear typo is tolerated.
    typo = record("typo", ask(base, company="AAPL",
               question="Wht drove the revenu change betwen 2023 and 2024?"))
    typo_request = typo.get("request") or {}
    results.append(check("typo: ok", typo.get("status") == "ok", typo.get("status", "")))
    results.append(check("typo: metric inferred", typo_request.get("metric") == "revenue",
                         str(typo_request.get("metric"))))
    results.append(check("typo: years inferred", sorted(typo_request.get("fiscal_years") or []) == [2023, 2024],
                         str(typo_request.get("fiscal_years"))))

    # 4. Ambiguous prompt needs clarification.
    ambiguous = record("ambiguous", ask(base, company="AAPL", question="How is the company doing?"))
    results.append(check("ambiguous: needs_clarification", ambiguous.get("status") == "needs_clarification",
                         ambiguous.get("status", "")))
    results.append(check("ambiguous: clarifications listed", bool(ambiguous.get("clarifications")),
                         str(ambiguous.get("clarifications"))))

    # 5. Explicit metric selection overrides the prompt's inferred metric.
    precedence = record("precedence", ask(base, company="AAPL", metric="net_income",
                     question="How did revenue change between 2023 and 2024?"))
    precedence_request = precedence.get("request") or {}
    results.append(check("precedence: ok", precedence.get("status") == "ok", precedence.get("status", "")))
    results.append(check("precedence: explicit metric wins", precedence_request.get("metric") == "net_income",
                         str(precedence_request.get("metric"))))

    return results, responses


def main() -> int:
    parser = argparse.ArgumentParser(prog="python evaluation/journey.py")
    parser.add_argument("--base", default=os.environ.get("WEB_BASE", "http://127.0.0.1:18001"))
    parser.add_argument("--json", default=None, help="write the check results as JSON")
    parser.add_argument("--dump", default=None, help="directory for the raw responses")
    args = parser.parse_args()

    results, responses = run(args.base)
    if args.json:
        with open(args.json, "w") as handle:
            json.dump(results, handle, indent=2)
    if args.dump:
        os.makedirs(args.dump, exist_ok=True)
        for name, response in responses.items():
            with open(os.path.join(args.dump, f"{name}.json"), "w") as handle:
                json.dump(response, handle, indent=2)
    failed = [r for r in results if r["status"] == "fail"]
    print(f"\n{len(results) - len(failed)}/{len(results)} journey checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
