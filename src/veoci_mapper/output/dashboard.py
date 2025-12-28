"""Unified HTML dashboard with tabs for graph, forms, and AI summary."""

import json
import webbrowser
from pathlib import Path
from typing import Any

import markdown
import networkx as nx
from rich.console import Console

console = Console()


def wrap_label(name: str, max_chars: int = 25) -> str:
    """Wrap label text and truncate if needed for external node labels."""
    words = name.split()
    lines = []
    current_line = ""

    for word in words:
        if len(current_line) + len(word) + 1 <= max_chars:
            current_line = f"{current_line} {word}".strip()
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    # Truncate to 3 lines max
    if len(lines) > 3:
        lines = lines[:3]
        lines[2] = lines[2][:max_chars - 3] + "..."

    return "\n".join(lines)


def _generate_table_rows(forms_table: list[dict[str, Any]]) -> str:
    """Generate HTML table rows for forms/workflows."""
    rows = []
    for item in sorted(forms_table, key=lambda x: x["name"]):
        badge_class = f"type-{item['type'].lower()}"
        external_badge = (
            "<span class='type-badge type-external'>External</span>" if item.get("external") else ""
        )
        rows.append(
            f"<tr data-id='{item['id']}' onclick='showNodeDetails(\"{item['id']}\")'>"
            f"<td>{item['name']}</td>"
            f"<td><span class='type-badge {badge_class}'>{item['type']}</span>{external_badge}</td>"
            f"<td>{item['refs_out']}</td>"
            f"<td>{item['refs_in']}</td>"
            f"<td style='color:#999;font-size:12px'>{item['id']}</td>"
            f"</tr>"
        )
    return "".join(rows)


def generate_dashboard_html(
    container_id: str,
    forms: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    relationships: list[Any],  # Relationship objects
    stats: dict[str, Any],
    graph: nx.DiGraph,
    markdown_summary: str,
) -> str:
    """Generate unified HTML dashboard with tabs."""

    # Build nodes and edges data for vis.js
    nodes_data = []
    for node_id, data in graph.nodes(data=True):
        node_type = data.get("node_type", "form")
        is_external = data.get("external", False)
        name = data.get("name", node_id)

        # Color: orange for external forms, blue for local forms, purple for workflows, teal for task types
        if node_type == "form":
            color = "#ff9800" if is_external else "#4fc3f7"
            shape = "dot"
            size = 30
            font_config = {"vadjust": 20}
        elif node_type == "workflow":
            color = "#ba68c8"
            shape = "square"
            size = 25
            font_config = {"vadjust": 20}
        elif node_type == "task_type":
            color = "#80cbc4" if is_external else "#26a69a"
            shape = "diamond"
            size = 30
            font_config = {"vadjust": 25}
        else:
            color = "#ba68c8"
            shape = "dot"
            size = 30
            font_config = {"vadjust": 50}

        node_def = {
            "id": node_id,
            "label": wrap_label(name),
            "title": f"{name} ({node_type}){' - External' if is_external else ''}",
            "color": color,
            "shape": shape,
            "size": size,
            "font": font_config,
        }

        nodes_data.append(node_def)

    edges_data = []
    for source, target, data in graph.edges(data=True):
        edge_category = data.get("edge_category", "field")
        rel_type = data.get("relationship_type", "")

        # Build edge based on category
        if edge_category == "action":
            # Action-based relationship
            action_name = data.get("action_name", "Unknown Action")
            trigger_type = data.get("trigger_type", "UNKNOWN")
            automatic = data.get("automatic", False)
            auto_text = "Yes" if automatic else "No"

            edges_data.append(
                {
                    "from": source,
                    "to": target,
                    "label": "ACT",
                    "title": f"{action_name}\nTrigger: {trigger_type}\nAutomatic: {auto_text}",
                    "arrows": "to",
                    "dashes": True,
                    "color": {"color": "#ff9800", "highlight": "#f57c00"},
                    "width": 2,
                    "edge_category": "action",
                    "action_name": action_name,
                    "trigger_type": trigger_type,
                    "automatic": automatic,
                }
            )
        else:
            # Field-based relationship
            field_name = data.get("field_name", "")
            edges_data.append(
                {
                    "from": source,
                    "to": target,
                    "label": rel_type[:3].upper() if rel_type else "",
                    "title": f"{rel_type}: {field_name}",
                    "arrows": "to",
                    "dashes": False,
                    "color": {"color": "#2196f3", "highlight": "#1976d2"},
                    "width": 2,
                    "edge_category": "field",
                    "relationship_type": rel_type,
                    "field_name": field_name,
                    "is_subform": data.get("is_subform"),
                }
            )

    # Build forms table data including task types
    forms_table = []
    for form in forms:
        form_id = str(form.get("id") or form.get("formId"))
        name = form.get("name", "Unknown")
        is_external = form.get("external", False)

        # Count relationships
        refs_out = len(list(graph.successors(form_id))) if form_id in graph else 0
        refs_in = len(list(graph.predecessors(form_id))) if form_id in graph else 0

        forms_table.append(
            {
                "id": form_id,
                "name": name,
                "type": "Form",
                "refs_out": refs_out,
                "refs_in": refs_in,
                "external": is_external,
            }
        )

    for workflow in workflows:
        wf_id = str(workflow.get("id") or workflow.get("processId"))
        name = workflow.get("name", "Unknown")
        refs_out = len(list(graph.successors(wf_id))) if wf_id in graph else 0
        refs_in = len(list(graph.predecessors(wf_id))) if wf_id in graph else 0

        forms_table.append(
            {
                "id": wf_id,
                "name": name,
                "type": "Workflow",
                "refs_out": refs_out,
                "refs_in": refs_in,
            }
        )

    # Add task types from graph
    for node_id, data in graph.nodes(data=True):
        if data.get("node_type") == "task_type":
            is_external = data.get("external", False)
            refs_out = len(list(graph.successors(node_id))) if node_id in graph else 0
            refs_in = len(list(graph.predecessors(node_id))) if node_id in graph else 0

            forms_table.append(
                {
                    "id": node_id,
                    "name": data.get("name", "Unknown"),
                    "type": "TaskType",
                    "refs_out": refs_out,
                    "refs_in": refs_in,
                    "external": is_external,
                }
            )

    # Convert markdown to HTML using markdown library
    markdown_html = markdown.markdown(markdown_summary, extensions=["tables", "fenced_code"])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Solution Map - Room {container_id}</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
            color: #333;
        }}
        .header {{
            background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
            color: white;
            padding: 12px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }}
        .header-left {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .header h1 {{
            font-size: 18px;
            font-weight: 500;
            margin: 0;
        }}
        .header .subtitle {{
            opacity: 0.8;
            font-size: 14px;
            margin: 0;
        }}
        .stats {{
            display: flex;
            gap: 15px;
            margin: 0;
        }}
        .stat {{
            background: rgba(255,255,255,0.15);
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 12px;
        }}
        .tabs {{
            background: white;
            display: flex;
            border-bottom: 1px solid #e0e0e0;
            padding: 0 20px;
        }}
        .tab {{
            padding: 15px 25px;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            font-weight: 500;
            color: #666;
            transition: all 0.2s;
        }}
        .tab:hover {{
            color: #1a237e;
        }}
        .tab.active {{
            color: #1a237e;
            border-bottom-color: #1a237e;
        }}
        .content {{
            display: none;
            height: calc(100vh - 105px);
            overflow: auto;
        }}
        .content.active {{
            display: block;
        }}
        .graph-container {{
            display: flex;
            height: calc(100% - 49px);
        }}
        .graph-panel {{
            width: 0;
            min-width: 0;
            background: white;
            border-right: 1px solid #e0e0e0;
            overflow: hidden;
            transition: width 0.2s ease, min-width 0.2s ease;
        }}
        .graph-panel.active {{
            width: 300px;
            min-width: 300px;
        }}
        .panel-header {{
            padding: 12px 15px;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #f8f9fa;
        }}
        .panel-header h3 {{
            margin: 0;
            font-size: 14px;
            font-weight: 600;
            color: #1a237e;
        }}
        .panel-close {{
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: #666;
            padding: 0 5px;
        }}
        .panel-close:hover {{
            color: #333;
        }}
        .panel-body {{
            padding: 15px;
            overflow-y: auto;
            height: calc(100% - 50px);
        }}
        .panel-section {{
            margin-bottom: 20px;
        }}
        .panel-section + .panel-section {{
            border-top: 2px solid #e0e0e0;
            padding-top: 20px;
            margin-top: 20px;
        }}
        .panel-section h4 {{
            font-size: 12px;
            text-transform: uppercase;
            color: #666;
            margin: 0 0 10px 0;
        }}
        .panel-subsection {{
            margin-bottom: 15px;
            padding: 10px;
            border-radius: 6px;
        }}
        .panel-subsection.actions {{
            background: #fff8e1;
            border-left: 3px solid #ff9800;
        }}
        .panel-subsection.fields {{
            background: #e3f2fd;
            border-left: 3px solid #2196f3;
        }}
        .panel-subsection h5 {{
            font-size: 11px;
            font-weight: 700;
            margin: 0 0 10px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .panel-subsection.actions h5 {{
            color: #e65100;
        }}
        .panel-subsection.fields h5 {{
            color: #1565c0;
        }}
        .panel-section .panel-ref-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .panel-section .panel-ref-item {{
            padding: 10px;
            background: #f5f5f5;
            border-radius: 4px;
            margin-bottom: 8px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .panel-section .panel-ref-item:hover {{
            background: #e3f2fd;
            transform: translateX(4px);
        }}
        .panel-section .panel-ref-name {{
            font-weight: 600;
            color: #333;
            display: block;
            margin-bottom: 6px;
        }}
        .panel-section .panel-ref-meta {{
            font-size: 11px;
            color: #666;
            line-height: 1.6;
        }}
        .panel-section .panel-ref-meta div {{
            margin-bottom: 2px;
        }}
        .panel-section .panel-no-refs {{
            color: #999;
            font-style: italic;
            font-size: 13px;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: 600;
            margin-left: 6px;
        }}
        .badge.action {{
            background: #ff9800;
            color: white;
        }}
        .badge.reference {{
            background: #2196f3;
            color: white;
        }}
        #graph {{
            flex: 1;
            height: 100%;
            background: white;
        }}
        .graph-container {{
            position: relative;
        }}
        .graph-legend {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            z-index: 100;
        }}
        .legend-title {{
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
            color: #666;
        }}
        .legend-item:last-child {{
            margin-bottom: 0;
        }}
        .legend-color {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
            flex-shrink: 0;
        }}
        .table-toolbar {{
            padding: 12px 20px;
            background: white;
            border-bottom: 1px solid #e0e0e0;
        }}
        .table-container {{
            padding: 0 20px 20px 20px;
            background: white;
            height: calc(100% - 57px);
            overflow-y: auto;
        }}
        .search-box {{
            padding: 6px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            width: 250px;
            font-size: 13px;
            height: 32px;
            box-sizing: border-box;
        }}
        .graph-toolbar {{
            padding: 8px 15px;
            background: white;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        .reset-btn {{
            padding: 6px 14px;
            background: #e8eaf6;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            height: 32px;
            box-sizing: border-box;
            display: flex;
            align-items: center;
        }}
        .reset-btn:hover {{
            background: #c5cae9;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th {{
            text-align: left;
            padding: 12px 15px;
            background: #f8f9fa;
            border-bottom: 2px solid #dee2e6;
            font-weight: 600;
            cursor: pointer;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        th:hover {{
            background: #e9ecef;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background: #f8f9fa;
            cursor: pointer;
        }}
        .type-badge {{
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        .detail-panel {{
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            border-radius: 8px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            width: 600px;
            max-height: 80vh;
            z-index: 1000;
            flex-direction: column;
        }}
        .detail-panel-body {{
            padding: 20px 25px 25px 25px;
            overflow-y: auto;
            flex: 1;
            min-height: 0;
        }}
        .detail-panel.active {{
            display: flex;
        }}
        .detail-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 999;
        }}
        .detail-overlay.active {{
            display: block;
        }}
        .detail-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 25px 15px 25px;
            border-bottom: 2px solid #e8eaf6;
            flex-shrink: 0;
        }}
        .detail-header h2 {{
            color: #1a237e;
            font-size: 18px;
            margin: 0;
        }}
        .close-btn {{
            background: none;
            border: none;
            font-size: 24px;
            color: #999;
            cursor: pointer;
            padding: 0;
            width: 30px;
            height: 30px;
            line-height: 30px;
            text-align: center;
        }}
        .close-btn:hover {{
            color: #333;
        }}
        .detail-section {{
            margin-bottom: 20px;
        }}
        .detail-section + .detail-section {{
            border-top: 2px solid #e0e0e0;
            padding-top: 20px;
            margin-top: 20px;
        }}
        .detail-section h3 {{
            color: #303f9f;
            font-size: 14px;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .ref-list {{
            list-style: none;
            padding: 0;
        }}
        .ref-item {{
            padding: 10px;
            margin-bottom: 8px;
            background: #f8f9fa;
            border-left: 3px solid #1a237e;
            border-radius: 4px;
        }}
        .ref-name {{
            font-weight: 600;
            color: #1a237e;
            display: block;
            margin-bottom: 4px;
        }}
        .ref-meta {{
            font-size: 12px;
            color: #666;
        }}
        .ref-meta span {{
            margin-right: 12px;
        }}
        .no-refs {{
            color: #999;
            font-style: italic;
            padding: 10px;
        }}
        .type-form {{
            background: #e3f2fd;
            color: #1565c0;
        }}
        .type-workflow {{
            background: #f3e5f5;
            color: #7b1fa2;
        }}
        .type-tasktype {{
            background: #e0f2f1;
            color: #00695c;
        }}
        .type-external {{
            background: #fff3e0;
            color: #e65100;
            margin-left: 6px;
        }}
        .group-header {{
            background: #f8f9fa;
            cursor: pointer;
            user-select: none;
            font-weight: 600;
            font-size: 15px;
            color: #333;
        }}
        .group-header:hover {{
            background: #e9ecef;
        }}
        .group-header td {{
            padding: 15px 15px !important;
            border-bottom: 2px solid #dee2e6 !important;
        }}
        .group-toggle {{
            font-size: 14px;
            color: #666;
            margin-left: 8px;
            transition: transform 0.2s;
            display: inline-block;
        }}
        .group-toggle.collapsed {{
            transform: rotate(-90deg);
        }}
        .group-count {{
            background: #1a237e;
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            margin-left: 10px;
        }}
        tr.item-row.hidden {{
            display: none;
        }}
        .markdown-container {{
            padding: 30px 50px;
            max-width: 900px;
            margin: 0 auto;
            background: white;
            min-height: 100%;
        }}
        .markdown-container h1 {{
            color: #1a237e;
            border-bottom: 2px solid #e8eaf6;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .markdown-container h2 {{
            color: #303f9f;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        .markdown-container ul {{
            margin-left: 20px;
            margin-bottom: 15px;
        }}
        .markdown-container li {{
            margin-bottom: 8px;
            line-height: 1.6;
        }}
        .markdown-container p {{
            line-height: 1.7;
            margin-bottom: 15px;
        }}
        .markdown-container strong {{
            color: #1a237e;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <h1>Solution Map</h1>
            <span class="subtitle">· Room {container_id}</span>
        </div>
        <div class="stats">
            <span class="stat">📋 {stats.get("form_count", 0)} Forms</span>
            <span class="stat">⚡ {stats.get("workflow_count", 0)} Workflows</span>
            <span class="stat" style="background: rgba(38, 166, 154, 0.25);">◆ {stats.get("task_type_count", 0)} Task Types</span>
            <span class="stat">🔗 {stats.get("total_edges", 0)} Relationships</span>
            <span class="stat">🏝️ {stats.get("isolated_nodes", 0)} Isolated</span>
        </div>
    </div>

    <div class="tabs">
        <div class="tab active" onclick="showTab('graph')">Graph</div>
        <div class="tab" onclick="showTab('table')">Object Grid</div>
        <div class="tab" onclick="showTab('summary')">AI Summary</div>
    </div>

    <div id="graph-content" class="content active">
        <div class="graph-toolbar">
            <input type="text" id="graph-search" class="search-box" placeholder="Search forms..." onkeyup="searchGraph(this.value)">
            <button onclick="resetGraph()" class="reset-btn">Reset View</button>
        </div>
        <div class="graph-container">
            <div id="graph-panel" class="graph-panel">
                <div class="panel-header">
                    <h3 id="panel-title">Select a node</h3>
                    <button onclick="closePanel()" class="panel-close">×</button>
                </div>
                <div class="panel-body">
                    <div class="panel-section">
                        <h4>References (Outgoing)</h4>
                        <ul id="panel-outgoing" class="panel-ref-list"></ul>
                    </div>
                    <div class="panel-section">
                        <h4>Referenced By (Incoming)</h4>
                        <ul id="panel-incoming" class="panel-ref-list"></ul>
                    </div>
                </div>
            </div>
            <div id="graph"></div>
            <div class="graph-legend">
                <div class="legend-title">Nodes</div>
                <div class="legend-item"><span class="legend-color" style="background:#4fc3f7"></span> Local Form</div>
                <div class="legend-item"><span class="legend-color" style="background:#ff9800"></span> External Form</div>
                <div class="legend-item"><span class="legend-color" style="background:#ba68c8"></span> Workflow</div>
                <div class="legend-item"><span class="legend-color" style="background:#26a69a"></span> Local Task Type</div>
                <div class="legend-item"><span class="legend-color" style="background:#80cbc4"></span> External Task Type</div>
                <div class="legend-item"><span class="legend-color" style="background:#ff6b6b"></span> Selected</div>
                <div class="legend-item"><span class="legend-color" style="background:#ffd93d"></span> Connected</div>
                <div class="legend-title" style="margin-top:12px">Relationships</div>
                <div class="legend-item"><span style="width:20px;height:2px;background:#2196f3;display:inline-block"></span> Field Reference</div>
                <div class="legend-item"><span style="width:20px;height:2px;background:#ff9800;display:inline-block;background-image:linear-gradient(90deg,#ff9800 50%,transparent 50%);background-size:8px 2px"></span> Custom Action</div>
            </div>
        </div>
    </div>

    <div id="table-content" class="content">
        <div class="table-toolbar">
            <input type="text" id="grid-search" class="search-box" placeholder="Search objects..." onkeyup="filterGrid(this.value)">
        </div>
        <div class="table-container" id="object-grid">
            <!-- Grid content will be generated by JavaScript -->
        </div>

        <!-- Detail panel overlay and modal -->
        <div class="detail-overlay" id="detail-overlay" onclick="closeDetails()"></div>
        <div class="detail-panel" id="detail-panel">
            <div class="detail-header">
                <h2 id="detail-title">Details</h2>
                <button class="close-btn" onclick="closeDetails()">×</button>
            </div>
            <div class="detail-panel-body">
                <div class="detail-section">
                    <h3>References (Outgoing)</h3>
                    <ul class="ref-list" id="refs-out"></ul>
                </div>
                <div class="detail-section">
                    <h3>Referenced By (Incoming)</h3>
                    <ul class="ref-list" id="refs-in"></ul>
                </div>
            </div>
        </div>
    </div>

    <div id="summary-content" class="content">
        <div class="markdown-container" id="markdown-content">
            {markdown_html}
        </div>
    </div>

    <script>
        // Human-readable trigger names
        function formatTriggerType(trigger) {{
            const triggerMap = {{
                'CHILD_OBJECT_MANUAL': 'Manual Trigger',
                'CHILD_OBJECT_CREATED': 'On Create',
                'CHILD_OBJECT_UPDATED': 'On Update',
                'CHILD_OBJECT_DELETED': 'On Delete',
                'SCHEDULED_ACTION': 'Scheduled',
                'BULK_ACTION_MANUAL': 'Bulk Manual',
                'OBJECT_MANUAL': 'Manual',
                'LINKED': 'Linked Action',
                'WEB_HOOK': 'Webhook',
                'LIST_MEMBER_ADDED': 'Member Added',
                'LIST_MEMBER_REMOVED': 'Member Removed'
            }};
            return triggerMap[trigger] || trigger;
        }}

        // Human-readable field type names
        function getReadableType(edge) {{
            const type = edge.relationship_type || edge;
            const typeMap = {{
                'LOOKUP': 'Form Lookup',
                'WORKFLOW_LOOKUP': 'Workflow Lookup',
                'FORM_ENTRY': 'Form Entry Link',
                'WORKFLOW': 'Workflow Entry Link',
                'TASK': 'Task Link',
                'ACTION_CREATES_ENTRY': 'Creates Entry',
                'ACTION_INVOKES_WORKFLOW': 'Invokes Workflow',
                'ACTION_CREATES_TASK': 'Creates Task',
                'ACTION_LAUNCHES_TEMPLATE': 'Launches Template',
                'ACTION_LAUNCHES_PLAN': 'Launches Plan'
            }};

            // Special case: REFERENCE depends on is_subform property
            if (type === 'REFERENCE') {{
                if (edge.is_subform === true) {{
                    return 'Subform';
                }} else if (edge.is_subform === false) {{
                    return 'Reference';
                }} else {{
                    return 'Reference/Subform';
                }}
            }}

            return typeMap[type] || type;
        }}

        // Tab switching
        function showTab(tabName) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
            const tabIndex = tabName === 'graph' ? 1 : tabName === 'table' ? 2 : 3;
            document.querySelector(`.tab:nth-child(${{tabIndex}})`).classList.add('active');
            document.getElementById(tabName + '-content').classList.add('active');
        }}

        // Store edges and nodes data for detail panel and search
        const edgesData = {json.dumps(edges_data)};
        const nodesData = {json.dumps(nodes_data)}.map(n => ({{
            ...n,
            originalColor: n.color
        }}));

        // Initialize graph
        const nodes = new vis.DataSet(nodesData);
        const edges = new vis.DataSet(edgesData);

        const container = document.getElementById('graph');
        const data = {{ nodes: nodes, edges: edges }};
        const options = {{
            physics: {{
                forceAtlas2Based: {{
                    gravitationalConstant: -120,
                    centralGravity: 0.005,
                    springLength: 350,
                    springConstant: 0.04
                }},
                solver: 'forceAtlas2Based',
                stabilization: {{ iterations: 200 }}
            }},
            nodes: {{
                font: {{
                    size: 11,
                    multi: true,
                    face: 'system-ui, -apple-system, sans-serif'
                }}
            }},
            edges: {{
                font: {{ size: 10, align: 'middle' }},
                smooth: {{ type: 'curvedCW', roundness: 0.2 }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 100
            }}
        }};

        const network = new vis.Network(container, data, options);

        // Add click handler for nodes
        network.on('click', function(params) {{
            if (params.nodes && params.nodes.length > 0) {{
                const nodeId = params.nodes[0];
                showGraphPanel(nodeId);
            }}
        }});

        // Debounced search
        let searchTimeout;
        function searchGraph(query) {{
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {{
                performSearch(query);
            }}, 150);
        }}

        // Actual search logic
        function performSearch(query) {{
            if (!query || query.length < 2) {{
                // Reset colors without clearing input
                resetGraphColors();
                return;
            }}

            const q = query.toLowerCase();
            const matchingNodes = [];
            const connectedNodes = new Set();

            // Find matching nodes
            nodesData.forEach(node => {{
                if (node.label.toLowerCase().includes(q)) {{
                    matchingNodes.push(node.id);
                }}
            }});

            // Find connected nodes
            matchingNodes.forEach(nodeId => {{
                edgesData.forEach(edge => {{
                    if (edge.from === nodeId) {{
                        connectedNodes.add(edge.to);
                    }}
                    if (edge.to === nodeId) {{
                        connectedNodes.add(edge.from);
                    }}
                }});
            }});

            // Update node colors and styles
            const updates = nodesData.map(node => {{
                if (matchingNodes.includes(node.id)) {{
                    return {{ id: node.id, color: '#ff6b6b', font: {{ size: 18, bold: true }} }};
                }} else if (connectedNodes.has(node.id)) {{
                    return {{ id: node.id, color: '#ffd93d', font: {{ size: 16 }} }};
                }} else {{
                    return {{ id: node.id, color: '#ddd', font: {{ color: '#999', size: 12 }} }};
                }}
            }});

            nodes.update(updates);

            // Focus on first matching node
            if (matchingNodes.length > 0) {{
                network.focus(matchingNodes[0], {{
                    scale: 1.2,
                    animation: {{ duration: 500 }}
                }});
            }}
        }}

        // Reset colors only (called from search when query < 2)
        function resetGraphColors() {{
            const updates = nodesData.map(n => ({{
                id: n.id,
                color: n.originalColor,
                font: {{ size: 14, color: '#343434' }}
            }}));
            nodes.update(updates);
        }}

        // Full reset including input clear (called from Reset button)
        function resetGraph() {{
            resetGraphColors();
            network.fit({{ animation: {{ duration: 500 }} }});
            document.getElementById('graph-search').value = '';
        }}

        // Highlight a node and its connections
        function highlightNode(nodeId) {{
            const connectedNodes = new Set();

            // Find all nodes connected to this one
            edgesData.forEach(edge => {{
                if (edge.from === nodeId) {{
                    connectedNodes.add(edge.to);
                }}
                if (edge.to === nodeId) {{
                    connectedNodes.add(edge.from);
                }}
            }});

            // Update node colors
            const updates = nodesData.map(n => {{
                if (n.id === nodeId) {{
                    // Selected node - bright highlight
                    return {{ id: n.id, color: '#ff6b6b', font: {{ size: 18, color: '#333', bold: true }} }};
                }} else if (connectedNodes.has(n.id)) {{
                    // Connected node - secondary highlight
                    return {{ id: n.id, color: '#ffd93d', font: {{ size: 16, color: '#333' }} }};
                }} else {{
                    // Other nodes - dim
                    return {{ id: n.id, color: '#ddd', font: {{ color: '#999', size: 12 }} }};
                }}
            }});

            nodes.update(updates);
        }}

        // Focus on a node, highlight it and its connections, then show panel
        function focusNode(nodeId) {{
            // Highlight the node and its connections
            highlightNode(nodeId);

            // Focus camera on the node
            network.focus(nodeId, {{
                scale: 1.2,
                animation: {{ duration: 500 }}
            }});

            // Update panel to show this node's details
            showGraphPanel(nodeId);
        }}

        // Show graph panel with node details
        function showGraphPanel(nodeId) {{
            // Highlight the node and its connections
            highlightNode(nodeId);

            const node = nodesData.find(n => n.id === nodeId);
            if (!node) return;

            document.getElementById('panel-title').textContent = node.label;

            // Get outgoing references
            const outgoing = edgesData.filter(e => e.from === nodeId);
            const outList = document.getElementById('panel-outgoing');
            if (outgoing.length === 0) {{
                outList.innerHTML = '<li class="panel-no-refs">No outgoing references</li>';
            }} else {{
                // Group by category
                const actions = outgoing.filter(e => e.edge_category === 'action');
                const fields = outgoing.filter(e => e.edge_category !== 'action');

                let html = '';

                // Actions section
                if (actions.length > 0) {{
                    html += '<div class="panel-subsection actions"><h5>Custom Actions</h5>';
                    html += actions.map(e => {{
                        const target = nodesData.find(n => n.id === e.to);
                        return `<li class="panel-ref-item" onclick="focusNode('${{e.to}}')">
                            <div class="panel-ref-name">${{e.action_name || target?.label || e.to}}<span class="badge action">ACTION</span></div>
                            <div class="panel-ref-meta">
                                <div>Trigger: ${{formatTriggerType(e.trigger_type)}}</div>
                                <div>Automatic: ${{e.automatic ? 'Yes' : 'No'}}</div>
                            </div>
                        </li>`;
                    }}).join('');
                    html += '</div>';
                }}

                // Field references section
                if (fields.length > 0) {{
                    html += '<div class="panel-subsection fields"><h5>Field References</h5>';
                    html += fields.map(e => {{
                        const target = nodesData.find(n => n.id === e.to);
                        return `<li class="panel-ref-item" onclick="focusNode('${{e.to}}')">
                            <div class="panel-ref-name">${{target ? target.label : e.to}}</div>
                            <div class="panel-ref-meta">
                                <div>Type: ${{getReadableType(e)}}</div>
                                <div>Field: ${{e.field_name || 'N/A'}}</div>
                            </div>
                        </li>`;
                    }}).join('');
                    html += '</div>';
                }}

                outList.innerHTML = html;
            }}

            // Get incoming references
            const incoming = edgesData.filter(e => e.to === nodeId);
            const inList = document.getElementById('panel-incoming');
            if (incoming.length === 0) {{
                inList.innerHTML = '<li class="panel-no-refs">No incoming references</li>';
            }} else {{
                // Group by category
                const actions = incoming.filter(e => e.edge_category === 'action');
                const fields = incoming.filter(e => e.edge_category !== 'action');

                let html = '';

                // Actions section
                if (actions.length > 0) {{
                    html += '<div class="panel-subsection actions"><h5>Custom Actions</h5>';
                    html += actions.map(e => {{
                        const source = nodesData.find(n => n.id === e.from);
                        return `<li class="panel-ref-item" onclick="focusNode('${{e.from}}')">
                            <div class="panel-ref-name">${{e.action_name || source?.label || e.from}}<span class="badge action">ACTION</span></div>
                            <div class="panel-ref-meta">
                                <div>Trigger: ${{formatTriggerType(e.trigger_type)}}</div>
                                <div>Automatic: ${{e.automatic ? 'Yes' : 'No'}}</div>
                            </div>
                        </li>`;
                    }}).join('');
                    html += '</div>';
                }}

                // Field references section
                if (fields.length > 0) {{
                    html += '<div class="panel-subsection fields"><h5>Field References</h5>';
                    html += fields.map(e => {{
                        const source = nodesData.find(n => n.id === e.from);
                        return `<li class="panel-ref-item" onclick="focusNode('${{e.from}}')">
                            <div class="panel-ref-name">${{source ? source.label : e.from}}</div>
                            <div class="panel-ref-meta">
                                <div>Type: ${{getReadableType(e)}}</div>
                                <div>Field: ${{e.field_name || 'N/A'}}</div>
                            </div>
                        </li>`;
                    }}).join('');
                    html += '</div>';
                }}

                inList.innerHTML = html;
            }}

            document.getElementById('graph-panel').classList.add('active');
        }}

        // Close graph panel
        function closePanel() {{
            document.getElementById('graph-panel').classList.remove('active');
            resetGraphColors();
        }}

        // Object grid data
        const objectGridData = {json.dumps(forms_table)};

        // Build grouped grid on load
        function buildObjectGrid() {{
            const container = document.getElementById('object-grid');

            // Group by type
            const groups = {{
                'Form': [],
                'Workflow': [],
                'TaskType': []
            }};

            objectGridData.forEach(item => {{
                if (groups[item.type]) {{
                    groups[item.type].push(item);
                }}
            }});

            // Sort items within each group
            Object.values(groups).forEach(group => {{
                group.sort((a, b) => a.name.localeCompare(b.name));
            }});

            // Build unified table
            const typeLabels = {{
                'Form': '📋 Forms',
                'Workflow': '⚡ Workflows',
                'TaskType': '◆ Task Types'
            }};

            let html = `
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Type</th>
                            <th>Refs Out</th>
                            <th>Refs In</th>
                            <th>ID</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            for (const [type, items] of Object.entries(groups)) {{
                if (items.length === 0) continue;

                const groupId = `group-${{type.toLowerCase()}}`;
                // Group header row
                html += `
                    <tr class="group-header" onclick="toggleGroup('${{groupId}}')">
                        <td colspan="5">
                            <span class="group-toggle" id="${{groupId}}-toggle">▼</span>
                            ${{typeLabels[type]}}
                            <span class="group-count">${{items.length}}</span>
                        </td>
                    </tr>
                `;

                // Item rows
                items.forEach(item => {{
                    const badgeClass = `type-${{item.type.toLowerCase()}}`;
                    const externalBadge = item.external ? '<span class="type-badge type-external">External</span>' : '';

                    html += `
                        <tr class="item-row" data-group="${{groupId}}" data-id="${{item.id}}" data-name="${{item.name.toLowerCase()}}" onclick="showNodeDetails('${{item.id}}')">
                            <td>${{item.name}}</td>
                            <td>
                                <span class="type-badge ${{badgeClass}}">${{item.type}}</span>
                                ${{externalBadge}}
                            </td>
                            <td>${{item.refs_out}}</td>
                            <td>${{item.refs_in}}</td>
                            <td style='color:#999;font-size:12px'>${{item.id}}</td>
                        </tr>
                    `;
                }});
            }}

            html += `
                    </tbody>
                </table>
            `;

            container.innerHTML = html;
        }}

        // Toggle group collapse
        function toggleGroup(groupId) {{
            const toggle = document.getElementById(groupId + '-toggle');
            const items = document.querySelectorAll(`tr.item-row[data-group="${{groupId}}"]`);

            const isCollapsed = toggle.classList.contains('collapsed');

            if (isCollapsed) {{
                toggle.classList.remove('collapsed');
                items.forEach(item => item.classList.remove('hidden'));
            }} else {{
                toggle.classList.add('collapsed');
                items.forEach(item => item.classList.add('hidden'));
            }}
        }}

        // Grid filtering
        function filterGrid(query) {{
            const q = query.toLowerCase();
            const items = document.querySelectorAll('tr.item-row');

            if (!q || q.length < 2) {{
                // Show all items
                items.forEach(item => {{
                    item.style.display = '';
                }});
                return;
            }}

            items.forEach(item => {{
                const name = item.getAttribute('data-name');
                if (name.includes(q)) {{
                    item.style.display = '';
                }} else {{
                    item.style.display = 'none';
                }}
            }});
        }}

        // Build grid on page load
        document.addEventListener('DOMContentLoaded', buildObjectGrid);

        // Show node details when clicking a table row
        function showNodeDetails(nodeId) {{
            // Find node name
            const node = nodesData.find(n => n.id === nodeId);
            if (!node) return;

            // Update title
            document.getElementById('detail-title').textContent = node.label;

            // Find outgoing edges (references)
            const outgoing = edgesData.filter(e => e.from === nodeId);
            const refsOutEl = document.getElementById('refs-out');
            refsOutEl.innerHTML = '';

            if (outgoing.length === 0) {{
                refsOutEl.innerHTML = '<div class="no-refs">No outgoing references</div>';
            }} else {{
                // Group by category
                const actions = outgoing.filter(e => e.edge_category === 'action');
                const fields = outgoing.filter(e => e.edge_category !== 'action');

                // Actions section
                if (actions.length > 0) {{
                    const wrapper = document.createElement('div');
                    wrapper.style.background = '#fff8e1';
                    wrapper.style.borderLeft = '3px solid #ff9800';
                    wrapper.style.padding = '10px';
                    wrapper.style.borderRadius = '6px';
                    wrapper.style.marginBottom = '15px';
                    const header = document.createElement('h4');
                    header.textContent = 'Custom Actions';
                    header.style.color = '#e65100';
                    header.style.fontSize = '11px';
                    header.style.fontWeight = '700';
                    header.style.marginBottom = '10px';
                    header.style.textTransform = 'uppercase';
                    wrapper.appendChild(header);
                    refsOutEl.appendChild(wrapper);

                    actions.forEach(edge => {{
                        const targetNode = nodesData.find(n => n.id === edge.to);
                        const li = document.createElement('li');
                        li.className = 'ref-item';

                        li.innerHTML = `
                            <span class="ref-name">${{edge.action_name || targetNode?.label || edge.to}}<span class="badge action">ACTION</span></span>
                            <div class="ref-meta" style="margin-top:6px;line-height:1.6">
                                <div><strong>Target:</strong> ${{targetNode ? targetNode.label : edge.to}}</div>
                                <div><strong>Trigger:</strong> ${{formatTriggerType(edge.trigger_type)}}</div>
                                <div><strong>Automatic:</strong> ${{edge.automatic ? 'Yes' : 'No'}}</div>
                            </div>
                        `;
                        wrapper.appendChild(li);
                    }});
                }}

                // Field references section
                if (fields.length > 0) {{
                    const fieldWrapper = document.createElement('div');
                    fieldWrapper.style.background = '#e3f2fd';
                    fieldWrapper.style.borderLeft = '3px solid #2196f3';
                    fieldWrapper.style.padding = '10px';
                    fieldWrapper.style.borderRadius = '6px';
                    fieldWrapper.style.marginBottom = '15px';
                    const header = document.createElement('h4');
                    header.textContent = 'Field References';
                    header.style.color = '#1565c0';
                    header.style.fontSize = '11px';
                    header.style.fontWeight = '700';
                    header.style.marginBottom = '10px';
                    header.style.textTransform = 'uppercase';
                    fieldWrapper.appendChild(header);
                    refsOutEl.appendChild(fieldWrapper);

                    fields.forEach(edge => {{
                        const targetNode = nodesData.find(n => n.id === edge.to);
                        const li = document.createElement('li');
                        li.className = 'ref-item';

                        li.innerHTML = `
                            <span class="ref-name">${{targetNode ? targetNode.label : edge.to}}</span>
                            <div class="ref-meta" style="margin-top:6px;line-height:1.6">
                                <div><strong>Type:</strong> ${{getReadableType(edge)}}</div>
                                <div><strong>Field:</strong> ${{edge.field_name || 'N/A'}}</div>
                            </div>
                        `;
                        fieldWrapper.appendChild(li);
                    }});
                }}
            }}

            // Find incoming edges (referenced by)
            const incoming = edgesData.filter(e => e.to === nodeId);
            const refsInEl = document.getElementById('refs-in');
            refsInEl.innerHTML = '';

            if (incoming.length === 0) {{
                refsInEl.innerHTML = '<div class="no-refs">No incoming references</div>';
            }} else {{
                // Group by category
                const actions = incoming.filter(e => e.edge_category === 'action');
                const fields = incoming.filter(e => e.edge_category !== 'action');

                // Actions section
                if (actions.length > 0) {{
                    const wrapper = document.createElement('div');
                    wrapper.style.background = '#fff8e1';
                    wrapper.style.borderLeft = '3px solid #ff9800';
                    wrapper.style.padding = '10px';
                    wrapper.style.borderRadius = '6px';
                    wrapper.style.marginBottom = '15px';
                    const header = document.createElement('h4');
                    header.textContent = 'Custom Actions';
                    header.style.color = '#e65100';
                    header.style.fontSize = '11px';
                    header.style.fontWeight = '700';
                    header.style.marginBottom = '10px';
                    header.style.textTransform = 'uppercase';
                    wrapper.appendChild(header);
                    refsInEl.appendChild(wrapper);

                    actions.forEach(edge => {{
                        const sourceNode = nodesData.find(n => n.id === edge.from);
                        const li = document.createElement('li');
                        li.className = 'ref-item';

                        li.innerHTML = `
                            <span class="ref-name">${{edge.action_name || sourceNode?.label || edge.from}}<span class="badge action">ACTION</span></span>
                            <div class="ref-meta" style="margin-top:6px;line-height:1.6">
                                <div><strong>Source:</strong> ${{sourceNode ? sourceNode.label : edge.from}}</div>
                                <div><strong>Trigger:</strong> ${{formatTriggerType(edge.trigger_type)}}</div>
                                <div><strong>Automatic:</strong> ${{edge.automatic ? 'Yes' : 'No'}}</div>
                            </div>
                        `;
                        wrapper.appendChild(li);
                    }});
                }}

                // Field references section
                if (fields.length > 0) {{
                    const fieldWrapper = document.createElement('div');
                    fieldWrapper.style.background = '#e3f2fd';
                    fieldWrapper.style.borderLeft = '3px solid #2196f3';
                    fieldWrapper.style.padding = '10px';
                    fieldWrapper.style.borderRadius = '6px';
                    fieldWrapper.style.marginBottom = '15px';
                    const header = document.createElement('h4');
                    header.textContent = 'Field References';
                    header.style.color = '#1565c0';
                    header.style.fontSize = '11px';
                    header.style.fontWeight = '700';
                    header.style.marginBottom = '10px';
                    header.style.textTransform = 'uppercase';
                    fieldWrapper.appendChild(header);
                    refsInEl.appendChild(fieldWrapper);

                    fields.forEach(edge => {{
                        const sourceNode = nodesData.find(n => n.id === edge.from);
                        const li = document.createElement('li');
                        li.className = 'ref-item';

                        li.innerHTML = `
                            <span class="ref-name">${{sourceNode ? sourceNode.label : edge.from}}</span>
                            <div class="ref-meta" style="margin-top:6px;line-height:1.6">
                                <div><strong>Type:</strong> ${{getReadableType(edge)}}</div>
                                <div><strong>Field:</strong> ${{edge.field_name || 'N/A'}}</div>
                            </div>
                        `;
                        fieldWrapper.appendChild(li);
                    }});
                }}
            }}

            // Show panel and overlay
            document.getElementById('detail-panel').classList.add('active');
            document.getElementById('detail-overlay').classList.add('active');
        }}

        // Close detail panel
        function closeDetails() {{
            document.getElementById('detail-panel').classList.remove('active');
            document.getElementById('detail-overlay').classList.remove('active');
        }}
    </script>
</body>
</html>"""

    return html


def markdown_to_html(markdown: str) -> str:
    """Convert markdown to basic HTML."""
    import re

    html = markdown

    # Headers
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Bold
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)

    # Lists
    lines = html.split("\n")
    in_list = False
    result = []
    for line in lines:
        if line.strip().startswith("- "):
            if not in_list:
                result.append("<ul>")
                in_list = True
            result.append(f"<li>{line.strip()[2:]}</li>")
        else:
            if in_list:
                result.append("</ul>")
                in_list = False
            if line.strip() and not line.startswith("<"):
                result.append(f"<p>{line}</p>")
            else:
                result.append(line)
    if in_list:
        result.append("</ul>")

    return "\n".join(result)


def export_dashboard(
    container_id: str,
    forms: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    relationships: list[Any],
    stats: dict[str, Any],
    graph: nx.DiGraph,
    markdown_summary: str,
    output_path: Path,
) -> Path:
    """Export unified dashboard HTML."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    html = generate_dashboard_html(
        container_id=container_id,
        forms=forms,
        workflows=workflows,
        relationships=relationships,
        stats=stats,
        graph=graph,
        markdown_summary=markdown_summary,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def open_in_browser(path: Path) -> bool:
    """Open file in default browser. Returns True if successful."""
    try:
        webbrowser.open(f"file://{path.absolute()}")
        return True
    except Exception:
        return False
