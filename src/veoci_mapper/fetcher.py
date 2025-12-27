"""Batch fetcher for Veoci forms, workflows, and their definitions."""

import asyncio
from typing import Any

from rich.console import Console
from rich.progress import Progress, TaskID

from veoci_mapper.client import VeociClient

console = Console()


async def fetch_forms_list(client: VeociClient, container_id: str) -> list[dict[str, Any]]:
    """Fetch list of all forms in a container."""
    return await client.get("/forms", params={"c": container_id})


async def fetch_form_definition(client: VeociClient, form_id: str) -> dict[str, Any]:
    """Fetch full form definition including field schema."""
    return await client.get(f"/forms/{form_id}")


async def fetch_workflows_list(client: VeociClient, container_id: str) -> list[dict[str, Any]]:
    """Fetch list of all workflows in a container."""
    return await client.get("/workflows", params={"c": container_id})


async def fetch_all_form_definitions(
    client: VeociClient,
    forms: list[dict[str, Any]],
    max_concurrent: int = 5,
) -> list[dict[str, Any]]:
    """
    Fetch full definitions for all forms in parallel.

    Uses semaphore to limit concurrent requests.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_semaphore(form: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            form_id = form.get("id") or form.get("formId")
            try:
                definition = await fetch_form_definition(client, str(form_id))
                return definition
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to fetch form {form_id}: {e}[/yellow]")
                return form  # Return basic info if definition fetch fails

    tasks = [fetch_with_semaphore(form) for form in forms]
    return await asyncio.gather(*tasks)


async def fetch_solution(
    client: VeociClient,
    container_id: str,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """
    Fetch complete solution data from a container.

    Returns:
        dict with keys: forms, form_definitions, workflows, container_id
    """
    # Track progress if provided
    task_id: TaskID | None = None
    if progress:
        task_id = progress.add_task("Fetching solution...", total=3)

    def advance() -> None:
        if progress and task_id is not None:
            progress.advance(task_id)

    # 1. Fetch forms list
    console.print("[dim]Fetching forms list...[/dim]")
    forms = await fetch_forms_list(client, container_id)
    console.print(f"[green]Found {len(forms)} forms[/green]")
    advance()

    # 2. Fetch workflows list
    console.print("[dim]Fetching workflows list...[/dim]")
    workflows = await fetch_workflows_list(client, container_id)
    console.print(f"[green]Found {len(workflows)} workflows[/green]")
    advance()

    # 3. Fetch all form definitions in parallel
    console.print(f"[dim]Fetching {len(forms)} form definitions...[/dim]")
    form_definitions = await fetch_all_form_definitions(client, forms)
    console.print(f"[green]Fetched {len(form_definitions)} form definitions[/green]")
    advance()

    return {
        "container_id": container_id,
        "forms": forms,
        "form_definitions": form_definitions,
        "workflows": workflows,
    }
