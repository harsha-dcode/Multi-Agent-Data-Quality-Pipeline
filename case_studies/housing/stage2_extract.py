import pandas as pd
import numpy as np
import sys

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

INPUT = str(_HERE / "input" / "house_50k_sample.csv")
OUT = str(_HERE / "00_inspect_report.txt")

with open(OUT, "w", encoding="utf-8") as f:
    # detect encoding roughly - try utf-8 first
    df = pd.read_csv(INPUT, encoding="utf-8", dtype=str, keep_default_na=False)
    f.write(f"Rows: {len(df)}\n")
    f.write(f"Cols: {len(df.columns)}\n")
    f.write(f"Columns:\n")
    for c in df.columns:
        f.write(f"  {c}\n")
    f.write("\nFirst 5 rows:\n")
    f.write(df.head(5).to_string() + "\n")
    f.write("\nLast 5 rows:\n")
    f.write(df.tail(5).to_string() + "\n")
    f.write("\nDtypes (raw, all read as str):\n")
    f.write(str(df.dtypes) + "\n")

    f.write("\n\n=== Per-column sample of unique values (first 15) and null-disguise scan ===\n")
    null_disguises = {'', ' ', '-', '?', 'n/a', 'na', 'null', 'none', 'tbd', 'unknown', 'undefined',
                       '#n/a', '#value!', '#ref!'}
    for c in df.columns:
        vals = df[c]
        nunique = vals.nunique()
        sample = vals.unique()[:15]
        disguise_hits = vals.apply(lambda v: str(v).strip().casefold() in null_disguises).sum()
        f.write(f"\nColumn: {c} | nunique={nunique} | disguise_hits={disguise_hits}\n")
        f.write(f"  sample: {list(sample)}\n")

    f.write("\n\n=== Full value_counts for likely categorical columns (nunique < 50) ===\n")
    for c in df.columns:
        if df[c].nunique() < 50:
            f.write(f"\n--- {c} ---\n")
            f.write(df[c].value_counts(dropna=False).to_string() + "\n")

print("done")
