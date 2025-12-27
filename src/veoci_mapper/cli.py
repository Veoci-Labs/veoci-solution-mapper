"""CLI interface for Veoci Solution Mapper."""

import asyncio
import os
from pathlib import Path

import questionary
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from veoci_mapper.analyzer import analyze_solution
from veoci_mapper.client import AuthenticationError, VeociClient
from veoci_mapper.fetcher import fetch_solution
from veoci_mapper.graph import build_graph, get_graph_stats
from veoci_mapper.output import (
    export_dashboard,
    export_json,
    export_markdown,
    export_mermaid,
    generate_basic_markdown,
    generate_markdown_summary,
    open_in_browser,
)

load_dotenv()

app = typer.Typer(
    name="veoci-map",
    help="Map Veoci solution relationships and visualize form connections.",
)
console = Console()


async def run_map(
    room_id: str,
    token: str,
    base_url: str,
    output_dir: Path,
    auto_open: bool = True,
) -> None:
    """Main mapping logic."""

    console.print(Panel(f"Mapping solution in room [bold]{room_id}[/bold]"))

    try:
        async with VeociClient(token=token, base_url=base_url) as client:
            # Fetch solution data
            solution = await fetch_solution(client, room_id)

            # Analyze relationships
            console.print("[dim]Analyzing relationships...[/dim]")
            relationships = analyze_solution(solution["form_definitions"])
            console.print(f"[green]Found {len(relationships)} relationships[/green]")

            # Build graph
            console.print("[dim]Building graph...[/dim]")
            graph = build_graph(
                solution["forms"],
                solution["workflows"],
                relationships,
            )
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

            # Generate markdown first (needed for dashboard)
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

            # Dashboard (replaces separate HTML)
            dashboard_path = export_dashboard(
                container_id=room_id,
                forms=solution["forms"],
                workflows=solution["workflows"],
                relationships=relationships,
                stats=stats,
                graph=graph,
                markdown_summary=summary,
                output_path=output_dir / "solution.html",
            )
            console.print(f"  [green]✓[/green] Dashboard: {dashboard_path}")

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

            # Mermaid
            mmd_path = export_mermaid(
                graph=graph,
                output_path=output_dir / "solution.mmd",
            )
            console.print(f"  [green]✓[/green] Mermaid: {mmd_path}")

            # Also save markdown separately
            md_path = export_markdown(summary, output_dir / "solution.md")
            console.print(f"  [green]✓[/green] Markdown: {md_path}")

            console.print(f"\n[bold green]✓ Complete![/bold green] Outputs saved to {output_dir}")

            # Auto-open dashboard
            if auto_open:
                console.print("\n[dim]Opening dashboard in browser...[/dim]")
                if open_in_browser(dashboard_path):
                    console.print("[green]Dashboard opened![/green]")
                else:
                    msg = (
                        "[yellow]Couldn't open automatically. "
                        f"Open manually:[/yellow] {dashboard_path}"
                    )
                    console.print(msg)

    except AuthenticationError as e:
        console.print(f"[bold red]Authentication failed:[/bold red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


def run_interactive() -> None:
    """Run interactive wizard mode."""

    console.print(
        Panel.fit(
            "[bold]Veoci Solution Mapper[/bold]\nMap forms, workflows, and their relationships",
            border_style="blue",
        )
    )
    console.print()

    # Get base URL
    base_url = questionary.text(
        "Veoci API URL:",
        default=os.getenv("VEOCI_BASE_URL", "https://veoci.com"),
    ).ask()

    if base_url is None:  # User cancelled
        raise typer.Exit(0)

    # Get token (check env first)
    env_token = os.getenv("VEOCI_TOKEN")
    if env_token:
        use_env = questionary.confirm(
            "Use token from VEOCI_TOKEN environment variable?",
            default=True,
        ).ask()
        if use_env is None:
            raise typer.Exit(0)
        token = env_token if use_env else None
    else:
        token = None

    if not token:
        token = questionary.password(
            "Personal Access Token (PAT):",
        ).ask()

        if not token:
            console.print("[red]Token is required[/red]")
            raise typer.Exit(1)

    # Get room ID
    room_id = questionary.text(
        "Room ID to map:",
        validate=lambda x: len(x) > 0 or "Room ID is required",
    ).ask()

    if room_id is None:
        raise typer.Exit(0)

    # Get output directory
    output_str = questionary.text(
        "Output directory:",
        default="./output",
    ).ask()

    if output_str is None:
        raise typer.Exit(0)

    output_dir = Path(output_str)

    # Confirm
    console.print()
    console.print("[bold]Configuration:[/bold]")
    console.print(f"  API URL: {base_url}")
    console.print(f"  Room ID: {room_id}")
    console.print(f"  Output:  {output_dir}")
    console.print()

    confirm = questionary.confirm(
        "Proceed with mapping?",
        default=True,
    ).ask()

    if not confirm:
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    console.print()

    # Run the mapping
    asyncio.run(run_map(room_id, token, base_url, output_dir, auto_open=False))

    # Prompt to open dashboard
    open_now = questionary.confirm(
        "Open dashboard in browser?",
        default=True,
    ).ask()

    if open_now:
        dashboard_path = output_dir / "solution.html"
        if open_in_browser(dashboard_path):
            console.print("[green]Dashboard opened![/green]")
        else:
            msg = (
                "[yellow]Couldn't open automatically. "
                f"Open manually:[/yellow] {dashboard_path}"
            )
            console.print(msg)


@app.command()
def map(
    room_id: str = typer.Option(
        None,
        "--room-id",
        "-r",
        help="The Veoci room ID to map",
    ),
    token: str = typer.Option(
        None,
        "--token",
        "-t",
        envvar="VEOCI_TOKEN",
        help="Veoci Personal Access Token (or set VEOCI_TOKEN env var)",
    ),
    base_url: str = typer.Option(
        "https://veoci.com",
        "--base-url",
        "-u",
        envvar="VEOCI_BASE_URL",
        help="Veoci API base URL",
    ),
    output: Path = typer.Option(
        Path("./output"),
        "--output",
        "-o",
        help="Output directory for generated files",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Run in interactive mode with prompts",
    ),
    no_open: bool = typer.Option(
        False,
        "--no-open",
        help="Don't open dashboard in browser when complete",
    ),
) -> None:
    """Map a Veoci solution and generate visualizations."""

    # Interactive mode
    if interactive:
        run_interactive()
        return

    # Non-interactive mode requires room_id
    if not room_id:
        console.print("[bold red]Error:[/bold red] --room-id is required (or use --interactive)")
        raise typer.Exit(1)

    if not token:
        console.print(
            "[bold red]Error:[/bold red] No token provided. Use --token or set VEOCI_TOKEN"
        )
        raise typer.Exit(1)

    asyncio.run(run_map(room_id, token, base_url, output, auto_open=not no_open))


def main() -> None:
    """Entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
