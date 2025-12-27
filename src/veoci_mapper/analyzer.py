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
    relationship_type: str  # REFERENCE, FORM_ENTRY, LOOKUP, WORKFLOW
    field_name: str


# Relationship types
REFERENCE = "REFERENCE"
FORM_ENTRY = "FORM_ENTRY"
LOOKUP = "LOOKUP"
WORKFLOW = "WORKFLOW"


def extract_relationships(form_definition: dict[str, Any]) -> list[Relationship]:
    """Extract all relationships from a single form definition.

    Args:
        form_definition: A form definition dict from the Veoci API

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

                relationships.append(
                    Relationship(
                        source_id=form_id,
                        source_name=form_name,
                        target_id=str(source_form_id),
                        target_name=target_name,
                        target_type="form",
                        relationship_type=field_type,
                        field_name=field_name,
                    )
                )

        # WORKFLOW - uses properties.processId
        elif field_type == WORKFLOW:
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
                        relationship_type=WORKFLOW,
                        field_name=field_name,
                    )
                )

    return relationships


def get_referenced_ids(relationships: list[Relationship]) -> set[str]:
    """Get all target IDs from relationships."""
    return {r.target_id for r in relationships if r.target_type == "form"}


def analyze_solution(form_definitions: list[dict[str, Any]]) -> list[Relationship]:
    """Analyze all forms in a solution and extract relationships.

    Args:
        form_definitions: List of form definition dicts

    Returns:
        Combined list of all relationships, deduplicated
    """
    all_relationships: list[Relationship] = []

    for form in form_definitions:
        relationships = extract_relationships(form)
        all_relationships.extend(relationships)

    # Deduplicate based on all fields
    seen = set()
    unique_relationships = []

    for rel in all_relationships:
        # Create tuple of all significant fields for deduplication
        key = (
            rel.source_id,
            rel.target_id,
            rel.target_type,
            rel.relationship_type,
            rel.field_name,
        )

        if key not in seen:
            seen.add(key)
            unique_relationships.append(rel)

    return unique_relationships
