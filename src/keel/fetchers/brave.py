"""Brave Search API client with rate limiting."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import httpx

from keel.errors import ConfigError, FetchError
from keel.utils.console import warn
from keel.utils.network import RateLimiter, retry_with_backoff

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
RESULTS_PER_QUERY = 10

_rate_limiter = RateLimiter(requests_per_second=1.0)


def search_brave(
    queries: list[str],
    api_key_env: str = "BRAVE_SEARCH_API_KEY",
) -> list[dict[str, Any]]:
    """Run search queries against Brave Search API.

    Returns a list of dicts with: title, url, domain, date, snippet.
    """
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise ConfigError(
            f"Brave Search API key not found. Set the {api_key_env} environment variable."
        )

    results: list[dict[str, Any]] = []

    for query in queries:
        try:
            hits = _search_single(query, api_key)
            results.extend(hits)
        except FetchError as exc:
            warn(f"Search failed for query '{query}': {exc.message}")

    return results


def _search_single(query: str, api_key: str) -> list[dict[str, Any]]:
    """Execute a single search query."""
    _rate_limiter.wait()

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }

    params = {
        "q": query,
        "count": RESULTS_PER_QUERY,
    }

    def _do_request() -> httpx.Response:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(BRAVE_SEARCH_URL, headers=headers, params=params)
            resp.raise_for_status()
            return resp

    resp = retry_with_backoff(_do_request)
    data = resp.json()

    results: list[dict[str, Any]] = []
    web_results = data.get("web", {}).get("results", [])
    total = len(web_results)
    for position, item in enumerate(web_results):
        url = item.get("url", "")
        domain = _extract_domain(url)
        results.append({
            "title": item.get("title", ""),
            "url": url,
            "domain": domain,
            "date": item.get("page_age", "Unknown"),
            "snippet": item.get("description", ""),
            "search_position": position,
            "search_total": total,
        })

    return results


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc.removeprefix("www.")
    except Exception:
        return url
