"""Approved tools for the questions API: get_metric, compare_periods, search.

Each tool is a plain function taking an injected connection, so the endpoint and
the tests use the same code. Only parameterized SQL against published gold runs
here; there is no model-generated SQL.
"""
from __future__ import annotations

from api.tools import financials
from api.tools.financials import list_metrics

__all__ = ["financials", "list_metrics"]
