"""Render scan-N.md — the source discovery output file."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def render_scan_markdown(
    topic: str,
    queries: list[str],
    results: list[dict[str, Any]],
) -> str:
    """Render the scan results as a markdown table."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    queries_str = ", ".join(f'"{q}"' for q in queries)

    lines = [
        f"# Source Discovery: {topic}",
        f"Generated: {timestamp}",
        f"Queries used: {queries_str}",
        "",
        "| # | Title | Source | Date | URL | Trust |",
        "|---|-------|--------|------|-----|-------|",
    ]

    for i, item in enumerate(results, 1):
        title = _escape_pipe(item.get("title", "Untitled"))
        domain = _escape_pipe(item.get("domain", "?"))
        date = item.get("date", "Unknown")
        url = item.get("url", "")
        trust = item.get("trust_tier", "untiered")
        trust_display = trust.replace("_", " ").title() if trust != "untiered" else "Untiered"

        lines.append(f"| {i} | {title} | {domain} | {date} | {url} | {trust_display} |")

    lines.append("")
    lines.append(f"Sources found: {len(results)}")
    lines.append("")

    return "\n".join(lines)


def _escape_pipe(text: str) -> str:
    """Escape pipe characters in markdown table cells."""
    return text.replace("|", "\\|")
