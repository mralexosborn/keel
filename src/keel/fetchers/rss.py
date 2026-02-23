"""RSS feed fetcher via feedparser with keyword filtering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser

from keel.utils.console import warn

# Only include entries from the last 90 days
RSS_WINDOW_DAYS = 90


def fetch_rss_feeds(
    feeds: list[dict[str, Any]],
    topic: str,
    queries: list[str],
) -> list[dict[str, Any]]:
    """Fetch entries from RSS feeds, filtered by keyword relevance and recency.

    Returns a list of dicts with: title, url, domain, date, source_name, trust_tier.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=RSS_WINDOW_DAYS)
    keywords = _extract_keywords(topic, queries)
    results: list[dict[str, Any]] = []

    for feed_config in feeds:
        url = feed_config.get("url", "")
        name = feed_config.get("name", url)
        tier = feed_config.get("trust_tier", 3)

        try:
            parsed = feedparser.parse(url)
        except Exception as exc:
            warn(f"Failed to parse RSS feed '{name}': {exc}")
            continue

        for entry in parsed.entries:
            # Parse date
            entry_date = _parse_entry_date(entry)
            if entry_date and entry_date < cutoff:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")

            if not link:
                continue

            # Keyword filter
            text = f"{title} {summary}".lower()
            if not any(kw in text for kw in keywords):
                continue

            domain = _extract_domain(link)
            results.append({
                "title": title,
                "url": link,
                "domain": domain,
                "date": entry_date.strftime("%Y-%m-%d") if entry_date else "Unknown",
                "source_name": name,
                "trust_tier": tier,
            })

    return results


def _extract_keywords(topic: str, queries: list[str]) -> list[str]:
    """Build a lowercase keyword list from topic and queries."""
    words = set()
    for text in [topic] + queries:
        for word in text.lower().split():
            cleaned = word.strip("\"'.,;:!?()[]{}").lower()
            if len(cleaned) > 3:
                words.add(cleaned)
    return list(words)


def _parse_entry_date(entry: Any) -> datetime | None:
    """Try to parse a date from a feedparser entry."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, field, None)
        if parsed:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except Exception:
                pass
    return None


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        return parsed.netloc.removeprefix("www.")
    except Exception:
        return url
