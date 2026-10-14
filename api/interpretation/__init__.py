"""Validate interpreted fields against the existing request contract.

Release v0.2 stage 1 (task T009) reuses QuestionRequest and the existing routing
rules. Later stages add LLM interpretation and endpoint orchestration.
"""
from __future__ import annotations

from api.interpretation.contract import (
    Interpretation,
    ValidationResult,
    validate_interpretation,
)

__all__ = ["Interpretation", "ValidationResult", "validate_interpretation"]
