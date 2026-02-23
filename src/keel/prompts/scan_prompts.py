"""Prompts for Stage 1: Source Discovery."""

from __future__ import annotations


def query_generation_prompt(topic: str, notes: str | None = None) -> str:
    """Generate the prompt for expanding a topic into search queries."""
    context_block = ""
    if notes:
        context_block = (
            f"\n\nThe author has provided these initial notes and context for this project:\n"
            f"{notes}\n"
        )

    return f"""You are helping a researcher discover sources on the following topic:

"{topic}"{context_block}

Generate 5-8 specific search queries optimized for finding different types of sources. Cover these angles:
- Trade press / industry reporting
- Policy analysis and government reports
- Financial data and company filings
- Technical detail and academic work
- Contrarian or dissenting perspectives

Return ONLY a JSON array of query strings, nothing else. Example:
["query one", "query two", "query three"]"""
