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

    # Get connected forms (non-isolated)
    connected_forms = [
        n for n in graph.nodes()
        if graph.in_degree(n) > 0 or graph.out_degree(n) > 0
    ]

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

    prompt = f"""Analyze this Veoci solution and write a clear, professional markdown summary.

## Solution Data

**Container ID:** {container_id}

**Statistics:**
- Forms: {stats.get('form_count', 0)}
- Workflows: {stats.get('workflow_count', 0)}
- Relationships: {stats.get('total_edges', 0)}
- Connected components: {stats.get('connected_components', 0)}

**Forms and their relationships:**
{chr(10).join(form_details[:30])}
{"... and more" if len(form_details) > 30 else ""}

**Workflows:**
{chr(10).join(f"- {w}" for w in workflow_names)}

**Most referenced forms:**
{chr(10).join(f"- {item['name']} ({item['count']} references)" for item in stats.get('most_referenced', [])[:5])}

## Instructions

Write a markdown document with these sections:
1. **Overview** - What this solution appears to be for (infer from form/workflow names)
2. **Key Components** - The most important forms and workflows
3. **Data Flow** - How forms connect to each other (based on relationships)
4. **Workflows** - What each workflow likely does
5. **Recommendations** - Any observations about the solution structure

Keep it concise but informative. Use bullet points. Be professional."""

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
