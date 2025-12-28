"""CLI interface for Veoci Solution Mapper."""

import asyncio
import logging
import os
from pathlib import Path

import questionary
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from veoci_mapper.analyzer import analyze_solution, get_referenced_ids
from veoci_mapper.client import AuthenticationError, VeociClient
from veoci_mapper.fetcher import (
    fetch_all_task_type_definitions,
    fetch_external_forms,
    fetch_external_task_types,
    fetch_solution,
)
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


def configure_logging(debug: bool = False) -> None:
    """Configure logging level based on debug flag."""
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console)],
        force=True,  # Allow reconfiguration
    )


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

            # Extract actions from solution
            actions = solution.get("actions", {})

            # Fetch full definitions for solution task types
            task_types_list = solution.get("task_types", [])
            if task_types_list:
                console.print(
                    f"[dim]Fetching {len(task_types_list)} task type definitions...[/dim]"
                )
                # Extract container ID from each task type, or fall back to room_id
                task_type_refs = [
                    (
                        str(tt.get("categoryId")),
                        str(tt.get("container", {}).get("id", room_id))
                    )
                    for tt in task_types_list
                ]
                solution_task_types_dict = await fetch_all_task_type_definitions(
                    client,
                    task_type_refs,
                )
                solution_task_types = list(solution_task_types_dict.values())
                console.print(
                    f"[green]Fetched {len(solution_task_types)} "
                    "task type definitions[/green]"
                )
            else:
                solution_task_types = []

            # Analyze relationships (field + action)
            console.print("[dim]Analyzing relationships...[/dim]")
            relationships = analyze_solution(
                solution["form_definitions"],
                actions=actions,
                container_id=solution.get("container_id"),
            )
            console.print(f"[green]Found {len(relationships)} relationships[/green]")

            # Extract task type references from relationships
            task_type_refs = {
                (r.target_id, r.target_container_id)
                for r in relationships
                if r.target_type == "task_type" and r.target_container_id
            }

            # Fetch external task types (from other containers)
            # Use categoryId as canonical identifier (referenced by TASK fields)
            existing_task_type_ids = {str(tt.get("categoryId")) for tt in solution_task_types}
            external_task_types = await fetch_external_task_types(
                client,
                task_type_refs,
                existing_task_type_ids,
                room_id,
            )

            # Merge task types
            all_task_types = solution_task_types + external_task_types
            task_types_by_id = {str(tt.get("categoryId")): tt for tt in all_task_types}

            # Re-analyze with task types to extract relationships from task type fields
            # This may reveal additional task type references (recursive)
            if task_types_by_id:
                console.print("[dim]Analyzing task type relationships...[/dim]")
                task_type_relationships = analyze_solution(
                    solution["form_definitions"],
                    actions=actions,
                    container_id=solution.get("container_id"),
                    task_types=task_types_by_id,
                )

                # Extract any new task type references from task type fields
                new_task_type_refs = {
                    (r.target_id, r.target_container_id)
                    for r in task_type_relationships
                    if r.target_type == "task_type"
                    and r.target_container_id
                    and r.target_id not in task_types_by_id
                }

                # Fetch any newly discovered task types
                if new_task_type_refs:
                    console.print(
                        f"[dim]Fetching {len(new_task_type_refs)} "
                        "task types referenced by other task types...[/dim]"
                    )
                    more_task_types = await fetch_external_task_types(
                        client,
                        new_task_type_refs,
                        set(task_types_by_id.keys()),
                        room_id,
                    )
                    # Add to collections
                    all_task_types.extend(more_task_types)
                    for tt in more_task_types:
                        task_types_by_id[str(tt.get("categoryId"))] = tt

                # Merge unique relationships
                existing_rel_keys = {
                    (r.source_id, r.target_id, r.field_name, r.action_id)
                    for r in relationships
                }
                added_count = 0
                for rel in task_type_relationships:
                    key = (rel.source_id, rel.target_id, rel.field_name, rel.action_id)
                    if key not in existing_rel_keys:
                        relationships.append(rel)
                        existing_rel_keys.add(key)
                        added_count += 1
                if added_count > 0:
                    console.print(
                        f"[green]Found {added_count} additional relationships "
                        "from task types[/green]"
                    )

            # Fetch external forms
            existing_form_ids = {str(f.get("id") or f.get("formId")) for f in solution["forms"]}
            referenced_ids = get_referenced_ids(relationships)
            external_forms = await fetch_external_forms(client, referenced_ids, existing_form_ids)

            # Merge external forms
            all_forms = solution["forms"] + external_forms

            # Build graph
            console.print("[dim]Building graph...[/dim]")
            graph = build_graph(
                all_forms,
                solution["workflows"],
                relationships,
                task_types=all_task_types,
            )
            stats = get_graph_stats(graph)

            # Print stats
            console.print("\n[bold]Graph Statistics:[/bold]")

            # Build node type breakdown
            node_types = [f"{stats['form_count']} forms", f"{stats['workflow_count']} workflows"]
            if stats.get('task_type_count', 0) > 0:
                node_types.append(f"{stats['task_type_count']} task types")

            console.print(
                f"  Nodes: {stats['total_nodes']} ({', '.join(node_types)})"
            )

            # Count external nodes
            external_form_count = sum(1 for f in all_forms if f.get("external", False))
            external_task_type_count = sum(1 for tt in all_task_types if tt.get("external", False))
            if external_form_count > 0 or external_task_type_count > 0:
                external_parts = []
                if external_form_count > 0:
                    external_parts.append(f"{external_form_count} forms")
                if external_task_type_count > 0:
                    external_parts.append(f"{external_task_type_count} task types")
                console.print(f"  External: {', '.join(external_parts)}")

            console.print(f"  Edges: {stats['total_edges']}")
            console.print(f"  Isolated: {stats['isolated_nodes']}")
            console.print(f"  Components: {stats['connected_components']}")

            # Generate outputs
            console.print("\n[bold]Generating outputs...[/bold]")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate markdown first (needed for dashboard)
            summary = await generate_markdown_summary(
                container_id=room_id,
                forms=all_forms,
                workflows=solution["workflows"],
                stats=stats,
                graph=graph,
            )
            if summary is None:
                summary = generate_basic_markdown(
                    container_id=room_id,
                    forms=all_forms,
                    workflows=solution["workflows"],
                    stats=stats,
                )

            # Dashboard (replaces separate HTML)
            dashboard_path = export_dashboard(
                container_id=room_id,
                forms=all_forms,
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
                forms=all_forms,
                workflows=solution["workflows"],
                task_types=all_task_types,
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
            msg = f"[yellow]Couldn't open automatically. Open manually:[/yellow] {dashboard_path}"
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
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug logging (shows HTTP requests, etc.)",
    ),
) -> None:
    """Map a Veoci solution and generate visualizations."""

    # Configure logging based on debug flag
    configure_logging(debug)

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
