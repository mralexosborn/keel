"""Network utilities — retry with backoff and rate limiter."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

import httpx

from keel.errors import FetchError

T = TypeVar("T")

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
BACKOFF_BASE = 2.0


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_retries: int = MAX_RETRIES,
    backoff_base: float = BACKOFF_BASE,
) -> T:
    """Call fn(), retrying on httpx errors with exponential backoff."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                delay = backoff_base ** attempt
                time.sleep(delay)
    raise FetchError(f"Request failed after {max_retries} attempts: {last_exc}")


class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, requests_per_second: float) -> None:
        self._min_interval = 1.0 / requests_per_second
        self._last_call = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()
