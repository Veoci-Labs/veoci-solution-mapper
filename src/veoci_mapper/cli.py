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
from veoci_mapper.output import (
    export_json,
    export_mermaid,
    export_html,
    generate_markdown_summary,
    generate_basic_markdown,
    export_markdown,
)

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
        Path("./output"),
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
    asyncio.run(_fetch_and_report(room_id, token, base_url, output))


async def _fetch_and_report(
    room_id: str,
    token: str,
    base_url: str,
    output_dir: Path,
) -> None:
    """Fetch solution data and generate all outputs."""
    async with VeociClient(token=token, base_url=base_url) as client:
        solution = await fetch_solution(client, room_id)

    # Analyze relationships
    console.print("[dim]Analyzing relationships...[/dim]")
    relationships = analyze_solution(solution["form_definitions"])
    console.print(f"[green]Found {len(relationships)} relationships[/green]")

    # Build graph
    console.print("[dim]Building graph...[/dim]")
    graph = build_graph(solution["forms"], solution["workflows"], relationships)
    stats = get_graph_stats(graph)

    # Print stats
    console.print("\n[bold]Graph Statistics:[/bold]")
    console.print(
        f"  Nodes: {stats['total_nodes']} "
        f"({stats['form_count']} forms, {stats['workflow_count']} workflows)"
    )
    console.print(f"  Edges: {stats['total_edges']}")
    console.print(f"  Isolated: {stats['isolated_nodes']}")
    console.print(f"  Components: {stats['connected_components']}")

    # Generate outputs
    console.print("\n[bold]Generating outputs...[/bold]")
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = export_json(
        container_id=room_id,
        forms=solution["forms"],
        workflows=solution["workflows"],
        relationships=relationships,
        stats=stats,
        output_path=output_dir / "solution.json",
    )
    console.print(f"  [green]✓[/green] JSON: {json_path}")

    # HTML (interactive graph)
    html_path = export_html(
        graph=graph,
        output_path=output_dir / "solution.html",
        title=f"Solution Map - Room {room_id}",
    )
    console.print(f"  [green]✓[/green] HTML: {html_path}")

    # Mermaid
    mmd_path = export_mermaid(
        graph=graph,
        output_path=output_dir / "solution.mmd",
    )
    console.print(f"  [green]✓[/green] Mermaid: {mmd_path}")

    # Markdown (AI or fallback)
    summary = await generate_markdown_summary(
        container_id=room_id,
        forms=solution["forms"],
        workflows=solution["workflows"],
        stats=stats,
        graph=graph,
    )
    if summary is None:
        summary = generate_basic_markdown(
            container_id=room_id,
            forms=solution["forms"],
            workflows=solution["workflows"],
            stats=stats,
        )
    md_path = export_markdown(summary, output_dir / "solution.md")
    console.print(f"  [green]✓[/green] Markdown: {md_path}")

    console.print(f"\n[bold green]✓ Complete![/bold green] Outputs saved to {output_dir}")


def main() -> None:
    """Entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
