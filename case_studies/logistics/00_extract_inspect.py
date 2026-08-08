"""
Stage 2: Data Extraction / Raw Inventory
Reads the raw logistics CSV and writes a structural inventory report.
"""
import pandas as pd
import numpy as np
import os

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

IN_PATH = str(_HERE / "input" / "logistics_supply_chain_dataset_v3.csv")
OUT_DIR = str(_HERE)
OUT_PATH = os.path.join(OUT_DIR, "00_extraction_inventory.txt")

with open(IN_PATH, "rb") as f:
    raw_bytes = f.read()

# Detect BOM
has_bom = raw_bytes[:3] == b'\xef\xbb\xbf'

# Try encodings
encoding_used = "utf-8-sig" if has_bom else "utf-8"

df = pd.read_csv(IN_PATH, encoding=encoding_used, dtype=str, keep_default_na=False)

lines = []
lines.append("=== STAGE 2: DATA EXTRACTION / RAW INVENTORY ===")
lines.append(f"Input file: {IN_PATH}")
lines.append(f"File size bytes: {len(raw_bytes)}")
lines.append(f"BOM present: {has_bom}")
lines.append(f"Encoding used: {encoding_used}")
lines.append(f"Detected delimiter: comma")
lines.append(f"Row count (excluding header): {len(df)}")
lines.append(f"Column count: {len(df.columns)}")
lines.append("")
lines.append("Column names (raw, exact order):")
for i, c in enumerate(df.columns):
    lines.append(f"  [{i}] {c}")

lines.append("")
lines.append("=== FIRST 10 ROWS (raw, as strings) ===")
lines.append(df.head(10).to_string())

lines.append("")
lines.append("=== LAST 10 ROWS (raw, as strings) ===")
lines.append(df.tail(10).to_string())

lines.append("")
lines.append("=== STRUCTURAL ANOMALY CHECK ===")
# Check for fully blank rows
blank_rows = df[(df.apply(lambda r: all(str(v).strip() == "" for v in r), axis=1))]
lines.append(f"Fully blank rows: {len(blank_rows)}")

# Check for rows where all cells look like a footer/summary (e.g. contain 'total' 'sum')
suspect_footer = df[df.apply(lambda r: any('total' in str(v).lower() or 'summary' in str(v).lower() for v in r), axis=1)]
lines.append(f"Rows containing 'total'/'summary' token anywhere: {len(suspect_footer)}")

# Check column name issues
lines.append("")
lines.append("Header issues check:")
for c in df.columns:
    issues = []
    if c != c.strip():
        issues.append("leading/trailing whitespace")
    if any(ch in c for ch in [' ', '-', '.', '/']):
        issues.append("contains space/hyphen/dot/slash")
    if issues:
        lines.append(f"  '{c}': {issues}")
lines.append("  (columns not listed above had no header issues)")

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Wrote {OUT_PATH}")
print(f"Rows: {len(df)}, Cols: {len(df.columns)}")
print(list(df.columns))
