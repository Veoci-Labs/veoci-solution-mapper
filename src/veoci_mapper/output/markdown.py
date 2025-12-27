"""AI-generated markdown summary using Gemini."""

import os
from pathlib import Path
from typing import Any
import networkx as nx

from rich.console import Console

console = Console()


def generate_summary_prompt(
    container_id: str,
    forms: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    stats: dict[str, Any],
    graph: nx.DiGraph,
) -> str:
    """Generate the prompt for Gemini to summarize the solution."""

    # Build form list with relationships
    form_details = []
    for form in forms:
        form_id = str(form.get("id") or form.get("formId"))
        name = form.get("name", "Unknown")

        # Get relationships for this form
        refs_out = list(graph.successors(form_id)) if form_id in graph else []
        refs_in = list(graph.predecessors(form_id)) if form_id in graph else []

        detail = f"- {name}"
        if refs_out:
            out_names = [graph.nodes[n].get("name", n) for n in refs_out[:3]]
            detail += f" → references: {', '.join(out_names)}"
        if refs_in:
            in_names = [graph.nodes[n].get("name", n) for n in refs_in[:3]]
            detail += f" ← referenced by: {', '.join(in_names)}"
        form_details.append(detail)

    workflow_names = [w.get("name", "Unknown") for w in workflows]

    # Extract custom actions from graph edges
    action_details = []
    for source, target, data in graph.edges(data=True):
        if data.get("edge_category") == "action":
            source_name = graph.nodes[source].get("name", source)
            target_name = graph.nodes[target].get("name", target)
            action_name = data.get("action_name", "Unknown action")
            trigger = data.get("trigger_type", "Unknown")
            rel_type = data.get("relationship_type", "ACTION")
            action_details.append(
                f"- {action_name}: {source_name} → {target_name} "
                f"(trigger: {trigger}, type: {rel_type})"
            )

    prompt = f"""Analyze this Veoci solution and write a clear, professional markdown summary.
The primary goal is to help the user understand how this solution works and how its components interact.

## Solution Data

**Container ID:** {container_id}

**Statistics:**
- Forms: {stats.get('form_count', 0)}
- Workflows: {stats.get('workflow_count', 0)}
- Total Relationships: {stats.get('total_edges', 0)}
- Action-based relationships: {stats.get('action_edges', 0)}
- Field-based relationships: {stats.get('field_edges', 0)}
- Connected components: {stats.get('connected_components', 0)}

**Forms and their relationships:**
{chr(10).join(form_details[:30])}
{"... and more" if len(form_details) > 30 else ""}

**Workflows:**
{chr(10).join(f"- {w}" for w in workflow_names)}

**Custom Actions (automations that connect forms):**
{chr(10).join(action_details[:20]) if action_details else "No custom actions found"}
{"... and more" if len(action_details) > 20 else ""}

**Most referenced forms (central to the solution):**
{chr(10).join(f"- {item['name']} ({item['count']} references)" for item in stats.get('most_referenced', [])[:5])}

## Instructions

Write a markdown document that helps the user understand this solution. Focus on clarity and practical understanding.

**Required sections (in order of importance):**

1. **Overview** - What is this solution for? Infer the business purpose from form and workflow names. Be specific about what problems it solves.

2. **Core Components** - Identify the central forms that anchor this solution. Explain what role each key form plays in the overall workflow.

3. **How It Works** - Describe the data flow through the solution:
   - How do forms connect to each other?
   - What triggers create new entries or update data?
   - How do workflows orchestrate the process?

4. **Automations & Actions** - Explain the important custom actions:
   - What do they do?
   - When do they trigger?
   - How do they connect different parts of the solution?

5. **Supporting Components** - List any utility forms, reporting forms, or secondary components.

6. **Notes** (optional, brief) - Any observations about potential improvements or notable patterns, but keep this short.

**Guidelines:**
- Prioritize helping the user understand what this solution DOES over analyzing its structure
- Use plain language, not technical jargon
- Be concise - bullet points are preferred
- Focus on the "why" and "how" of the solution
- Custom actions are important - they show how the solution automates work"""

    return prompt


async def generate_markdown_summary(
    container_id: str,
    forms: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    stats: dict[str, Any],
    graph: nx.DiGraph,
) -> str | None:
    """
    Generate markdown summary using Gemini.

    Returns None if Gemini is not configured.
    """
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        console.print("[yellow]Skipping AI summary - GEMINI_API_KEY not set[/yellow]")
        return None

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = generate_summary_prompt(container_id, forms, workflows, stats, graph)

        console.print("[dim]Generating AI summary...[/dim]")
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
        )

        text = response.text

        # Strip markdown code fences if present
        if text.startswith("```markdown"):
            text = text[len("```markdown"):].strip()
        if text.startswith("```"):
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        return text

    except ImportError:
        console.print("[yellow]google-genai not installed - skipping AI summary[/yellow]")
        return None
    except Exception as e:
        console.print(f"[yellow]AI summary failed: {e}[/yellow]")
        return None


def export_markdown(
    summary: str,
    output_path: Path,
) -> Path:
    """
    Write markdown summary to file.

    Returns the path to the created file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(summary)

    return output_path


def generate_basic_markdown(
    container_id: str,
    forms: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    stats: dict[str, Any],
) -> str:
    """Generate basic markdown without AI (fallback)."""

    lines = [
        "# Solution Map",
        "",
        f"**Container ID:** {container_id}",
        "",
        "## Statistics",
        "",
        f"- **Forms:** {stats.get('form_count', 0)}",
        f"- **Workflows:** {stats.get('workflow_count', 0)}",
        f"- **Relationships:** {stats.get('total_edges', 0)}",
        f"- **Connected Components:** {stats.get('connected_components', 0)}",
        f"- **Isolated Nodes:** {stats.get('isolated_nodes', 0)}",
        "",
        "## Forms",
        "",
    ]

    for form in forms:
        name = form.get("name", "Unknown")
        lines.append(f"- {name}")

    lines.extend([
        "",
        "## Workflows",
        "",
    ])

    for workflow in workflows:
        name = workflow.get("name", "Unknown")
        lines.append(f"- {name}")

    if stats.get("most_referenced"):
        lines.extend([
            "",
            "## Most Referenced Forms",
            "",
        ])
        for item in stats.get("most_referenced", []):
            lines.append(f"- {item['name']} ({item['count']} references)")

    return "\n".join(lines)
