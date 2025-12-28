"""Veoci Solution Mapper - CLI tool to map Veoci solution structure and dependencies."""

from veoci_mapper.analyzer import (
    FORM_ENTRY,
    LOOKUP,
    REFERENCE,
    TASK,
    WORKFLOW,
    WORKFLOW_LOOKUP,
    Relationship,
    analyze_solution,
    extract_relationships,
    get_referenced_workflow_ids,
)
from veoci_mapper.client import (
    AuthenticationError,
    NotFoundError,
    VeociClient,
    VeociClientError,
)
from veoci_mapper.fetcher import (
    fetch_forms_list,
    fetch_solution,
    fetch_workflows_list,
)
from veoci_mapper.graph import (
    build_graph,
    get_graph_stats,
    get_node_neighbors,
)

__version__ = "0.1.0"

__all__ = [
    "VeociClient",
    "VeociClientError",
    "AuthenticationError",
    "NotFoundError",
    "fetch_solution",
    "fetch_forms_list",
    "fetch_workflows_list",
    "Relationship",
    "extract_relationships",
    "analyze_solution",
    "REFERENCE",
    "FORM_ENTRY",
    "LOOKUP",
    "TASK",
    "WORKFLOW",
    "WORKFLOW_LOOKUP",
    "get_referenced_workflow_ids",
    "build_graph",
    "get_graph_stats",
    "get_node_neighbors",
]
