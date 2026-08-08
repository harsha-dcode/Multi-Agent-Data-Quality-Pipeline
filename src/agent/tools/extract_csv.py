"""Stage 1: Extract a CSV into the landing zone as Parquet."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from claude_agent_sdk import tool


def make_extract_csv_tool(landing_dir: Path):
    """Factory: returns the @tool-decorated function with landing_dir bound."""

    @tool(
        "extract_csv",
        (
            "Read a CSV from the landing zone and convert it to Parquet for downstream "
            "stages. ALWAYS the first tool you call. Returns row count and column list."
        ),
        {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename of the CSV in the landing zone (e.g. 'input.csv').",
                },
            },
            "required": ["filename"],
        },
    )
    async def extract_csv(args: dict[str, Any]) -> dict[str, Any]:
        filename = args["filename"]
        src = landing_dir / filename
        if not src.exists():
            return {
                "content": [{"type": "text", "text": f"ERROR: file not found: {src}"}],
                "is_error": True,
            }
        try:
            df = pd.read_csv(src)
        except Exception as e:  # noqa: BLE001  — surface any read failure to the agent
            return {
                "content": [{"type": "text", "text": f"ERROR reading CSV: {e}"}],
                "is_error": True,
            }
        out = landing_dir / "extracted.parquet"
        df.to_parquet(out, index=False)
        msg = (
            f"Extracted {len(df)} rows x {len(df.columns)} columns from {filename}.\n"
            f"Columns: {', '.join(df.columns)}\n"
            f"Saved Parquet at: {out}"
        )
        return {"content": [{"type": "text", "text": msg}]}

    return extract_csv
