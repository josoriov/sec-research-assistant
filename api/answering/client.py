"""Language-model access for cited answer composition (task T006).

A minimal OpenAI-compatible client built on the standard library, so the project
adds no dependency. It talks to any `/chat/completions` endpoint (OpenAI, Azure,
a local Ollama/vLLM/LM Studio). The API key is read from the environment and is
only ever placed in the request header, never logged. Redirects are refused so
the bearer token cannot be replayed to another origin.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import NoReturn

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class LLMError(RuntimeError):
    """The model endpoint could not be reached or returned an unusable response.

    Carries any safe metadata already parsed from the attempt (model and token
    usage) so the failure can still be attributed and accounted for.
    """

    def __init__(self, message, *, model=None, prompt_tokens=None,
                 completion_tokens=None):
        super().__init__(message)
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so Authorization never crosses to another origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            req.full_url, code, f"refusing redirect to {newurl}", headers, fp
        )


_opener = urllib.request.build_opener(_NoRedirect())


def _open(request, timeout=None):
    # Indirection so tests can replace it without any network access.
    return _opener.open(request, timeout=timeout)


@dataclass(frozen=True)
class ChatResult:
    content: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    refusal: str | None = None


def _as_token(value) -> int | None:
    # bool is an int subclass; treat only real ints as token counts.
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class OpenAIChatClient:
    """One `/chat/completions` request per call; no SDK, no streaming."""

    def __init__(self, base_url: str, api_key: str | None, model: str,
                 timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(self, messages: list[dict]) -> ChatResult:
        body = json.dumps(
            {"model": self.model, "messages": messages, "temperature": 0}
        ).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + "/chat/completions", data=body, method="POST"
        )
        request.add_header("Content-Type", "application/json")
        if self.api_key:
            request.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with _open(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            # The configured model is known even when no payload arrived.
            raise LLMError(f"chat completion request failed: {exc}",
                           model=self.model) from exc
        return self._parse_envelope(payload)

    def _parse_envelope(self, payload) -> ChatResult:
        if not isinstance(payload, dict):
            raise LLMError("malformed chat completion response", model=self.model)
        # Extract safe metadata first so a rejected envelope is still attributable.
        model = payload.get("model")
        if not isinstance(model, str):
            model = self.model
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        prompt_tokens = _as_token(usage.get("prompt_tokens"))
        completion_tokens = _as_token(usage.get("completion_tokens"))

        def fail(message) -> NoReturn:
            raise LLMError(message, model=model, prompt_tokens=prompt_tokens,
                           completion_tokens=completion_tokens)

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            fail("chat completion response has no choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            fail("chat completion response has no message")
        content = message.get("content")
        refusal = message.get("refusal")
        if content is None and not isinstance(refusal, str):
            fail("chat completion response has no content")
        if content is not None and not isinstance(content, str):
            fail("chat completion content is not text")
        return ChatResult(
            content=content or "",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            refusal=refusal if isinstance(refusal, str) else None,
        )


def client_from_env(env=None) -> OpenAIChatClient | None:
    """Build a client from the environment, or None when no model is configured.

    Enabled when `LLM_MODEL` is set together with either `LLM_API_KEY` (hosted)
    or an explicit `LLM_BASE_URL` (e.g. a local server that needs no key).
    """
    env = os.environ if env is None else env
    model = env.get("LLM_MODEL")
    if not model:
        return None
    base_url = env.get("LLM_BASE_URL")
    api_key = env.get("LLM_API_KEY")
    if not base_url and not api_key:
        return None
    return OpenAIChatClient(
        base_url=base_url or DEFAULT_BASE_URL,
        api_key=api_key,
        model=model,
        timeout=float(env.get("LLM_TIMEOUT", "30")),
    )
