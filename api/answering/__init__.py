"""Cited answer composition over published gold evidence (task T006).

`compose_answer` builds a prompt with stable source ids and returns a cited
answer; `answer_question_with_citations` runs the T005 tools and attaches the
answer. The model is an OpenAI-compatible endpoint configured through the
environment (see docs/setup.md §9).
"""
from api.answering.client import (
    ChatResult, LLMError, OpenAIChatClient, client_from_env,
)
from api.answering.compose import (
    answer_question_with_citations, compose_answer, configure_logging,
)

__all__ = [
    "ChatResult", "LLMError", "OpenAIChatClient", "client_from_env",
    "answer_question_with_citations", "compose_answer", "configure_logging",
]
