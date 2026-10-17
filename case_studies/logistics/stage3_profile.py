"""
Stage 3: Data Profiling
Full column-by-column statistical and quality profile.
"""
import pandas as pd
import numpy as np
import os

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

IN_PATH = str(_HERE / "input" / "logistics_supply_chain_dataset_v3.csv")
OUT_DIR = str(_HERE)
OUT_PATH = os.path.join(OUT_DIR, "01_profile_report.txt")

df = pd.read_csv(IN_PATH, encoding="utf-8", dtype=str, keep_default_na=False)

NULL_DISGUISES = {'', ' ', '-', '?', 'n/a', 'na', 'null', 'none', 'tbd', 'unknown',
                   'undefined', '#n/a', '#value!', '#ref!'}

def is_disguised_null(v):
    return str(v).strip().casefold() in NULL_DISGUISES

lines = []
lines.append("=== STAGE 3: DATA PROFILING ===")
lines.append(f"Total rows: {len(df)}")
lines.append(f"Total columns: {len(df.columns)}")
lines.append("")

for col in df.columns:
    s = df[col]
    lines.append(f"--- Column: {col} ---")
    n = len(s)
    disguised_null_mask = s.apply(is_disguised_null)
    null_count = disguised_null_mask.sum()
    null_rate = 100 * null_count / n
    lines.append(f"  Null count (incl. disguises): {null_count} ({null_rate:.2f}%)")

    # breakdown of disguise tokens found
    if null_count > 0:
        tokens = s[disguised_null_mask].apply(lambda v: str(v).strip().casefold()).value_counts()
        lines.append(f"  Disguise token breakdown: {dict(tokens)}")

    nonnull = s[~disguised_null_mask]
    unique_count = nonnull.nunique()
    lines.append(f"  Unique non-null values: {unique_count}")

    top10 = nonnull.value_counts().head(10)
    lines.append(f"  Top 10 values: {dict(top10)}")

    # try numeric
    numeric_conv = pd.to_numeric(nonnull, errors='coerce')
    numeric_valid_rate = numeric_conv.notna().mean() if len(nonnull) else 0
    if numeric_valid_rate > 0.9:
        vals = numeric_conv.dropna()
        lines.append(f"  [NUMERIC] min={vals.min()}, max={vals.max()}, mean={vals.mean():.4f}, "
                      f"median={vals.median():.4f}, std={vals.std():.4f}, skew={vals.skew():.4f}, "
                      f"pct_negative={100*(vals<0).mean():.2f}%, pct_zero={100*(vals==0).mean():.2f}%")

    # try date
    if 'date' in col.lower():
        date_conv = pd.to_datetime(nonnull, errors='coerce', format='mixed')
        unparseable = date_conv.isna().sum()
        lines.append(f"  [DATE] min={date_conv.min()}, max={date_conv.max()}, unparseable={unparseable}")

    # string length stats for object-like columns
    if numeric_valid_rate <= 0.9 and 'date' not in col.lower():
        lens = nonnull.apply(len)
        if len(lens):
            lines.append(f"  [STRING] min_len={lens.min()}, max_len={lens.max()}, avg_len={lens.mean():.2f}")
            longest = nonnull.loc[lens.idxmax()] if len(lens) else None
            shortest = nonnull.loc[lens.idxmin()] if len(lens) else None
            lines.append(f"  Longest sample: {longest!r}")
            lines.append(f"  Shortest sample: {shortest!r}")

    if unique_count > 0 and unique_count < 50 and numeric_valid_rate <= 0.9:
        lines.append(f"  [CATEGORICAL] all unique values: {sorted(nonnull.unique().tolist())}")

    if unique_count == 1:
        lines.append(f"  *** ZERO VARIANCE COLUMN ***")

    if null_rate > 30:
        lines.append(f"  *** HIGH RISK: >30% nulls ***")

    lines.append("")

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Wrote {OUT_PATH}")
