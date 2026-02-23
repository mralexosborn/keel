"""Click CLI group, global flags, and context object."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv

from keel.core.config import load_config
from keel.core.workspace import keel_dir


@dataclass
class KeelContext:
    """Shared context passed through Click commands."""

    verbose: bool = False
    project_slug: str | None = None
    no_cache: bool = False
    edit: bool = False
    context_file: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def keel_dir(self) -> Path:
        return keel_dir()


pass_ctx = click.make_pass_decorator(KeelContext, ensure=True)


@click.group()
@click.option("--project", "-p", default=None, help="Operate on a specific project slug.")
@click.option("--verbose", "-v", is_flag=True, help="Show Claude Code invocations and raw output.")
@click.option("--no-cache", is_flag=True, help="Force re-fetch of sources.")
@click.option("--edit", is_flag=True, help="Open output file in $EDITOR after stage completes.")
@click.option("--context", "context_file", default=None, help="Load additional seed context file.")
@click.pass_context
def cli(ctx: click.Context, project: str | None, verbose: bool, no_cache: bool, edit: bool, context_file: str | None) -> None:
    """Keel — compress the research-to-draft pipeline for long-form analytical writing."""
    load_dotenv()
    kctx = KeelContext(
        verbose=verbose,
        project_slug=project,
        no_cache=no_cache,
        edit=edit,
        context_file=context_file,
        config=load_config(keel_dir()),
    )
    ctx.obj = kctx


# Import and register commands
from keel.commands.new import new  # noqa: E402
from keel.commands.scan import scan  # noqa: E402
from keel.commands.digest import digest  # noqa: E402
from keel.commands.status import status  # noqa: E402
from keel.commands.sources import sources  # noqa: E402
from keel.commands.project import list_cmd, set_cmd, archive_cmd  # noqa: E402

cli.add_command(new)
cli.add_command(scan)
cli.add_command(digest)
cli.add_command(status)
cli.add_command(sources)
cli.add_command(list_cmd)
cli.add_command(set_cmd)
cli.add_command(archive_cmd)
