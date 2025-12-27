"""Visual graph export (HTML)."""

from pathlib import Path
import json
import networkx as nx


def export_html(
    graph: nx.DiGraph,
    output_path: Path,
    title: str = "Solution Graph",
) -> Path:
    """Export interactive HTML graph visualization.

    Args:
        graph: NetworkX directed graph
        output_path: Path to save HTML file
        title: Page title

    Returns:
        Path to created HTML file
    """
    # Generate vis.js graph data
    nodes = []
    for node_id, attrs in graph.nodes(data=True):
        nodes.append({
            "id": node_id,
            "label": attrs.get("label", node_id),
            "title": attrs.get("title", ""),  # tooltip
            "group": attrs.get("type", "unknown"),
        })

    edges = []
    for source, target, attrs in graph.edges(data=True):
        edges.append({
            "from": source,
            "to": target,
            "label": attrs.get("type", ""),
            "arrows": "to",
        })

    # Serialize to JSON for embedding
    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)

    # HTML template with vis.js
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: sans-serif; }}
        #graph {{ width: 100vw; height: 100vh; }}
        .info {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(255,255,255,0.9);
            padding: 10px;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            z-index: 1000;
        }}
    </style>
</head>
<body>
    <div class="info">
        <strong>{title}</strong><br>
        Nodes: {len(nodes)} | Edges: {len(edges)}
    </div>
    <div id="graph"></div>
    <script>
        const nodes = new vis.DataSet({nodes_json});
        const edges = new vis.DataSet({edges_json});

        const container = document.getElementById('graph');
        const data = {{ nodes, edges }};
        const options = {{
            nodes: {{
                shape: 'box',
                margin: 10,
                widthConstraint: {{ maximum: 200 }},
            }},
            edges: {{
                smooth: {{ type: 'cubicBezier' }},
            }},
            physics: {{
                enabled: true,
                stabilization: {{ iterations: 200 }},
            }},
            groups: {{
                form: {{ color: {{ background: '#97C2FC' }} }},
                workflow: {{ color: {{ background: '#FFCC66' }} }},
            }},
        }};

        new vis.Network(container, data, options);
    </script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    return output_path
