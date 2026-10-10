"""Read-only annual-metric queries against gold.annual_metrics.

The SQL lives in the repo's `sql/` directory and is executed with bound named
parameters, so user input never changes the statement text. Changes are computed
in SQL (see sql/compare_periods.sql). Zero denominators, missing periods,
multiple candidate periods, and ambiguous (restated/conflicting) inputs are all
reported explicitly rather than hidden.
"""
from __future__ import annotations

from pathlib import Path

from api.schemas import NeedsClarification

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"

_VALUE_COLUMNS = (
    "cik", "metric", "unit", "period_start", "period_end", "fiscal_year",
    "value", "is_ambiguous", "source_fact_id", "manifest_id", "accession",
    "form", "filed_date",
)


def _load(name: str) -> str:
    return (SQL_DIR / name).read_text()


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def list_metrics(conn) -> list[str]:
    """Supported metrics, from the gold mapping (the source of truth)."""
    rows = conn.execute(
        "select metric from gold.metric_concepts order by metric"
    ).fetchall()
    return [row[0] for row in rows]


def get_metric(conn, *, cik: int, metric: str, fiscal_years=None,
               unit: str = "USD") -> dict:
    """Annual values for one metric, optionally filtered to fiscal years."""
    years = sorted(set(fiscal_years)) if fiscal_years else None
    rows = conn.execute(
        _load("get_metric.sql"),
        {"cik": cik, "metric": metric, "unit": unit, "fiscal_years": years},
    ).fetchall()
    values = []
    for row in rows:
        item = dict(zip(_VALUE_COLUMNS, row))
        item["value"] = float(item["value"])
        item["period_start"] = _iso(item["period_start"])
        item["period_end"] = _iso(item["period_end"])
        item["filed_date"] = _iso(item["filed_date"])
        values.append(item)
    notes = []
    if years:
        found = {item["fiscal_year"] for item in values}
        notes = [
            f"no annual value for fiscal_year={year}"
            for year in years if year not in found
        ]
    notes.extend(
        f"fiscal_year={item['fiscal_year']} value is flagged ambiguous "
        "(restated or conflicting disclosures)"
        for item in values if item["is_ambiguous"]
    )
    return {
        "tool": "get_metric", "cik": cik, "metric": metric, "unit": unit,
        "values": values, "notes": notes,
    }


def _source(value, period_start, period_end, is_ambiguous, source_fact_id,
            manifest_id, accession, form, filed_date) -> dict | None:
    if value is None:
        return None
    return {
        "period_start": _iso(period_start), "period_end": _iso(period_end),
        "is_ambiguous": is_ambiguous, "source_fact_id": source_fact_id,
        "manifest_id": manifest_id, "accession": accession, "form": form,
        "filed_date": _iso(filed_date),
    }


def compare_periods(conn, *, cik: int, year_a: int, year_b: int,
                    metric: str, unit: str = "USD") -> dict:
    """Two annual values and their change (year_a is the base).

    Each side carries its selected gold source and ambiguity flag. If a
    requested year matches more than one eligible annual period, the caller must
    refine the period: raise `NeedsClarification` instead of guessing.
    """
    row = conn.execute(
        _load("compare_periods.sql"),
        {"cik": cik, "metric": metric, "unit": unit,
         "year_a": year_a, "year_b": year_b},
    ).fetchone()
    if row is None:  # defensive: the template always returns exactly one row
        row = (0, None, 0, None) + (None,) * 18 + (None, None)
    (count_a, periods_a, count_b, periods_b,
     value_a, ps_a, pe_a, amb_a, sfa, ma, acc_a, form_a, fd_a,
     value_b, ps_b, pe_b, amb_b, sfb, mb, acc_b, form_b, fd_b,
     change_absolute, change_percent) = row

    ambiguous = []
    if count_a > 1:
        ambiguous.append(f"fiscal_year={year_a} ({periods_a})")
    if count_b > 1:
        ambiguous.append(f"fiscal_year={year_b} ({periods_b})")
    if ambiguous:
        raise NeedsClarification(
            "fiscal_years",
            "multiple annual periods match " + "; ".join(ambiguous)
            + "; specify a single period per year",
        )

    notes = []
    if count_a == 0:
        notes.append(f"no annual value for fiscal_year={year_a}")
    if count_b == 0:
        notes.append(f"no annual value for fiscal_year={year_b}")
    if count_a == 1 and amb_a:
        notes.append(f"fiscal_year={year_a} input is flagged ambiguous "
                     "(restated or conflicting disclosures)")
    if count_b == 1 and amb_b:
        notes.append(f"fiscal_year={year_b} input is flagged ambiguous "
                     "(restated or conflicting disclosures)")
    if value_a == 0:
        notes.append("base value is zero; percent change is undefined")
    return {
        "tool": "compare_periods", "cik": cik, "metric": metric, "unit": unit,
        "year_a": year_a, "year_b": year_b,
        "value_a": _number(value_a), "value_b": _number(value_b),
        "source_a": _source(value_a, ps_a, pe_a, amb_a, sfa, ma, acc_a, form_a, fd_a),
        "source_b": _source(value_b, ps_b, pe_b, amb_b, sfb, mb, acc_b, form_b, fd_b),
        "change_absolute": _number(change_absolute),
        "change_percent": _number(change_percent),
        "notes": notes,
    }


def _number(value):
    return None if value is None else float(value)
