"""Mermaid diagram export."""

from pathlib import Path
import networkx as nx


def export_mermaid(
    graph: nx.DiGraph,
    output_path: Path,
) -> Path:
    """Export Mermaid flowchart diagram.

    Args:
        graph: NetworkX directed graph
        output_path: Path to save .mmd file

    Returns:
        Path to created Mermaid file
    """
    lines = ["graph TD"]

    # Node definitions
    for node_id, attrs in graph.nodes(data=True):
        label = attrs.get("label", node_id)
        node_type = attrs.get("type", "unknown")

        # Shape based on type
        if node_type == "workflow":
            shape_start, shape_end = "[[", "]]"  # subprocess
        else:
            shape_start, shape_end = "[", "]"  # rectangle

        # Sanitize label for Mermaid
        safe_label = label.replace('"', "'")
        lines.append(f'    {node_id}{shape_start}"{safe_label}"{shape_end}')

    # Edge definitions
    for source, target, attrs in graph.edges(data=True):
        edge_label = attrs.get("type", "")
        if edge_label:
            lines.append(f'    {source} -->|{edge_label}| {target}')
        else:
            lines.append(f'    {source} --> {target}')

    content = "\n".join(lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    return output_path
