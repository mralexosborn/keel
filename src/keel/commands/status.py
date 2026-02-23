"""keel status — show current project state."""

from __future__ import annotations

import click
from rich.table import Table

from keel.cli import KeelContext, pass_ctx
from keel.core.state import STAGES, get_active_stage, is_stage_complete, next_action, read_state
from keel.core.workspace import project_path, require_active_project
from keel.utils.console import console, info


@click.command()
@pass_ctx
def status(ctx: KeelContext) -> None:
    """Show current project, stage, and next action."""
    slug = require_active_project(ctx.project_slug)
    pdir = project_path(slug)
    state = read_state(pdir)

    console.print(f"\n[bold]Project:[/] {slug}")
    console.print(f"[bold]Topic:[/] {state.get('topic', '?')}")
    console.print(f"[bold]Created:[/] {state.get('created', '?')}")
    console.print()

    table = Table(title="Stage Progress", show_lines=False)
    table.add_column("Stage", style="bold")
    table.add_column("Status")
    table.add_column("Output")

    active = get_active_stage(state)

    for stage in STAGES:
        if is_stage_complete(state, stage):
            status_str = "[green]Complete[/]"
        elif stage == active:
            status_str = "[yellow]Active[/]"
        else:
            status_str = "[dim]Pending[/]"

        output = state.get("stages", {}).get(stage, {}).get("output", "")
        output_exists = (pdir / output).exists() if output else False
        output_str = f"{output} {'[green]✓[/]' if output_exists else ''}" if output else ""

        table.add_row(stage.capitalize(), status_str, output_str)

    console.print(table)
    console.print()
    info(f"Next: {next_action(state)}")

    # Show scan count
    scan_count = state.get("scan_count", 0)
    if scan_count:
        latest = state.get("stages", {}).get("scan", {}).get("output", "")
        info(f"Scans: {scan_count} (latest: {latest})")

    # Show source count if relevant
    sources_dir = pdir / "sources"
    if sources_dir.exists():
        pdf_count = len(list(sources_dir.glob("*.pdf")))
        if pdf_count:
            info(f"PDFs in sources/: {pdf_count}")
