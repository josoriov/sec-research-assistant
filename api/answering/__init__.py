"""OpenAI-compatible model client for answer composition."""
from api.answering.client import ChatResult, LLMError, OpenAIChatClient, client_from_env

__all__ = ["ChatResult", "LLMError", "OpenAIChatClient", "client_from_env"]
