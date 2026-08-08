#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
02b_targeted_probe.py -- follow-up checks on two things 02_extract_and_profile.py flagged but
did not fully resolve: (1) the 20 email cells that don't contain the literal string
'example.com', and (2) an exact characterization of the raw-duplicate groups, since
"duplicated(keep=False)" alone doesn't say how many groups or how many extra rows would be
removed.
"""
import os
import pandas as pd

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

OUT_DIR = str(_HERE)
REPORT = os.path.join(OUT_DIR, "02b_targeted_probe_report.txt")
df = pd.read_pickle(os.path.join(OUT_DIR, "_raw_with_source_row.pkl"))

lines = []
def log(s=""):
    lines.append(str(s))

log("=" * 78)
log("PROBE 1 -- email cells NOT containing literal 'example.com'")
log("=" * 78)
email_col = "Customer Email"
mask = ~df[email_col].str.contains("example.com", regex=False, na=False)
subset = df.loc[mask, ["__source_row", email_col]]
log(f"Count: {len(subset)}")
for _, row in subset.iterrows():
    log(f"  row {row['__source_row']}: {row[email_col]!r}")

log("\n" + "=" * 78)
log("PROBE 2 -- exact-duplicate row groups (raw strings, before any normalization)")
log("=" * 78)
data_cols = [c for c in df.columns if c != "__source_row"]
dup_mask = df[data_cols].duplicated(keep=False)
dup_df = df.loc[dup_mask].sort_values(data_cols)
groups = dup_df.groupby(data_cols, dropna=False)
n_groups = 0
n_extra_rows = 0
for key, g in groups:
    n_groups += 1
    n_extra_rows += len(g) - 1
    src_rows = g["__source_row"].tolist()
    log(f"  group of {len(g)} identical raw rows, __source_row = {src_rows}, order_id={g['order_id'].iloc[0]!r}")
log(f"\nTotal duplicate groups: {n_groups}")
log(f"Total rows involved (incl. first occurrence): {dup_mask.sum()}")
log(f"Extra rows that 4.11 exact-dup removal would drop (keep first per group): {n_extra_rows}")

log("\n" + "=" * 78)
log("PROBE 3 -- order_id repeats that are NOT raw exact-duplicates (potential PK conflicts)")
log("=" * 78)
oid_stripped = df["order_id"].str.strip()
oid_counts = oid_stripped.value_counts()
repeated_ids = oid_counts[oid_counts > 1].index.tolist()
pk_conflict_groups = 0
for oid in repeated_ids:
    grp = df[oid_stripped == oid]
    # are all rows in this order_id group identical on every OTHER column too (raw strings)?
    other_cols = [c for c in data_cols if c != "order_id"]
    all_identical = grp[other_cols].duplicated(keep=False).all() and grp[other_cols].nunique().eq(1).all()
    if not all_identical:
        pk_conflict_groups += 1
        log(f"  order_id {oid!r}: {len(grp)} rows, NOT all-identical on other columns -> real PK conflict candidate")
        for _, r in grp.iterrows():
            log(f"      row {r['__source_row']}: customer={r['customer name']!r} date={r['Order_Date']!r} rev={r['Total Revenue']!r}")
log(f"\nTotal order_id groups with a genuine (non-exact-dup) conflict: {pk_conflict_groups}")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines).encode("ascii", errors="replace").decode("ascii"))
print(f"\n[WROTE] {REPORT}")
