"""Build NetworkX graph from solution relationships."""

from typing import Any

import networkx as nx

from veoci_mapper.analyzer import Relationship


def build_graph(
    forms: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    relationships: list[Relationship],
    task_types: list[dict[str, Any]] | None = None,
    solution_container_id: str | None = None,
) -> nx.DiGraph:
    """
    Build a directed graph from forms, workflows, task types, and their relationships.

    Nodes represent forms, workflows, and task types.
    Edges represent relationships between them.
    """
    graph = nx.DiGraph()
    task_types = task_types or []

    # Add form nodes
    for form in forms:
        form_id = str(form.get("id") or form.get("formId"))
        is_external = form.get("external", False)
        # External forms may have their own containerId, otherwise use solution container
        container_id = form.get("containerId") or solution_container_id
        graph.add_node(
            form_id,
            name=form.get("name", "Unknown"),
            node_type="form",
            external=is_external,
            container_id=str(container_id) if container_id else None,
        )

    # Add workflow nodes
    for workflow in workflows:
        workflow_id = str(workflow.get("id") or workflow.get("processId"))
        # External workflows may have their own containerId, otherwise use solution container
        container_id = workflow.get("containerId") or solution_container_id
        graph.add_node(
            workflow_id,
            name=workflow.get("name", "Unknown"),
            node_type="workflow",
            container_id=str(container_id) if container_id else None,
        )

    # Add task type nodes
    for task_type in task_types:
        # Use categoryId as the canonical identifier (referenced by TASK fields)
        task_type_id = str(task_type.get("categoryId"))
        is_external = task_type.get("external", False)
        container_id = task_type.get("container", {}).get("id")
        graph.add_node(
            task_type_id,
            name=task_type.get("name", "Unknown"),
            node_type="task_type",
            external=is_external,
            container_id=str(container_id) if container_id else None,
        )

    # Add relationship edges
    for rel in relationships:
        edge_data = {
            "relationship_type": rel.relationship_type,
            "field_name": rel.field_name,
            "target_type": rel.target_type,
        }

        # Add action metadata if present
        if rel.action_id:
            edge_data["action_id"] = rel.action_id
            edge_data["action_name"] = rel.action_name
            edge_data["trigger_type"] = rel.trigger_type
            edge_data["automatic"] = rel.automatic
            edge_data["edge_category"] = "action"
        else:
            edge_data["edge_category"] = "field"

        # Add is_subform if present (for REFERENCE relationships)
        if rel.is_subform is not None:
            edge_data["is_subform"] = rel.is_subform

        graph.add_edge(rel.source_id, rel.target_id, **edge_data)

    return graph


def get_graph_stats(graph: nx.DiGraph) -> dict[str, Any]:
    """Get statistics about the solution graph."""
    form_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_type") == "form"]
    workflow_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_type") == "workflow"]
    task_type_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_type") == "task_type"]

    # Count edges by relationship type and category
    edge_types: dict[str, int] = {}
    action_edges = 0
    field_edges = 0
    for _, _, data in graph.edges(data=True):
        rel_type = data.get("relationship_type", "unknown")
        edge_types[rel_type] = edge_types.get(rel_type, 0) + 1

        # Count by edge category
        if data.get("edge_category") == "action":
            action_edges += 1
        elif data.get("edge_category") == "field":
            field_edges += 1

    # Find isolated nodes (no connections)
    isolated = list(nx.isolates(graph))

    # Find most connected nodes
    in_degrees = sorted(graph.in_degree(), key=lambda x: x[1], reverse=True)[:5]
    out_degrees = sorted(graph.out_degree(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_nodes": graph.number_of_nodes(),
        "form_count": len(form_nodes),
        "workflow_count": len(workflow_nodes),
        "task_type_count": len(task_type_nodes),
        "total_edges": graph.number_of_edges(),
        "action_edges": action_edges,
        "field_edges": field_edges,
        "edge_types": edge_types,
        "isolated_nodes": len(isolated),
        "connected_components": nx.number_weakly_connected_components(graph),
        "most_referenced": [
            {"id": n, "name": graph.nodes[n].get("name"), "count": c}
            for n, c in in_degrees
            if c > 0
        ],
        "most_referencing": [
            {"id": n, "name": graph.nodes[n].get("name"), "count": c}
            for n, c in out_degrees
            if c > 0
        ],
    }


def get_node_neighbors(graph: nx.DiGraph, node_id: str) -> dict[str, Any]:
    """Get information about a node's connections."""
    if node_id not in graph:
        return {"error": f"Node {node_id} not found"}

    node_data = graph.nodes[node_id]

    # Incoming edges (who references this node)
    predecessors = []
    for pred in graph.predecessors(node_id):
        edge_data = graph.edges[pred, node_id]
        predecessors.append(
            {
                "id": pred,
                "name": graph.nodes[pred].get("name"),
                "relationship": edge_data.get("relationship_type"),
                "field": edge_data.get("field_name"),
            }
        )

    # Outgoing edges (what this node references)
    successors = []
    for succ in graph.successors(node_id):
        edge_data = graph.edges[node_id, succ]
        successors.append(
            {
                "id": succ,
                "name": graph.nodes[succ].get("name"),
                "relationship": edge_data.get("relationship_type"),
                "field": edge_data.get("field_name"),
            }
        )

    return {
        "id": node_id,
        "name": node_data.get("name"),
        "type": node_data.get("node_type"),
        "referenced_by": predecessors,
        "references": successors,
    }
