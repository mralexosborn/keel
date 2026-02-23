"""keel new — create a new research project and auto-run scan."""

from __future__ import annotations

import click

from keel.cli import KeelContext, pass_ctx
from keel.core.state import init_state
from keel.core.workspace import create_project
from keel.utils.console import info, success
from keel.utils.slugify import slugify


@click.command()
@click.argument("topic")
@pass_ctx
def new(ctx: KeelContext, topic: str) -> None:
    """Create a new research project from a topic string."""
    slug = slugify(topic)
    if not slug:
        raise click.ClickException("Topic produced an empty slug. Use a more descriptive topic.")

    info(f"Creating project: {slug}")
    project_dir = create_project(slug, topic)
    init_state(project_dir, topic)
    success(f"Project created at {project_dir}")

    # Auto-run scan
    from keel.commands.scan import _run_scan

    ctx.project_slug = slug
    _run_scan(ctx)
