"""Stage 8: Write the agent's markdown report to the final dir."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from claude_agent_sdk import tool


def make_report_tool(final_dir: Path):

    @tool(
        "write_report",
        (
            "Write a markdown report summarizing the analysis: what the data was, what "
            "cleaning decisions were made and WHY, key findings relevant to the brief, "
            "and any caveats. The report is the narrative half of the deliverable; the "
            "cleaned dataset is the data half."
        ),
        {
            "type": "object",
            "properties": {
                "markdown": {
                    "type": "string",
                    "description": "Full markdown report content.",
                },
            },
            "required": ["markdown"],
        },
    )
    async def write_report(args: dict[str, Any]) -> dict[str, Any]:
        path = final_dir / "report.md"
        path.write_text(args["markdown"], encoding="utf-8")
        return {"content": [{"type": "text", "text": f"Wrote report to {path} ({len(args['markdown'])} chars)"}]}

    return write_report
