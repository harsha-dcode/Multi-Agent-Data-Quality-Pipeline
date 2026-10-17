# -*- coding: utf-8 -*-
"""
CROSS-CUTTING VERIFICATION: independent write-back check for the sales run.

Per the "never trust a step's own success report" rule, this re-derives every
number from the artifacts on disk (cleaned_data.csv, viz_ready.csv,
change_log.csv) rather than trusting what stage4_clean.py / stage5_validate.py /
stage8_viz_prep.py printed to the console.

Run with:
    python 08_verify_writeback.py

Writes: 08_verify_writeback_report.txt
"""
import re
from pathlib import Path as _Path

import numpy as np
import pandas as pd

_HERE = _Path(__file__).resolve().parent
CLEANED = str(_HERE / "cleaned_data.csv")
VIZ = str(_HERE / "viz_ready.csv")
CHANGELOG = str(_HERE / "change_log.csv")
REPORT = str(_HERE / "08_verify_writeback_report.txt")

lines = []


def log(s=""):
    lines.append(str(s))
    print(s)


def rule(t):
    log()
    log(t)
    log("-" * len(t))


df = pd.read_csv(CLEANED, encoding="utf-8", low_memory=False)
viz = pd.read_csv(VIZ, encoding="utf-8", low_memory=False)
cl = pd.read_csv(CHANGELOG, encoding="utf-8", low_memory=False)

log("=" * 78)
log("WRITE-BACK VERIFICATION -- SALES")
log("=" * 78)
log(f"cleaned_data.csv : rows={len(df):,}  cols={len(df.columns)}")
log(f"viz_ready.csv    : rows={len(viz):,}  cols={len(viz.columns)}")
log(f"change_log.csv   : rows={len(cl):,}")

# ---- 1. row identity ---------------------------------------------------
rule("1. __source_row integrity (the audit trail depends on this)")
if "__source_row" not in df.columns:
    log("  FAIL: __source_row missing -- the change log cannot be resolved")
else:
    sr = df["__source_row"]
    log(f"  nulls               : {int(sr.isna().sum())}   (must be 0)")
    log(f"  duplicates          : {int(sr.duplicated().sum())}   (must be 0)")
    log(f"  min / max           : {int(sr.min())} / {int(sr.max())}")
    log(f"  monotonic increasing: {bool(sr.is_monotonic_increasing)}")

# ---- 2. headers --------------------------------------------------------
rule("2. Header normalisation (Stage 4.1)")
non_snake = [c for c in df.columns
             if c != "__source_row" and not re.fullmatch(r"[a-z0-9_]+", c)]
log(f"  non-snake_case headers remaining: {non_snake if non_snake else '[] (correct)'}")

# ---- 3. flags ----------------------------------------------------------
rule("3. Flag columns -- materialised on the frame, not only in the log")
flags = [c for c in df.columns if c.endswith("_flag")]
log(f"  flag columns present: {len(flags)}")
total_true = 0
for f in flags:
    n = int(pd.to_numeric(df[f], errors="coerce").fillna(0).astype(bool).sum()
            if df[f].dtype != object
            else df[f].astype(str).str.strip().str.lower().isin(["true", "1"]).sum())
    total_true += n
    if n:
        log(f"    {f:<44} True = {n:,}")
log(f"  total flagged cells across all flag columns: {total_true:,}")

# ---- 4. Stage 8 filtering ---------------------------------------------
rule("4. cleaned_data.csv -> viz_ready.csv filtering (Stage 8)")
if "__source_row" in df.columns and "__source_row" in viz.columns:
    a, b = set(df["__source_row"]), set(viz["__source_row"])
    dropped = a - b
    log(f"  rows in cleaned          : {len(a):,}")
    log(f"  rows in viz_ready        : {len(b):,}")
    log(f"  filtered out for viz     : {len(dropped):,}")
    log(f"  viz is a subset of cleaned: {b.issubset(a)}   (must be True)")
    if dropped:
        sub = df[df["__source_row"].isin(dropped)]
        log("  why those rows were filtered (flags True among dropped rows):")
        for f in flags:
            n = int(sub[f].astype(str).str.strip().str.lower().isin(["true", "1"]).sum())
            if n:
                log(f"    {f:<44} {n:,}")

# ---- 5. change log -----------------------------------------------------
rule("5. change_log.csv integrity")
log("  CHANGE_TYPE breakdown:")
for ct, n in cl["CHANGE_TYPE"].value_counts().items():
    log(f"    {str(ct):<44} {n:,}")

if "SOURCE_ROW" in cl.columns and "__source_row" in df.columns:
    logged = pd.to_numeric(cl["SOURCE_ROW"], errors="coerce").dropna().astype(int)
    known = set(df["__source_row"].astype(int))
    removed = cl.loc[cl["CHANGE_TYPE"].astype(str).str.contains("REMOV|DROP", case=False,
                                                                na=False), "SOURCE_ROW"]
    removed = set(pd.to_numeric(removed, errors="coerce").dropna().astype(int))
    orphan = set(logged) - known - removed
    log()
    log(f"  distinct SOURCE_ROW values in log : {logged.nunique():,}")
    log(f"  rows logged as removed            : {len(removed):,}")
    log(f"  orphaned log entries              : {len(orphan):,}   (must be 0)")

# ---- 6. reconstructability --------------------------------------------
rule("6. Reconstructability precondition")
need = ["SOURCE_ROW", "COLUMN", "CHANGE_TYPE", "ORIGINAL_VALUE", "NEW_VALUE", "REASON"]
missing = [c for c in need if c not in cl.columns]
log(f"  required log fields present: {'yes' if not missing else 'MISSING ' + str(missing)}")

# ---- 7. derived column + the revenue cross-check ------------------------
rule("7. revenue_calculated and the revenue_mismatch_flag")
num = lambda c: pd.to_numeric(df[c], errors="coerce")
if {"revenue_calculated", "units_sold", "unit_price"}.issubset(df.columns):
    exp = num("units_sold") * num("unit_price")
    rc = num("revenue_calculated")
    m = rc.notna() & exp.notna()
    agree = int(((rc[m] - exp[m]).abs() < 0.01).sum())
    log(f"  revenue_calculated == units_sold * unit_price: {agree:,} / "
        f"{int(m.sum()):,} ({agree / max(int(m.sum()), 1) * 100:.1f}%)")

if {"revenue_mismatch_flag", "total_revenue", "revenue_calculated"}.issubset(df.columns):
    flg = df["revenue_mismatch_flag"].astype(str).str.strip().str.lower().isin(["true", "1"])
    tr, rc = num("total_revenue"), num("revenue_calculated")
    comparable = tr.notna() & rc.notna()
    rel = (tr - rc).abs() / rc.abs().replace(0, np.nan)
    log()
    log(f"  rows where total_revenue and revenue_calculated are comparable: "
        f"{int(comparable.sum()):,}")
    log(f"  revenue_mismatch_flag True: {int(flg.sum()):,}")
    log(f"  of those, median relative gap: "
        f"{rel[flg & comparable].median() * 100:.1f}%" if (flg & comparable).any() else "  n/a")
    log("  The pipeline flagged these rather than recomputing total_revenue,")
    log("  because which of the two fields is wrong is not determinable from")
    log("  the data alone (see insights_report.md R1).")

log()
log("=" * 78)
log("Verification complete -- every figure above was recomputed from the")
log("artifacts on disk, independent of what the pipeline scripts reported.")
log("=" * 78)

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nwrote {REPORT}")
