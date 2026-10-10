"""OpenAI-compatible client: env configuration, request shape, error mapping,
redirect safety, and envelope validation.

No external network: the module-level opener is replaced with a stub, except the
redirect regression, which uses two loopback servers.
"""
import http.server
import json
import threading
import urllib.error

import pytest

from api.answering import client as client_mod
from api.answering.client import LLMError, OpenAIChatClient, client_from_env


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def test_client_from_env_is_none_without_a_model_or_endpoint():
    assert client_from_env({}) is None
    assert client_from_env({"LLM_MODEL": "gpt-4o-mini"}) is None  # no key, no base url


def test_client_from_env_uses_default_openai_base_url_with_key():
    client = client_from_env({"LLM_MODEL": "gpt-4o-mini", "LLM_API_KEY": "sk-test"})
    assert client.base_url == "https://api.openai.com/v1"
    assert client.api_key == "sk-test"
    assert client.model == "gpt-4o-mini"


def test_client_from_env_allows_a_local_server_without_a_key():
    client = client_from_env(
        {"LLM_MODEL": "llama3", "LLM_BASE_URL": "http://localhost:11434/v1"}
    )
    assert client.base_url == "http://localhost:11434/v1"
    assert client.api_key is None


def test_complete_posts_messages_and_reads_usage(monkeypatch):
    captured = {}

    def fake_open(request, timeout=None):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({
            "model": "gpt-test",
            "choices": [{"message": {"content": "{\"answer\":\"ok\"}"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 4},
        })

    monkeypatch.setattr(client_mod, "_open", fake_open)
    client = OpenAIChatClient("https://api.openai.com/v1/", "sk-secret", "gpt-test")
    result = client.complete([{"role": "user", "content": "hi"}])

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-secret"
    assert captured["body"]["model"] == "gpt-test"
    assert captured["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert result.content == "{\"answer\":\"ok\"}"
    assert result.prompt_tokens == 11 and result.completion_tokens == 4


def test_complete_maps_transport_and_shape_errors_to_llm_error(monkeypatch):
    def unreachable(request, timeout=None):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(client_mod, "_open", unreachable)
    with pytest.raises(LLMError):
        OpenAIChatClient("http://x/v1", None, "m").complete([])

    monkeypatch.setattr(client_mod, "_open",
                        lambda request, timeout=None: FakeResponse({"nope": 1}))
    with pytest.raises(LLMError):
        OpenAIChatClient("http://x/v1", None, "m").complete([])


def _payload(content=None, refusal=None, usage=None, choices=True):
    message = {"content": content}
    if refusal is not None:
        message["refusal"] = refusal
    payload = {"model": "m", "usage": usage or {"prompt_tokens": 1, "completion_tokens": 2}}
    if choices:
        payload["choices"] = [{"message": message}]
    return payload


def _client_with(monkeypatch, payload):
    monkeypatch.setattr(client_mod, "_open",
                        lambda request, timeout=None: FakeResponse(payload))
    return OpenAIChatClient("http://x/v1", None, "m")


def test_complete_rejects_non_text_content(monkeypatch):
    with pytest.raises(LLMError) as excinfo:
        _client_with(monkeypatch, _payload(content=42)).complete([])
    # F033: the rejected envelope still carries safe metadata.
    assert excinfo.value.model == "m"
    assert excinfo.value.prompt_tokens == 1
    assert excinfo.value.completion_tokens == 2


def test_complete_transport_error_carries_the_configured_model(monkeypatch):
    monkeypatch.setattr(client_mod, "_open", lambda request, timeout=None: (_ for _ in ()).throw(urllib.error.URLError("down")))
    with pytest.raises(LLMError) as excinfo:
        OpenAIChatClient("http://x/v1", None, "configured-model").complete([])
    assert excinfo.value.model == "configured-model"
    assert excinfo.value.prompt_tokens is None


def test_complete_missing_choices_is_an_error(monkeypatch):
    with pytest.raises(LLMError):
        _client_with(monkeypatch, {"usage": {}}).complete([])


def test_complete_tolerates_malformed_usage(monkeypatch):
    result = _client_with(monkeypatch, _payload(content="ok", usage=[1, 2])).complete([])
    assert result.content == "ok"
    assert result.prompt_tokens is None and result.completion_tokens is None


def test_complete_surfaces_a_refusal(monkeypatch):
    result = _client_with(monkeypatch,
                          _payload(content=None, refusal="I cannot help.")).complete([])
    assert result.content == ""
    assert result.refusal == "I cannot help."


def _serve(handler_cls):
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_redirect_does_not_forward_the_bearer_to_another_origin():
    seen = {}

    class Destination(http.server.BaseHTTPRequestHandler):
        def _record(self):
            # urllib turns a redirected POST into a GET, so record both.
            seen["authorization"] = self.headers.get("Authorization")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        do_POST = _record
        do_GET = _record

        def log_message(self, *args):
            pass

    destination = _serve(Destination)

    class Redirector(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(302)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{destination.server_address[1]}/chat/completions",
            )
            self.end_headers()

        def log_message(self, *args):
            pass

    redirector = _serve(Redirector)
    try:
        client = OpenAIChatClient(
            f"http://127.0.0.1:{redirector.server_address[1]}/v1", "sk-secret", "m"
        )
        with pytest.raises(LLMError):
            client.complete([{"role": "user", "content": "hi"}])
        # The redirect is refused, so the destination server is never contacted.
        assert "authorization" not in seen
    finally:
        redirector.shutdown()
        destination.shutdown()
