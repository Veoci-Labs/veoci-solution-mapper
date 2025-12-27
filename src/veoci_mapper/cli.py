"""CLI interface for Veoci Solution Mapper."""

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import typer
from rich.console import Console

load_dotenv()

app = typer.Typer(
    name="veoci-map",
    help="Map Veoci solution structure and dependencies",
    add_completion=False,
)
console = Console()


@app.command()
def map(
    room_id: str = typer.Option(
        ...,
        "--room-id",
        "-r",
        help="Veoci room ID to map",
    ),
    token: str = typer.Option(
        ...,
        "--token",
        "-t",
        help="Veoci API token",
        envvar="VEOCI_TOKEN",
    ),
    output: Path = typer.Option(
        Path.cwd(),
        "--output",
        "-o",
        help="Output directory for generated files",
        file_okay=False,
        dir_okay=True,
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Enable interactive mode for configuration",
    ),
) -> None:
    """Map a Veoci room's solution structure and dependencies.

    This command fetches the solution structure from a Veoci room and generates
    documentation and dependency graphs.
    """
    console.print(f"[bold green]Mapping room {room_id}...[/bold green]")

    if interactive:
        console.print("[yellow]Interactive mode enabled (not yet implemented)[/yellow]")

    console.print(f"Output directory: {output}")
    console.print("[dim]Placeholder - implementation pending[/dim]")


def main() -> None:
    """Entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
