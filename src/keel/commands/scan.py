"""keel scan — Stage 1 source discovery orchestrator."""

from __future__ import annotations

import json
import os

import click

from keel.cli import KeelContext, pass_ctx
from keel.core.claude import invoke_claude
from keel.core.config import get_model
from keel.core.state import (
    can_run_stage,
    complete_stage,
    is_stage_complete,
    next_scan_number,
    read_state,
)
from keel.core.workspace import project_path, require_active_project
from keel.errors import ClaudeError
from keel.fetchers.brave import search_brave
from keel.fetchers.rss import fetch_rss_feeds
from keel.formatters.scan_output import render_scan_markdown
from keel.processors.ranking import deduplicate, rank_results
from keel.prompts.scan_prompts import query_generation_prompt
from keel.utils.console import error, info, stage_header, success, warn


@click.command()
@pass_ctx
def scan(ctx: KeelContext) -> None:
    """Stage 1: Discover and rank sources for the active project."""
    _run_scan(ctx)


def _run_scan(ctx: KeelContext) -> None:
    """Core scan logic, also called by 'keel new'."""
    slug = require_active_project(ctx.project_slug)
    pdir = project_path(slug)
    state = read_state(pdir)

    # Check stage progression — scan can always re-run (creates a new numbered version)
    if not is_stage_complete(state, "scan"):
        ok, reason = can_run_stage(state, "scan")
        if not ok:
            raise click.ClickException(reason)

    topic = state.get("topic", slug)
    stage_header("Stage 1", f"Source Discovery: {topic}")

    # Load user notes if available
    notes = _load_notes(pdir, ctx.context_file)

    # Step 1: Generate search queries via Claude
    info("Generating search queries...")
    model = get_model(ctx.config, "scan")
    prompt = query_generation_prompt(topic, notes)

    try:
        raw = invoke_claude(prompt, pdir, verbose=ctx.verbose, model=model)
        queries = _parse_queries(raw)
    except ClaudeError:
        warn("Claude query generation failed. Using topic as fallback query.")
        queries = [topic]

    info(f"Using {len(queries)} search queries")
    if ctx.verbose:
        for q in queries:
            info(f"  - {q}")

    # Step 2: Fetch from RSS feeds
    feeds = ctx.config.get("sources", {}).get("rss_feeds", [])
    rss_results = []
    if feeds:
        info(f"Fetching from {len(feeds)} RSS feeds...")
        rss_results = fetch_rss_feeds(feeds, topic, queries)
        info(f"Found {len(rss_results)} RSS results")

    # Step 3: Fetch from Brave Search
    brave_results = []
    api_key_env = ctx.config.get("search", {}).get("api_key_env", "BRAVE_SEARCH_API_KEY")
    if os.environ.get(api_key_env):
        info("Searching via Brave Search API...")
        brave_results = search_brave(queries, api_key_env=api_key_env)
        info(f"Found {len(brave_results)} search results")
    else:
        warn(f"Brave Search API key not set ({api_key_env}). Skipping web search.")

    # Step 4: Merge, deduplicate, rank
    all_results = rss_results + brave_results
    if not all_results:
        error("No results found from any source.")
        return

    unique = deduplicate(all_results)
    ranked = rank_results(unique, ctx.config)
    info(f"After dedup and ranking: {len(ranked)} sources")

    # Step 5: Write output with numbered version
    n = next_scan_number(state)
    output_filename = f"scan-{n}.md"
    output = render_scan_markdown(topic, queries, ranked)
    output_path = pdir / output_filename
    output_path.write_text(output)

    state = complete_stage(pdir, state, "scan", output=output_filename)
    success(f"Scan #{n} complete: {output_path}")
    info("Next: Review sources, save relevant PDFs to sources/, then run 'keel digest'.")

    # Open in editor if requested
    if ctx.edit:
        editor = os.environ.get("EDITOR", "vi")
        click.edit(filename=str(output_path), editor=editor)


def _load_notes(project_dir, context_file: str | None) -> str | None:
    """Load user seed context from notes.md or --context flag."""
    if context_file:
        from pathlib import Path

        cf = Path(context_file)
        if cf.exists():
            return cf.read_text()

    notes_path = project_dir / "notes.md"
    if notes_path.exists():
        return notes_path.read_text()

    return None


def _parse_queries(raw: str) -> list[str]:
    """Parse Claude's JSON array response into a list of query strings."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        queries = json.loads(text)
        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            return queries
    except json.JSONDecodeError:
        pass

    # Fallback: try to extract anything that looks like a list
    import re

    matches = re.findall(r'"([^"]+)"', raw)
    if matches:
        return matches

    return [raw.strip()]
