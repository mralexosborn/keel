"""keel sources — list/add/remove RSS feeds and trusted domains."""

from __future__ import annotations

import click
from rich.table import Table

from keel.cli import KeelContext, pass_ctx
from keel.core.config import load_config, save_config
from keel.core.workspace import keel_dir
from keel.utils.console import console, info, success


@click.group(invoke_without_command=True)
@click.pass_context
def sources(ctx: click.Context) -> None:
    """List, add, or remove RSS feeds and trusted domains."""
    if ctx.invoked_subcommand is None:
        _list_sources(ctx.obj)


@sources.command("add")
@click.argument("url")
@click.option("--name", default=None, help="Display name for the feed.")
@click.option("--tier", type=click.IntRange(1, 3), default=2, help="Trust tier (1-3).")
@click.option("--type", "source_type", type=click.Choice(["rss", "domain"]), default="rss", help="Source type.")
@pass_ctx
def add_source(ctx: KeelContext, url: str, name: str | None, tier: int, source_type: str) -> None:
    """Add an RSS feed or trusted domain."""
    kd = keel_dir()
    config = load_config(kd)

    if source_type == "rss":
        feeds = config.setdefault("sources", {}).setdefault("rss_feeds", [])
        # Check for duplicate
        if any(f.get("url") == url for f in feeds):
            info(f"Feed already exists: {url}")
            return
        feeds.append({
            "url": url,
            "name": name or url,
            "trust_tier": tier,
            "domains": [],
        })
        save_config(kd, config)
        success(f"Added RSS feed: {url}")
    else:
        tier_key = f"tier_{tier}"
        domains = config.setdefault("sources", {}).setdefault("trusted_domains", {}).setdefault(tier_key, [])
        domain = url.lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")
        if domain in domains:
            info(f"Domain already in tier {tier}: {domain}")
            return
        domains.append(domain)
        save_config(kd, config)
        success(f"Added domain to tier {tier}: {domain}")


@sources.command("remove")
@click.argument("url")
@pass_ctx
def remove_source(ctx: KeelContext, url: str) -> None:
    """Remove an RSS feed or trusted domain."""
    kd = keel_dir()
    config = load_config(kd)

    # Try RSS feeds first
    feeds = config.get("sources", {}).get("rss_feeds", [])
    original_len = len(feeds)
    config["sources"]["rss_feeds"] = [f for f in feeds if f.get("url") != url]
    if len(config["sources"]["rss_feeds"]) < original_len:
        save_config(kd, config)
        success(f"Removed RSS feed: {url}")
        return

    # Try trusted domains
    domain = url.lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")
    for tier_key in ("tier_1", "tier_2", "tier_3"):
        domains = config.get("sources", {}).get("trusted_domains", {}).get(tier_key, [])
        if domain in domains:
            domains.remove(domain)
            save_config(kd, config)
            success(f"Removed domain from {tier_key}: {domain}")
            return

    info(f"Source not found: {url}")


def _list_sources(ctx: KeelContext) -> None:
    """Display current RSS feeds and trusted domains."""
    config = ctx.config

    feeds = config.get("sources", {}).get("rss_feeds", [])
    if feeds:
        table = Table(title="RSS Feeds", show_lines=False)
        table.add_column("Name", style="bold")
        table.add_column("URL")
        table.add_column("Tier")
        for feed in feeds:
            table.add_row(
                feed.get("name", "?"),
                feed.get("url", "?"),
                str(feed.get("trust_tier", "?")),
            )
        console.print(table)
    else:
        info("No RSS feeds configured.")

    console.print()

    trusted = config.get("sources", {}).get("trusted_domains", {})
    has_domains = False
    for tier_key in ("tier_1", "tier_2", "tier_3"):
        domains = trusted.get(tier_key, [])
        if domains:
            has_domains = True
            label = tier_key.replace("_", " ").title()
            console.print(f"[bold]{label}:[/] {', '.join(domains)}")

    if not has_domains:
        info("No trusted domains configured.")

    blocked = config.get("sources", {}).get("blocked_domains", [])
    if blocked:
        console.print(f"\n[bold]Blocked:[/] {', '.join(blocked)}")
