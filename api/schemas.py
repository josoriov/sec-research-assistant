"""Request/response models for POST /answer and POST /ask.

Pydantic validates the shape of the request (types, ranges, enum values) before
any tool runs; the router then resolves company/metric/period and either returns
`needs_clarification` or an evidence package. `POST /ask` (release v0.2) accepts
a natural-language prompt plus explicit selections and returns that same package
with the interpreted request and, on failure, an `error` status.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# Fiscal years are bounded far enough to reject typos while accepting any real
# SEC annual period.
FiscalYear = Annotated[int, Field(ge=1900, le=2100)]


class Tool(str, Enum):
    """The approved tool set. There are no others."""

    get_metric = "get_metric"
    compare_periods = "compare_periods"
    search_passages = "search_passages"


class QuestionRequest(BaseModel):
    company: str = Field(min_length=1, description="Ticker (e.g. AAPL) or numeric CIK")
    metric: str | None = Field(
        default=None, description="revenue | net_income | operating_cash_flow"
    )
    fiscal_years: list[FiscalYear] = Field(
        default_factory=list,
        description="Fiscal years: one for a value, two to compare (earlier is the base)",
    )
    question: str | None = Field(
        default=None, min_length=1, description="Free text used for passage retrieval"
    )
    tool: Tool | None = Field(
        default=None, description="Explicit tool; inferred deterministically when omitted"
    )
    limit: int = Field(default=5, ge=1, le=20, description="Max passages to return")
    include_superseded: bool = Field(
        default=False, description="Include passages from superseded filings"
    )


class Clarification(BaseModel):
    field: str
    reason: str


class Citation(BaseModel):
    """A citation resolved to application-supplied metadata/URL."""

    id: str
    kind: str
    url: str | None = None
    accession: str | None = None
    section: str | None = None
    label: str | None = None


class Answer(BaseModel):
    """A composed, cited answer (task T006)."""

    text: str
    citations: list[Citation] = Field(default_factory=list)
    abstained: bool = False
    limitations: str | None = None
    model: str | None = None
    usage: dict | None = None
    latency_ms: int | None = None
    cost_usd: float | None = None


class NeedsClarification(Exception):
    """Raised by a tool when executing it needs an unambiguous input first.

    `answer_question` converts it into the standard `needs_clarification`
    response, so the endpoint never guesses between candidate periods.
    """

    def __init__(self, field: str, reason: str):
        super().__init__(reason)
        self.field = field
        self.reason = reason


class QuestionResponse(BaseModel):
    status: Literal["ok", "needs_clarification"]
    clarifications: list[Clarification] = Field(default_factory=list)
    calculations: list[dict] = Field(default_factory=list)
    passages: list[dict] = Field(default_factory=list)
    # Composed cited answer (task T006); omitted from the response when no model
    # is configured (H008), via response_model_exclude_unset at the route.
    answer: Answer | None = None


class AskRequest(BaseModel):
    """POST /ask: a natural-language question with explicit selections (T011).

    The company is required (the user picks one); the metric is optional and,
    when given, takes precedence over the interpreted metric. Fiscal years are
    not selected here — the interpreter extracts them from the prompt.
    """

    company: str = Field(min_length=1, description="Ticker (e.g. AAPL) or numeric CIK")
    metric: str | None = Field(
        default=None, description="Optional explicit metric; overrides interpretation"
    )
    question: str = Field(min_length=1, description="Natural-language question")


class AskResponse(BaseModel):
    """POST /ask: the endpoint response plus how the prompt was understood.

    Carries the complete evidence/answer package so nothing is lost for display,
    the validated `request` the prompt was mapped to, and `error` when
    interpretation failed (a provider or malformed-reply failure, distinct from a
    user-correctable clarification). Defined separately from `QuestionResponse`
    because its `status` deliberately adds an `error` state (`/answer` never
    returns it).
    """

    status: Literal["ok", "needs_clarification", "error"]
    clarifications: list[Clarification] = Field(default_factory=list)
    calculations: list[dict] = Field(default_factory=list)
    passages: list[dict] = Field(default_factory=list)
    answer: Answer | None = None
    request: QuestionRequest | None = None
    error: str | None = None
