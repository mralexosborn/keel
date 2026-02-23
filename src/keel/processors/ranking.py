"""Deduplication, trust-tier scoring, and recency sorting for scan results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from keel.core.config import get_trust_tier, is_blocked

# Wire services and intergovernmental orgs that are universally authoritative
# regardless of topic. Kept intentionally small — domain-type heuristics
# (.gov, .edu, etc.) handle the long tail.
_WIRE_SERVICES = {
    "reuters.com",
    "apnews.com",
    "afp.com",
}


def deduplicate(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate URLs, keeping the first occurrence."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in results:
        url = _normalize_url(item.get("url", ""))
        if url not in seen:
            seen.add(url)
            unique.append(item)
    return unique


def rank_results(
    results: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Score and sort results by trust × relevance × recency. Filter blocked domains."""
    scored: list[dict[str, Any]] = []

    for item in results:
        domain = item.get("domain", "")
        if is_blocked(config, domain):
            continue

        trust = _trust_score(config, domain)
        relevance = _relevance_score(item)
        recency = _recency_score(item.get("date", "Unknown"))

        score = trust * relevance * recency

        scored.append({
            **item,
            "trust_tier": _trust_label(config, domain),
            "score": round(score, 4),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _trust_score(config: dict[str, Any], domain: str) -> float:
    """Compute trust score from config tiers, domain type heuristics, and wire services."""
    # Check explicit config tiers first
    tier_name, multiplier = get_trust_tier(config, domain)
    if tier_name != "untiered":
        return multiplier

    # Domain-type heuristics for domains not in the config
    clean = domain.lower().removeprefix("www.")

    # Wire services
    if clean in _WIRE_SERVICES:
        return 3.0

    # Government domains — primary sources
    if clean.endswith(".gov") or clean.endswith(".mil"):
        return 3.0

    # Intergovernmental / international orgs
    if clean.endswith(".int"):
        return 2.5

    # Education / academic
    if clean.endswith(".edu"):
        return 2.0

    # Research publications (PubMed, ScienceDirect, arxiv, etc.)
    if any(p in clean for p in ("ncbi.nlm.nih.gov", "sciencedirect.com", "arxiv.org", "jstor.org", "nature.com", "springer.com")):
        return 2.0

    # Known think tank / research org patterns (broad, not publication-specific)
    if clean.endswith(".org") and any(p in clean for p in (
        "brookings", "csis", "stimson", "carnegie", "rand", "cfr",
        "chathamhouse", "imo.", "oecd", "worldbank", "imf.",
    )):
        return 2.5

    # Generic .org gets a small bump over unknown .com
    if clean.endswith(".org"):
        return 0.7

    # Everything else
    return 0.5


def _trust_label(config: dict[str, Any], domain: str) -> str:
    """Human-readable trust label for display."""
    tier_name, _ = get_trust_tier(config, domain)
    if tier_name != "untiered":
        return tier_name

    clean = domain.lower().removeprefix("www.")
    if clean in _WIRE_SERVICES:
        return "wire_service"
    # Check academic before .gov so pmc.ncbi.nlm.nih.gov → academic
    if any(p in clean for p in ("ncbi.nlm.nih.gov", "sciencedirect.com", "arxiv.org", "jstor.org", "nature.com", "springer.com")):
        return "academic"
    if clean.endswith(".gov") or clean.endswith(".mil"):
        return "government"
    if clean.endswith(".int"):
        return "intergovernmental"
    if clean.endswith(".edu"):
        return "academic"
    if clean.endswith(".org") and any(p in clean for p in (
        "brookings", "csis", "stimson", "carnegie", "rand", "cfr",
        "chathamhouse", "imo.", "oecd", "worldbank", "imf.",
    )):
        return "research"
    return "untiered"


def _relevance_score(item: dict[str, Any]) -> float:
    """Score based on search engine result position.

    Brave returns results in relevance order. Position 0 (top result)
    scores 1.0, decaying to 0.5 for the last result. Items without
    a search position (e.g. RSS results) get a neutral 0.75.
    """
    position = item.get("search_position")
    total = item.get("search_total")

    if position is None or total is None or total == 0:
        return 0.75

    # Linear decay from 1.0 (top) to 0.5 (bottom)
    return 1.0 - (position / total) * 0.5


def _recency_score(date_str: str) -> float:
    """Score recency: 1.0 for today, decaying over 90 days."""
    if date_str in ("Unknown", "", None):
        return 0.5

    try:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            try:
                dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, IndexError):
                return 0.5

        now = datetime.now(timezone.utc)
        age_days = (now - dt).days
        if age_days < 0:
            return 1.0
        if age_days > 90:
            return 0.1
        return 1.0 - (age_days / 90.0) * 0.9
    except Exception:
        return 0.5


def _normalize_url(url: str) -> str:
    """Normalize a URL for deduplication."""
    try:
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized.lower()
    except Exception:
        return url.lower()
