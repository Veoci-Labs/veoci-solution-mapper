"""JSON export for solution map."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from veoci_mapper.analyzer import Relationship


class SolutionExport(BaseModel):
    """Pydantic model for JSON export."""
    container_id: str
    forms: list[dict[str, Any]]
    workflows: list[dict[str, Any]]
    task_types: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    statistics: dict[str, Any]


def export_json(
    container_id: str,
    forms: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    task_types: list[dict[str, Any]],
    relationships: list[Relationship],
    stats: dict[str, Any],
    output_path: Path,
) -> Path:
    """
    Export solution map as JSON.

    Returns the path to the created file.
    """
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build export structure
    export = SolutionExport(
        container_id=container_id,
        forms=[{
            "id": str(f.get("id") or f.get("formId")),
            "name": f.get("name", "Unknown"),
            "external": f.get("external", False),
        } for f in forms],
        workflows=[{
            "id": str(w.get("id") or w.get("processId")),
            "name": w.get("name", "Unknown"),
        } for w in workflows],
        task_types=[{
            "id": str(tt.get("categoryId")),
            "name": tt.get("name", "Unknown"),
            "external": tt.get("external", False),
        } for tt in task_types],
        relationships=[r.model_dump() for r in relationships],
        statistics=stats,
    )

    # Write JSON with pretty formatting
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export.model_dump(), f, indent=2, ensure_ascii=False)

    return output_path
