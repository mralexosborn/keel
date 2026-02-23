"""Rich console singleton and display helpers."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def info(msg: str) -> None:
    console.print(f"[bold blue]ℹ[/] {msg}")


def success(msg: str) -> None:
    console.print(f"[bold green]✓[/] {msg}")


def warn(msg: str) -> None:
    err_console.print(f"[bold yellow]⚠[/] {msg}")


def error(msg: str) -> None:
    err_console.print(f"[bold red]✗[/] {msg}")


def stage_header(stage: str, description: str) -> None:
    console.print(Panel(f"[bold]{description}[/]", title=stage, border_style="blue"))


def make_table(title: str, columns: list[tuple[str, str]]) -> Table:
    """Create a Rich table with the given title and (name, style) column specs."""
    table = Table(title=title, show_lines=True)
    for name, style in columns:
        table.add_column(name, style=style)
    return table
