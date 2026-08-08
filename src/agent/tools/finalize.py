"""Stage 9: Promote cleaned Parquet to final dir as CSV + Parquet."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from claude_agent_sdk import tool


def make_finalize_tool(cleaned_dir: Path, final_dir: Path):

    @tool(
        "finalize",
        (
            "Convert the cleaned Parquet to a CSV (and re-save Parquet) in the final folder, "
            "ready for any BI tool. Run this LAST, after clean_data and write_report."
        ),
        {"type": "object", "properties": {}},
    )
    async def finalize(args: dict[str, Any]) -> dict[str, Any]:
        src = cleaned_dir / "cleaned.parquet"
        if not src.exists():
            return {
                "content": [{"type": "text", "text": "ERROR: cleaned.parquet not found."}],
                "is_error": True,
            }
        df = pd.read_parquet(src)
        out_csv = final_dir / "final_dataset.csv"
        out_pq = final_dir / "final_dataset.parquet"
        df.to_csv(out_csv, index=False)
        df.to_parquet(out_pq, index=False)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Final dataset written: {out_csv} ({len(df)} rows x {len(df.columns)} cols)",
                }
            ]
        }

    return finalize
