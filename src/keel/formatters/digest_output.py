"""Render 02-digest.md header and source table."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import yaml


def render_digest_header(
    topic: str,
    source_count: int,
    extract_metadata: list[dict[str, Any]],
) -> str:
    """Render the header portion of 02-digest.md (before the synthesis content)."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Source Digest: {topic}",
        f"Generated: {timestamp}",
        f"Sources processed: {source_count}",
        "",
        "## Sources Extracted",
        "| # | File | Title | Author | Publication | Date |",
        "|---|------|-------|--------|-------------|------|",
    ]

    for i, meta in enumerate(extract_metadata, 1):
        filename = _escape_pipe(meta.get("file", "?"))
        title = _escape_pipe(meta.get("title", "?"))
        author = _escape_pipe(meta.get("author", "?"))
        pub = _escape_pipe(meta.get("publication", "?"))
        date = meta.get("date", "?")
        lines.append(f"| {i} | {filename} | {title} | {author} | {pub} | {date} |")

    lines.append("")
    return "\n".join(lines)


def parse_extract_frontmatter(extract_path) -> dict[str, Any]:
    """Parse YAML frontmatter from an extract markdown file."""
    from pathlib import Path

    text = Path(extract_path).read_text()

    if not text.startswith("---"):
        return {"file": Path(extract_path).stem}

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {"file": Path(extract_path).stem}

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}

    meta["file"] = Path(extract_path).stem
    return meta


def _escape_pipe(text: str) -> str:
    return str(text).replace("|", "\\|")
