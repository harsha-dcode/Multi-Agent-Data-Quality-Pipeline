"""Stage 2: Profile the extracted dataset.

Produces a JSON summary the agent reads to make cleaning decisions:
shape, dtypes, null counts, distributions, top categories, IQR outlier
signals.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from claude_agent_sdk import tool


def _summarize_column(s: pd.Series) -> dict[str, Any]:
    n = len(s)
    nulls = int(s.isna().sum())
    info: dict[str, Any] = {
        "dtype": str(s.dtype),
        "null_count": nulls,
        "null_pct": round(nulls / n * 100, 2) if n else 0.0,
        "unique": int(s.nunique(dropna=True)),
    }

    if pd.api.types.is_numeric_dtype(s):
        desc = s.describe()
        for k_in, k_out in [
            ("min", "min"),
            ("25%", "q25"),
            ("50%", "median"),
            ("75%", "q75"),
            ("max", "max"),
            ("mean", "mean"),
            ("std", "std"),
        ]:
            v = desc.get(k_in)
            info[k_out] = float(v) if v is not None and not pd.isna(v) else None
        # Cheap outlier signal via Tukey's IQR rule.
        if info["q25"] is not None and info["q75"] is not None:
            iqr = info["q75"] - info["q25"]
            if iqr > 0:
                lo = info["q25"] - 1.5 * iqr
                hi = info["q75"] + 1.5 * iqr
                info["iqr_outlier_count"] = int(((s < lo) | (s > hi)).sum())
                info["iqr_lower_bound"] = lo
                info["iqr_upper_bound"] = hi

    elif pd.api.types.is_datetime64_any_dtype(s):
        info["min"] = str(s.min())
        info["max"] = str(s.max())

    else:
        # object / categorical — show the top values
        top = s.value_counts(dropna=True).head(5)
        info["top_values"] = {str(k): int(v) for k, v in top.items()}

    return info


def make_profile_tool(landing_dir: Path, profiled_dir: Path):

    @tool(
        "profile_data",
        (
            "Generate a structural profile of the extracted dataset: shape, dtypes, null "
            "counts, distributions, top categories, IQR outlier signals. ALWAYS run this "
            "right after extract_csv. The profile drives every cleaning decision."
        ),
        {"type": "object", "properties": {}},
    )
    async def profile_data(args: dict[str, Any]) -> dict[str, Any]:
        src = landing_dir / "extracted.parquet"
        if not src.exists():
            return {
                "content": [{"type": "text", "text": "ERROR: extracted.parquet not found. Run extract_csv first."}],
                "is_error": True,
            }
        df = pd.read_parquet(src)
        profile = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "duplicate_row_count": int(df.duplicated().sum()),
            "columns": {col: _summarize_column(df[col]) for col in df.columns},
        }
        out = profiled_dir / "profile.json"
        out.write_text(json.dumps(profile, indent=2, default=str))
        return {"content": [{"type": "text", "text": json.dumps(profile, indent=2, default=str)}]}

    return profile_data
