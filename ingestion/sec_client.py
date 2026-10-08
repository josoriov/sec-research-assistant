"""SEC EDGAR HTTP client.

Identifies the client with a User-Agent (SEC access guidance requires a
descriptive agent with contact details) and throttles requests. Uses the
standard library so the project needs no HTTP dependency.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request

# SEC allows up to 10 requests/second; stay conservatively below that.
MIN_INTERVAL_SECONDS = 0.2
RETRYABLE_STATUS = (429, 500, 502, 503, 504)


class SecClient:
    def __init__(self, user_agent: str, min_interval: float = MIN_INTERVAL_SECONDS, opener=None):
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "SEC_USER_AGENT must identify the client with contact details, "
                "e.g. 'sec-research-assistant you@example.com'"
            )
        self.user_agent = user_agent
        self.min_interval = min_interval
        self._last_request = 0.0
        self._open = opener or urllib.request.urlopen

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request = time.monotonic()

    def get(self, url: str, *, retries: int = 3) -> bytes:
        """Fetch a URL, retrying temporary errors with exponential backoff."""
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            self._throttle()
            request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            try:
                with self._open(request, timeout=30) as response:
                    return response.read()
            except urllib.error.HTTPError as error:
                if error.code in RETRYABLE_STATUS and attempt < retries:
                    last_error = error
                    time.sleep(2**attempt)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError) as error:
                # TimeoutError covers response-body read timeouts as well as
                # connection timeouts, so large downloads still retry.
                if attempt < retries:
                    last_error = error
                    time.sleep(2**attempt)
                    continue
                raise
        raise last_error  # pragma: no cover - loop always returns or raises
