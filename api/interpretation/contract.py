"""Validate interpreted question fields against the existing request contract.

Release v0.2 stage 1 (task T009): an interpreter (stage 2) or the user's explicit
selections propose a company, metric, fiscal years, and an optional operation.
This module merges the explicit selections over the interpreted candidates,
builds the existing `api.schemas.QuestionRequest`, and applies Pydantic plus the
T005 routing rules (`api.router.plan`). Unsupported metrics or operations,
out-of-range or excessive years, and missing fields become `Clarification`
messages. Nothing is guessed and no tool or model runs here.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from pydantic import ValidationError

from api.router import plan
from api.schemas import Clarification, QuestionRequest


@dataclass(frozen=True)
class Interpretation:
    """Unvalidated candidate fields.

    The user's explicit choices (`selected`) and stage 2's model output
    (`interpreted`) share this shape. Values are deliberately untyped candidates:
    malformed input is passed through to Pydantic for validation rather than
    coerced here, and explicit values win field by field during the merge.
    """

    company: object | None = None
    metric: object | None = None
    fiscal_years: object = field(default_factory=tuple)
    operation: object | None = None


@dataclass(frozen=True)
class ValidationResult:
    """A validated, executable request, or the clarifications that block it.

    `request` is None whenever `clarifications` is non-empty, so a partially
    resolved request is never executed by mistake (mirrors `router.plan`).
    """

    request: QuestionRequest | None
    clarifications: list[Clarification]


def _prefer(explicit: object, inferred: object) -> object:
    """Explicit selection wins; an absent/blank/empty selection falls back.

    Only an intentional absence (`None`) or an empty list/tuple/blank string
    falls back. Any other value — including malformed scalars and containers —
    is preserved so Pydantic can reject it.
    """
    if explicit is None:
        return inferred
    if isinstance(explicit, str):
        return inferred if not explicit.strip() else explicit
    if isinstance(explicit, (list, tuple)) and not explicit:
        return inferred
    return explicit


def _prompt(value: object) -> object:
    """Treat a blank string prompt as absent; pass anything else to Pydantic."""
    if isinstance(value, str):
        return value if value.strip() else None
    return value


def _clarifications_from(exc: ValidationError) -> list[Clarification]:
    reasons: dict[str, str] = {}
    for error in exc.errors():
        loc = error.get("loc") or ()
        name = str(loc[0]) if loc else "request"
        reasons.setdefault(name, error.get("msg", "invalid value"))
    return [Clarification(field=name, reason=reason) for name, reason in reasons.items()]


def validate_interpretation(
    *,
    question: object,
    company_ciks: Mapping[str, int],
    allowed_metrics: Sequence[str],
    selected: Interpretation | None = None,
    interpreted: Interpretation | None = None,
    limit: int = 5,
    include_superseded: bool = False,
) -> ValidationResult:
    """Merge, validate, and route interpreted fields; never guess.

    The original prompt is preserved in `question` for passage retrieval and
    answer composition; a blank string prompt is treated as absent so a
    metric-only request stays valid.
    """
    selected = selected or Interpretation()
    interpreted = interpreted or Interpretation()

    candidate: dict[str, object] = {
        "company": _prefer(selected.company, interpreted.company),
        "metric": _prefer(selected.metric, interpreted.metric),
        "question": _prompt(question),
        "tool": _prefer(selected.operation, interpreted.operation),
        "limit": limit,
        "include_superseded": include_superseded,
    }
    years = _prefer(selected.fiscal_years, interpreted.fiscal_years)
    if years is not None:
        candidate["fiscal_years"] = years

    try:
        request = QuestionRequest.model_validate(candidate)
    except ValidationError as exc:
        return ValidationResult(request=None, clarifications=_clarifications_from(exc))

    clarifications, _ = plan(
        request, company_ciks=company_ciks, allowed_metrics=allowed_metrics
    )
    if clarifications:
        return ValidationResult(request=None, clarifications=clarifications)
    return ValidationResult(request=request, clarifications=[])
