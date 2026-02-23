"""keel list, set, archive — project management commands."""

from __future__ import annotations

import click
from rich.table import Table

from keel.cli import KeelContext, pass_ctx
from keel.core.state import get_active_stage, read_state
from keel.core.workspace import (
    archive_project,
    get_active_project,
    list_projects,
    project_path,
    set_active_project,
)
from keel.utils.console import console, info, success


@click.command("list")
@pass_ctx
def list_cmd(ctx: KeelContext) -> None:
    """List all active projects."""
    projects = list_projects()
    if not projects:
        info("No projects found. Run 'keel new <topic>' to create one.")
        return

    active = get_active_project()

    table = Table(title="Projects", show_lines=False)
    table.add_column("", width=2)
    table.add_column("Slug", style="bold")
    table.add_column("Topic")
    table.add_column("Stage")

    for proj in projects:
        slug = proj["slug"]
        marker = "[green]*[/]" if slug == active else ""
        try:
            state = read_state(project_path(slug))
            topic = state.get("topic", "?")
            stage = get_active_stage(state)
        except Exception:
            topic = "?"
            stage = "?"
        table.add_row(marker, slug, topic, stage)

    console.print(table)


@click.command("set")
@click.argument("slug")
@pass_ctx
def set_cmd(ctx: KeelContext, slug: str) -> None:
    """Switch active project to SLUG."""
    set_active_project(slug)
    success(f"Active project set to '{slug}'.")


@click.command("archive")
@click.argument("slug", required=False)
@pass_ctx
def archive_cmd(ctx: KeelContext, slug: str | None) -> None:
    """Move a project to the archive."""
    from keel.core.workspace import require_active_project

    target = slug or require_active_project(ctx.project_slug)

    if not click.confirm(f"Archive project '{target}'?"):
        return

    dest = archive_project(target)
    success(f"Project '{target}' archived to {dest}")
