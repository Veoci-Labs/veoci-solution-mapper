"""Relationship analysis for Veoci forms and workflows."""

from typing import Any

from pydantic import BaseModel


class Relationship(BaseModel):
    """A relationship between forms or to workflows."""

    source_id: str
    source_name: str
    target_id: str
    target_name: str | None
    target_type: str  # "form" or "workflow"
    relationship_type: str  # REFERENCE, FORM_ENTRY, LOOKUP, WORKFLOW, ACTION_*
    field_name: str | None = None  # Optional - actions don't have field names
    # Action metadata (only populated for action-based relationships)
    action_id: str | None = None
    action_name: str | None = None
    trigger_type: str | None = None
    automatic: bool | None = None
    # Task type metadata (only populated for task_type relationships)
    target_container_id: str | None = None
    # Reference type metadata (only populated for REFERENCE relationships)
    is_subform: bool | None = None


# Relationship types
REFERENCE = "REFERENCE"
FORM_ENTRY = "FORM_ENTRY"
LOOKUP = "LOOKUP"
WORKFLOW = "WORKFLOW"
WORKFLOW_LOOKUP = "WORKFLOW_LOOKUP"
TASK = "TASK"

# Action-based relationship types
ACTION_CREATES_ENTRY = "ACTION_CREATES_ENTRY"
ACTION_INVOKES_WORKFLOW = "ACTION_INVOKES_WORKFLOW"
ACTION_CREATES_TASK = "ACTION_CREATES_TASK"
ACTION_LAUNCHES_TEMPLATE = "ACTION_LAUNCHES_TEMPLATE"
ACTION_LAUNCHES_PLAN = "ACTION_LAUNCHES_PLAN"


def extract_relationships(
    form_definition: dict[str, Any], container_id: str | None = None
) -> list[Relationship]:
    """Extract all relationships from a single form definition.

    Args:
        form_definition: A form definition dict from the Veoci API
        container_id: Optional container ID to detect external relationships

    Returns:
        List of Relationship objects found in this form
    """
    relationships: list[Relationship] = []
    form_id = str(form_definition.get("id", ""))
    form_name = form_definition.get("name", "Unknown")

    fields = form_definition.get("fields", {})
    if not isinstance(fields, dict):
        return relationships

    for field_id, field in fields.items():
        field_type = field.get("fieldType", "")
        field_name = field.get("name", f"Field {field_id}")

        # REFERENCE, FORM_ENTRY, LOOKUP - all use sourceFormId
        if field_type in {REFERENCE, FORM_ENTRY, LOOKUP}:
            source_form_id = field.get("sourceFormId")
            if source_form_id:
                source_form = field.get("sourceForm", {})
                target_name = source_form.get("name") if source_form else None

                # Extract is_subform for REFERENCE fields
                # Subforms require explicit referenceNewEntry=true
                # Absence or false means it's a regular Reference field
                is_subform = None
                if field_type == REFERENCE:
                    reference_new_entry = field.get("properties", {}).get("referenceNewEntry")
                    is_subform = bool(reference_new_entry)

                relationships.append(
                    Relationship(
                        source_id=form_id,
                        source_name=form_name,
                        target_id=str(source_form_id),
                        target_name=target_name,
                        target_type="form",
                        relationship_type=field_type,
                        field_name=field_name,
                        is_subform=is_subform,
                    )
                )

        # WORKFLOW and WORKFLOW_LOOKUP - both use properties.processId
        elif field_type in {WORKFLOW, WORKFLOW_LOOKUP}:
            properties = field.get("properties", {})
            process_id = properties.get("processId")
            process_name = properties.get("processName")

            if process_id:
                relationships.append(
                    Relationship(
                        source_id=form_id,
                        source_name=form_name,
                        target_id=str(process_id),
                        target_name=process_name,
                        target_type="workflow",
                        relationship_type=field_type,  # Preserve actual field type
                        field_name=field_name,
                    )
                )

        # TASK - uses properties.taskTypeFilter and taskTypeContainer
        elif field_type == TASK:
            properties = field.get("properties", {})
            task_type_id = properties.get("taskTypeFilter")
            task_type_container = properties.get("taskTypeContainer")

            if task_type_id:
                # Use taskTypeContainer - this is where the task type is defined
                # Task types can be defined at group level, not the room/solution level
                container_id_str = (
                    str(task_type_container) if task_type_container else None
                )
                relationships.append(
                    Relationship(
                        source_id=form_id,
                        source_name=form_name,
                        target_id=str(task_type_id),
                        target_name=None,  # Will be resolved during analysis
                        target_type="task_type",
                        relationship_type=TASK,
                        field_name=field_name,
                        target_container_id=container_id_str,
                    )
                )

    return relationships


def extract_action_relationships(
    source_id: str,
    source_name: str,
    source_type: str,
    actions: list[dict[str, Any]],
) -> list[Relationship]:
    """Extract relationships from custom actions.

    Args:
        source_id: The form or workflow ID that owns these actions
        source_name: The form or workflow name
        source_type: "form" or "workflow"
        actions: List of action definitions from the API

    Returns:
        List of Relationship objects derived from actions
    """
    relationships: list[Relationship] = []

    for action in actions:
        action_id = str(action.get("id", ""))
        action_name = action.get("name", "Unknown Action")
        consequence_type = action.get("consequenceType", "")
        trigger_type = action.get("eventType", "")
        automatic = action.get("automatic", False)

        # Skip REST API calls - not data relationships
        if consequence_type == "CALL_REST_API":
            continue

        params = action.get("consequenceParams", {})
        if not isinstance(params, dict):
            continue

        target_object_type = params.get("targetObjectType")

        # Skip emails and SQL reports (11=SQL, 16/21/22=Email variants)
        if target_object_type in [11, 16, 21, 22]:
            continue

        # Map targetObjectType to relationship type and target field
        relationship_type = None
        target_id = None
        target_type = None

        if target_object_type == 5:  # Form
            relationship_type = ACTION_CREATES_ENTRY
            target_type = "form"
            # Only create relationship if we have an explicit target form ID
            target_id = params.get("targetForm")

        elif target_object_type == 9:  # Workflow
            relationship_type = ACTION_INVOKES_WORKFLOW
            target_type = "workflow"
            target_id = params.get("targetProcess")

        elif target_object_type == 3:  # Task
            relationship_type = ACTION_CREATES_TASK
            target_type = "task_type"  # Task types, not task instances
            target_id = params.get("targetTaskType")

        # Add relationship if we found a valid target
        if relationship_type and target_id:
            # For task types, extract container ID from action params
            target_container_id = None
            if target_type == "task_type":
                # Check for container in action params (field name may vary)
                target_container_id = (
                    params.get("targetTaskTypeContainer")
                    or params.get("taskTypeContainer")
                    or params.get("targetContainer")
                )

            relationships.append(
                Relationship(
                    source_id=source_id,
                    source_name=source_name,
                    target_id=str(target_id),
                    target_name=None,  # Will be resolved during analysis
                    target_type=target_type,
                    relationship_type=relationship_type,
                    field_name=None,  # Actions don't have field names
                    action_id=action_id,
                    action_name=action_name,
                    trigger_type=trigger_type,
                    automatic=automatic,
                    target_container_id=str(target_container_id) if target_container_id else None,
                )
            )

        # Check for template/plan launches via targetContainerType
        target_container_type = params.get("targetContainerType")

        if target_container_type == 5:  # Room Template
            container_id = params.get("targetContainerId")
            if container_id:
                relationships.append(
                    Relationship(
                        source_id=source_id,
                        source_name=source_name,
                        target_id=str(container_id),
                        target_name=None,
                        target_type="template",
                        relationship_type=ACTION_LAUNCHES_TEMPLATE,
                        field_name=None,
                        action_id=action_id,
                        action_name=action_name,
                        trigger_type=trigger_type,
                        automatic=automatic,
                    )
                )

        elif target_container_type == 7:  # Plan
            container_id = params.get("targetContainerId")
            if container_id:
                relationships.append(
                    Relationship(
                        source_id=source_id,
                        source_name=source_name,
                        target_id=str(container_id),
                        target_name=None,
                        target_type="plan",
                        relationship_type=ACTION_LAUNCHES_PLAN,
                        field_name=None,
                        action_id=action_id,
                        action_name=action_name,
                        trigger_type=trigger_type,
                        automatic=automatic,
                    )
                )

    return relationships


def get_referenced_ids(relationships: list[Relationship]) -> set[str]:
    """Get all target IDs from relationships."""
    return {r.target_id for r in relationships if r.target_type == "form"}


def get_referenced_workflow_ids(relationships: list[Relationship]) -> set[str]:
    """Get all workflow IDs from relationships."""
    return {r.target_id for r in relationships if r.target_type == "workflow"}


def analyze_solution(
    form_definitions: list[dict[str, Any]],
    actions: dict[str, list[dict[str, Any]]] | None = None,
    container_id: str | None = None,
    task_types: dict[str, dict[str, Any]] | None = None,
) -> list[Relationship]:
    """Analyze all forms and task types in a solution and extract relationships.

    Args:
        form_definitions: List of form definition dicts
        actions: Optional dict mapping object IDs to their action lists
                 Format: {object_id: [action1, action2, ...]}
        container_id: Optional container ID for external relationship detection
        task_types: Optional dict mapping task_type_id -> task type definition
                    Format: {task_type_id: {"id": ..., "name": ..., "fields": {...}}}

    Returns:
        Combined list of all relationships, deduplicated
    """
    all_relationships: list[Relationship] = []

    # Process forms
    for form in form_definitions:
        # Extract field-based relationships
        relationships = extract_relationships(form, container_id=container_id)
        all_relationships.extend(relationships)

        # Extract action-based relationships if actions provided
        if actions:
            form_id = str(form.get("id", ""))
            form_name = form.get("name", "Unknown")
            form_actions = actions.get(form_id, [])

            if form_actions:
                action_relationships = extract_action_relationships(
                    source_id=form_id,
                    source_name=form_name,
                    source_type="form",
                    actions=form_actions,
                )
                all_relationships.extend(action_relationships)

    # Process task types (same pattern as forms)
    if task_types:
        for task_type_id, task_type in task_types.items():
            # Extract field-based relationships from task type
            # Task type structure: {"id": ..., "name": ..., "fields": {...}, "container": {...}}
            relationships = extract_relationships(
                task_type, container_id=container_id
            )
            all_relationships.extend(relationships)

            # Extract action-based relationships if actions provided
            if actions:
                task_type_name = task_type.get("name", "Unknown Task Type")
                task_type_actions = actions.get(task_type_id, [])

                if task_type_actions:
                    action_relationships = extract_action_relationships(
                        source_id=task_type_id,
                        source_name=task_type_name,
                        source_type="task_type",
                        actions=task_type_actions,
                    )
                    all_relationships.extend(action_relationships)

    # Deduplicate based on all fields
    seen = set()
    unique_relationships = []

    for rel in all_relationships:
        # Create tuple of all significant fields for deduplication
        # Include action_id to differentiate multiple actions with same targets
        key = (
            rel.source_id,
            rel.target_id,
            rel.target_type,
            rel.relationship_type,
            rel.field_name,
            rel.action_id,  # None for field relationships, unique for actions
        )

        if key not in seen:
            seen.add(key)
            unique_relationships.append(rel)

    return unique_relationships
