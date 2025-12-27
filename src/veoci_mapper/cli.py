"""CLI interface for Veoci Solution Mapper."""

import asyncio
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from veoci_mapper.analyzer import analyze_solution
from veoci_mapper.client import VeociClient
from veoci_mapper.fetcher import fetch_solution
from veoci_mapper.graph import build_graph, get_graph_stats

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
    base_url: str = typer.Option(
        "https://veoci.com",
        "--base-url",
        "-u",
        help="Veoci base URL",
        envvar="VEOCI_BASE_URL",
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

    # Run async fetch
    asyncio.run(_fetch_and_report(room_id, token, base_url))


async def _fetch_and_report(room_id: str, token: str, base_url: str) -> None:
    """Fetch solution data and report summary."""
    async with VeociClient(token=token, base_url=base_url) as client:
        solution = await fetch_solution(client, room_id)

    # Analyze relationships
    relationships = analyze_solution(solution["form_definitions"])

    # Build graph
    graph = build_graph(solution["forms"], solution["workflows"], relationships)
    stats = get_graph_stats(graph)

    # Report summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Container ID: {solution['container_id']}")
    console.print(f"  Forms: {len(solution['forms'])}")
    console.print(f"  Form definitions: {len(solution['form_definitions'])}")
    console.print(f"  Workflows: {len(solution['workflows'])}")

    console.print("\n[bold]Graph Statistics:[/bold]")
    console.print(
        f"  Nodes: {stats['total_nodes']} "
        f"({stats['form_count']} forms, {stats['workflow_count']} workflows)"
    )
    console.print(f"  Edges: {stats['total_edges']}")
    console.print(f"  Isolated: {stats['isolated_nodes']}")
    console.print(f"  Components: {stats['connected_components']}")

    console.print("\n[green]Fetch complete![/green]")


def main() -> None:
    """Entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
