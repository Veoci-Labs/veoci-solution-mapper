"""Batch fetcher for Veoci forms, workflows, and their definitions."""

import asyncio
import logging
from typing import Any

from rich.console import Console
from rich.progress import Progress, TaskID

from veoci_mapper.client import VeociClient

console = Console()
logger = logging.getLogger(__name__)


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


async def fetch_external_forms(
    client: VeociClient,
    form_ids: set[str],
    existing_form_ids: set[str],
    max_concurrent: int = 5,
) -> list[dict[str, Any]]:
    """
    Fetch forms that are referenced but not in the main container.

    Returns forms with an 'external' flag set to True.
    """
    missing_ids = form_ids - existing_form_ids

    if not missing_ids:
        return []

    console.print(f"[dim]Fetching {len(missing_ids)} external forms...[/dim]")

    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_one(form_id: str) -> dict[str, Any] | None:
        async with semaphore:
            try:
                form = await client.get(f"/forms/{form_id}")
                form['external'] = True  # Mark as external
                return form
            except Exception as e:
                console.print(f"[yellow]Could not fetch external form {form_id}: {e}[/yellow]")
                return None

    tasks = [fetch_one(fid) for fid in missing_ids]
    results = await asyncio.gather(*tasks)

    external_forms = [f for f in results if f is not None]
    console.print(f"[green]Fetched {len(external_forms)} external forms[/green]")

    return external_forms


async def fetch_object_actions(
    client: VeociClient,
    object_id: str,
) -> list[dict[str, Any]]:
    """Fetch custom actions for a single form or workflow."""
    return await client.get(f"/objects/{object_id}/actions")


async def fetch_action_builder(
    client: VeociClient,
    action_id: str,
) -> dict[str, Any] | None:
    """Fetch full action configuration from builder endpoint."""
    try:
        return await client.get(f"/actions/{action_id}/builder")
    except Exception as e:
        logger.warning(f"Failed to fetch action builder {action_id}: {e}")
        return None


async def fetch_all_object_actions(
    client: VeociClient,
    object_ids: list[str],
    max_concurrent: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """
    Fetch actions for multiple objects in parallel.

    Two-phase fetch:
    1. Get basic action list from /objects/{id}/actions
    2. For mappable actions, fetch full config from /actions/{id}/builder

    Returns dict mapping object_id -> list of actions.
    Uses semaphore to limit concurrent requests.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    # Phase 1: Fetch basic action lists
    async def fetch_with_semaphore(object_id: str) -> tuple[str, list[dict[str, Any]]]:
        async with semaphore:
            try:
                actions = await fetch_object_actions(client, object_id)
                return (object_id, actions)
            except Exception as e:
                msg = (
                    f"[yellow]Warning: Failed to fetch actions for object {object_id}: "
                    f"{e}[/yellow]"
                )
                console.print(msg)
                return (object_id, [])  # Return empty list if fetch fails

    tasks = [fetch_with_semaphore(obj_id) for obj_id in object_ids]
    results = await asyncio.gather(*tasks)
    actions_by_object = dict(results)

    # Phase 2: Fetch builder details for mappable actions
    # targetObjectType: 3=Task, 5=Form, 9=Workflow
    # Skip REST API calls - they don't create cross-object relationships
    mappable_types = {3, 5, 9}
    actions_to_enrich = []

    for object_id, actions in actions_by_object.items():
        for action in actions:
            # targetObjectType is inside consequenceParams, not at root level
            params = action.get("consequenceParams") or {}
            target_type = params.get("targetObjectType")
            consequence_type = action.get("consequenceType")

            # Skip REST API actions (no cross-object target)
            if consequence_type == "CALL_REST_API":
                continue

            # Only enrich actions with mappable targets
            if target_type in mappable_types:
                actions_to_enrich.append((object_id, action))
            else:
                # Debug: log why we're not enriching
                if target_type is None:
                    logger.debug(
                        f"Action {action.get('id')} on {object_id}: "
                        f"targetObjectType is None - may need builder fetch"
                    )

    if actions_to_enrich:
        logger.info(
            f"Fetching builder details for {len(actions_to_enrich)} mappable actions "
            f"(out of {sum(len(acts) for acts in actions_by_object.values())} total)"
        )

        async def fetch_builder_with_semaphore(
            object_id: str,
            action: dict[str, Any]
        ) -> tuple[str, str, dict[str, Any] | None]:
            async with semaphore:
                action_id = str(action.get("id"))
                builder = await fetch_action_builder(client, action_id)
                return (object_id, action_id, builder)

        builder_tasks = [
            fetch_builder_with_semaphore(obj_id, action)
            for obj_id, action in actions_to_enrich
        ]
        builder_results = await asyncio.gather(*builder_tasks)

        # Replace basic action data with full builder response
        enriched_count = 0
        for object_id, action_id, builder in builder_results:
            if builder is None:
                continue

            # Find and replace the action in the original list
            for i, action in enumerate(actions_by_object[object_id]):
                if str(action.get("id")) == action_id:
                    actions_by_object[object_id][i] = builder
                    enriched_count += 1
                    break

        logger.info(f"Successfully enriched {enriched_count} actions with builder details")

    return actions_by_object


async def fetch_solution(
    client: VeociClient,
    container_id: str,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """
    Fetch complete solution data from a container.

    Returns:
        dict with keys: forms, form_definitions, workflows, actions, container_id
    """
    # Track progress if provided
    task_id: TaskID | None = None
    if progress:
        task_id = progress.add_task("Fetching solution...", total=4)

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

    # 4. Fetch custom actions for all forms and workflows
    form_ids = [str(f.get("id") or f.get("formId")) for f in forms]
    workflow_ids = [str(w.get("id")) for w in workflows if w.get("id")]
    all_object_ids = form_ids + workflow_ids

    msg = (
        f"[dim]Fetching actions for {len(all_object_ids)} objects "
        f"({len(form_ids)} forms, {len(workflow_ids)} workflows)...[/dim]"
    )
    console.print(msg)
    actions = await fetch_all_object_actions(client, all_object_ids)

    # Count actions by type for logging
    form_action_count = sum(len(actions.get(fid, [])) for fid in form_ids)
    workflow_action_count = sum(len(actions.get(wid, [])) for wid in workflow_ids)
    console.print(
        f"[green]Fetched {form_action_count} form actions, "
        f"{workflow_action_count} workflow actions[/green]"
    )

    # Debug: Check action data structure
    if actions:
        sample_obj_id = next(iter(actions.keys()))
        sample_actions = actions[sample_obj_id]
        if sample_actions:
            sample = sample_actions[0]
            logger.debug(f"Sample action from {sample_obj_id}: {list(sample.keys())}")
            logger.debug(f"  targetObjectType: {sample.get('targetObjectType')}")
            logger.debug(f"  consequenceParams: {sample.get('consequenceParams', {})}")

    advance()

    return {
        "container_id": container_id,
        "forms": forms,
        "form_definitions": form_definitions,
        "workflows": workflows,
        "actions": actions,
    }
