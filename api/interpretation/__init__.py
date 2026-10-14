"""Server-side interpretation of questions into the existing request contract.

Release v0.2 stage 1 (task T009): validate interpreted fields against
`QuestionRequest` and the T005 routing rules before any query. Stage 2 (task
T010) adds the LLM interpreter; stage 3 wires this into `POST /ask`.
"""
from __future__ import annotations

from api.interpretation.contract import (
    Interpretation,
    ValidationResult,
    validate_interpretation,
)
from api.interpretation.interpreter import (
    MALFORMED,
    PROVIDER,
    InterpretationError,
    InterpretationResult,
    build_messages,
    interpret,
    interpret_and_validate,
    parse_interpretation,
)

__all__ = [
    "MALFORMED",
    "PROVIDER",
    "Interpretation",
    "InterpretationError",
    "InterpretationResult",
    "ValidationResult",
    "build_messages",
    "interpret",
    "interpret_and_validate",
    "parse_interpretation",
    "validate_interpretation",
]
