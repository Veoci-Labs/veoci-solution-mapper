"""Output modules for solution mapper."""

from veoci_mapper.output.json_output import export_json, SolutionExport
from veoci_mapper.output.markdown import (
    generate_markdown_summary,
    export_markdown,
    generate_basic_markdown,
)
from veoci_mapper.output.visual import export_html
from veoci_mapper.output.mermaid import export_mermaid
from veoci_mapper.output.dashboard import export_dashboard, open_in_browser

__all__ = [
    "export_json",
    "SolutionExport",
    "generate_markdown_summary",
    "export_markdown",
    "generate_basic_markdown",
    "export_html",
    "export_mermaid",
    "export_dashboard",
    "open_in_browser",
]
