"""Configuration loading and defaults for keel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from keel.errors import ConfigError

DEFAULTS: dict[str, Any] = {
    "sources": {
        "rss_feeds": [],
        "trusted_domains": {
            "tier_1": [],
            "tier_2": [],
            "tier_3": [],
        },
        "blocked_domains": [],
    },
    "search": {
        "provider": "brave",
        "api_key_env": "BRAVE_SEARCH_API_KEY",
    },
    "claude": {
        "command": "claude",
        "default_model": "opus",
        "model_overrides": {
            "scan": "sonnet",
            "digest_extract": "sonnet",
        },
    },
    "archive": {
        "past_articles": [],
    },
}

# Trust tier multipliers for ranking
TRUST_MULTIPLIERS: dict[str, float] = {
    "tier_1": 3.0,
    "tier_2": 1.5,
    "tier_3": 1.0,
    "untiered": 0.5,
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(keel_dir: Path) -> dict[str, Any]:
    """Load config.yaml from keel_dir, merged with defaults."""
    config_path = keel_dir / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path) as f:
                user_config = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid config.yaml: {exc}")
        return _deep_merge(DEFAULTS, user_config)
    return DEFAULTS.copy()


def save_config(keel_dir: Path, config: dict[str, Any]) -> None:
    """Write config dict to config.yaml."""
    config_path = keel_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def get_model(config: dict[str, Any], task: str) -> str:
    """Resolve the Claude model for a given task."""
    overrides = config.get("claude", {}).get("model_overrides", {})
    return overrides.get(task, config.get("claude", {}).get("default_model", "opus"))


def get_trust_tier(config: dict[str, Any], domain: str) -> tuple[str, float]:
    """Return (tier_name, multiplier) for a domain."""
    trusted = config.get("sources", {}).get("trusted_domains", {})
    blocked = config.get("sources", {}).get("blocked_domains", [])

    # Strip www. prefix for matching
    clean = domain.lower().removeprefix("www.")

    if clean in blocked or domain in blocked:
        return "blocked", 0.0

    for tier_name in ("tier_1", "tier_2", "tier_3"):
        domains = trusted.get(tier_name, [])
        if clean in domains or domain in domains:
            return tier_name, TRUST_MULTIPLIERS[tier_name]

    return "untiered", TRUST_MULTIPLIERS["untiered"]


def is_blocked(config: dict[str, Any], domain: str) -> bool:
    """Check if a domain is in the blocked list."""
    tier, _ = get_trust_tier(config, domain)
    return tier == "blocked"
