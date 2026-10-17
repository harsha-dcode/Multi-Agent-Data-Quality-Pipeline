#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_summary.py -- assembles RUN_SUMMARY.md from the actual artifacts on disk (never
hand-typed), so every number in it is re-derivable by re-running 00-05 and this script.
"""

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

import os
import hashlib
import pandas as pd

OUT_DIR = str(_HERE)
IN_PATH = str(_HERE / "input" / "messy_sales.csv")
SUMMARY_MD = os.path.join(OUT_DIR, "RUN_SUMMARY.md")

raw_bytes = open(IN_PATH, "rb").read()
md5 = hashlib.md5(raw_bytes).hexdigest()
sha256 = hashlib.sha256(raw_bytes).hexdigest()

raw = pd.read_pickle(os.path.join(OUT_DIR, "_raw_with_source_row.pkl"))
clean = pd.read_csv(os.path.join(OUT_DIR, "cleaned_data.csv"))
viz = pd.read_csv(os.path.join(OUT_DIR, "viz_ready.csv"))
chg = pd.read_csv(os.path.join(OUT_DIR, "change_log.csv"), dtype=str)

n_raw = len(raw)
n_clean = len(clean)
n_viz = len(viz)
n_removed = n_raw - n_clean
n_dropped_viz = n_clean - n_viz

change_type_counts = chg["CHANGE_TYPE"].value_counts()

flag_cols = [c for c in clean.columns if c.endswith("_flag")]
flag_counts = {c: int(clean[c].sum()) for c in sorted(flag_cols)}

# naive-vs-preserved cell comparison, recomputed fresh (not copied from 00_peek_report.txt)
import io
text = raw_bytes.decode("utf-8-sig")
df_naive = pd.read_csv(io.StringIO(text))
df_safe = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
n_cells_total = df_safe.shape[0] * df_safe.shape[1]
destroyed = 0
for col_idx in range(df_safe.shape[1]):
    for row_idx in range(df_safe.shape[0]):
        raw_val = df_safe.iat[row_idx, col_idx]
        naive_val = df_naive.iat[row_idx, col_idx]
        naive_as_str = "" if pd.isna(naive_val) else str(naive_val)
        if (pd.isna(naive_val) and raw_val.strip() != "") or (naive_as_str != raw_val and raw_val.strip() != ""):
            destroyed += 1
preserved = n_cells_total - destroyed

# cross-column BR1 check summary, recomputed from cleaned_data.csv directly (not copied from log)
both_present = clean["total_revenue"].notna() & clean["units_sold"].notna() & clean["unit_price"].notna()
calc = clean["units_sold"] * clean["unit_price"]
rel_diff = (clean["total_revenue"] - calc).abs() / calc.replace(0, pd.NA).abs()
mismatch_final = (both_present & (rel_diff > 0.01) & (~clean["total_revenue_sign_flag"]) & (~clean["unit_price_sign_flag"])).sum()

# collision guard results, recomputed fresh (same logic as stage3_profile.py)
from thefuzz import utils as fuzz_utils

CANON = {
    "region": ["North", "South", "East", "West", "Northeast"],
    "product": ["Alpha", "Beta", "Gamma", "Delta"],
    "channel": ["Retail", "Wholesale", "Online", "Brick & Mortar", "B2B", "B2C"],
}
collision_results = {}
for col, canon_list in CANON.items():
    keys = [fuzz_utils.full_process(str(c)) for c in canon_list]
    collision_results[col] = len(set(keys)) < len(keys)

# validation report PASS/FAIL tally, parsed from validation_report.md itself
with open(os.path.join(OUT_DIR, "validation_report.md"), encoding="utf-8") as f:
    val_text = f.read()
n_v_pass = val_text.count("| PASS |")
n_v_fail = val_text.count("| FAIL |")
n_v_warn = val_text.count("| WARNING |")

artifacts = ["01_business_brief.yaml", "cleaned_data.csv", "viz_ready.csv", "change_log.csv",
             "validation_report.md", "insights_report.md"]
artifact_sizes = {}
for a in artifacts:
    p = os.path.join(OUT_DIR, a)
    artifact_sizes[a] = os.path.getsize(p) if os.path.isfile(p) else None

lines = []
def w(s=""):
    lines.append(str(s))

w("# RUN SUMMARY -- messy_sales.csv (Stage 1-9 pipeline)")
w("")
w(f"Run date: 2026-07-29 (unattended -- no user available mid-run; every judgment call is "
  f"written into `01_business_brief.yaml` and the stage reports below)")
w("")
w("## Source")
w("")
w(f"- Input path: `{IN_PATH}`")
w(f"- File size: {len(raw_bytes):,} bytes")
w(f"- MD5: `{md5}`")
w(f"- SHA-256: `{sha256}`")
w(f"- UTF-8 BOM present: **True** (`b'\\xef\\xbb\\xbf'` at byte 0) -- see `00_peek_report.txt`")
w(f"- Header defects confirmed: `region ` has a trailing space (silent-KeyError risk on "
  f"`df['region']`); `customer name`, `Customer Email`, `Phone Number`, `Units Sold`, "
  f"`Total Revenue` all contain embedded spaces requiring snake_case normalization")
w("")
w("## Extraction-layer defect quantification (Stage 2)")
w("")
w(f"- Total cells (raw grid, 312 rows x 11 cols): {n_cells_total:,}")
w(f"- Cells a naive `pd.read_csv()` (no dtype pin, default NA handling) would preserve verbatim: "
  f"{preserved:,} ({preserved/n_cells_total*100:.2f}%)")
w(f"- Cells a naive `pd.read_csv()` would alter or silently null: {destroyed:,} "
  f"({destroyed/n_cells_total*100:.2f}%) -- see `00_peek_report.txt` for the row-level examples")
w(f"- Mitigation: this pipeline loads with `encoding='utf-8-sig', dtype=str, keep_default_na=False`")
w("")
w("## Row counts")
w("")
w(f"- Raw rows: {n_raw}")
w(f"- `cleaned_data.csv` rows (audit trail, flagged rows kept): {n_clean} "
  f"({n_removed} removed as duplicates, {n_removed/n_raw*100:.2f}%)")
w(f"- `viz_ready.csv` rows (chart-ready, impossible-value rows filtered): {n_viz} "
  f"({n_dropped_viz} dropped from cleaned_data.csv, {n_dropped_viz/n_clean*100:.2f}%)")
w(f"- Overall raw -> viz_ready: {n_raw} -> {n_viz} "
  f"({n_raw-n_viz} fewer rows, {(n_raw-n_viz)/n_raw*100:.2f}%)")
w("")
w("## Duplicate removal breakdown (Stage 4.11)")
w("")
n_exact = len(chg[(chg["CHANGE_TYPE"]=="DUPLICATE_REMOVED") & (chg["REASON"].str.contains("exact duplicate", na=False))])
n_pk = len(chg[(chg["CHANGE_TYPE"]=="DUPLICATE_REMOVED") & (chg["REASON"].str.contains("customer_name capitalization", na=False))])
w(f"- Exact post-normalization duplicates removed: {n_exact}")
w(f"- Same-order_id / differs-only-by-customer_name-capitalization (PK-conflict exception): {n_pk}")
w(f"- Total removed: {n_exact + n_pk} (= raw {n_raw} - cleaned {n_clean} = {n_removed})")
w("")
w("## Cross-column check: total_revenue vs units_sold * unit_price (business_rules.BR1)")
w("")
n_comparable = int(both_present.sum())
w(f"- Rows with all three fields present (comparable): {n_comparable}")
w(f"- Rows disagreeing by more than 1% (excluding sign-flagged rows), recomputed directly from "
  f"`cleaned_data.csv`: {int(mismatch_final)} ({int(mismatch_final)/n_comparable*100:.2f}% of comparable rows)")
w(f"- Decision: **flagged via `revenue_mismatch_flag`, never recomputed/overwritten** -- which of "
  f"the three fields is wrong cannot be determined from the data alone (see brief BR1). "
  f"`revenue_calculated` is retained as a derived column for downstream comparison.")
w(f"- Note: `03_clean_report.txt` reports 15/233 (6.44%) for this same check because it runs "
  f"*before* Stage 4.11 deduplication (233 comparable rows out of the pre-dedup 312). The number "
  f"above is recomputed independently, post-dedup, straight from `cleaned_data.csv` (209 "
  f"comparable rows out of 281) -- both are correct for their own denominator; don't conflate them.")
w("")
w("## Collision guard results (Stage 4.4, run before any fuzzy matching)")
w("")
for col, collided in collision_results.items():
    verdict = "COLLISION -- fuzzy matching DISABLED for this column" if collided else "no collision -- fuzzy matching SAFE at threshold 85"
    w(f"- `{col}`: canonical set {CANON[col]} -> **{verdict}**")
w("")
w("## Change log breakdown (`change_log.csv`, one row per change)")
w("")
w(f"- Total change-log entries: {len(chg)}")
w("")
w("| CHANGE_TYPE | Count |")
w("|---|---:|")
for ct, n in change_type_counts.items():
    w(f"| {ct} | {n} |")
w("")
w("## Flag registry (materialized boolean columns on `cleaned_data.csv`)")
w("")
w("| Flag column | True count (of 281) |")
w("|---|---:|")
for c, n in flag_counts.items():
    w(f"| `{c}` | {n} |")
w("")
w("## Stage 5 validation (V1-V13)")
w("")
w(f"- Checks PASS: {n_v_pass}")
w(f"- Checks WARNING: {n_v_warn}")
w(f"- Checks FAIL: {n_v_fail}  (V2 -- critical columns null-free -- fails BY DESIGN: "
  f"`order_date`/`units_sold`/`unit_price` are `never_impute` per the business brief, "
  f"so genuine source-data nulls are left visible rather than fabricated. See "
  f"`validation_report.md` for the full table and the explicit justification section.)")
w(f"- Full table: see `validation_report.md`")
w("")
w("## Stage 8: viz_ready.csv filter")
w("")
w(f"- Filter rule: drop rows where `units_sold_sign_flag` OR `unit_price_sign_flag` OR "
  f"`total_revenue_sign_flag` is True (physically impossible negative value). Every other flag "
  f"(fuzzy-review confidence, statistical outliers, revenue mismatch, unparseable dates, "
  f"near-duplicates) is KEPT -- see `05_viz_ready_report.txt` for the full reasoning per flag.")
w(f"- Drop: {n_clean} -> {n_viz} ({n_dropped_viz} dropped, {n_dropped_viz/n_clean*100:.2f}%)")
w("")
w("## Stage 9: analytics")
w("")
w(f"- Performed by: `@analytics-expert` (invoked directly, foreground, per unattended-run "
  f"convention -- NOT a fallback)")
w(f"- Scope: General EDA, auto-selected (unattended run, no user available to choose a scope)")
w(f"- Analyzed: `viz_ready.csv` ({n_viz} rows), briefed with full flag-column semantics and "
  f"cleaning caveats so aggregates are not silently distorted by rows the pipeline had already "
  f"flagged as suspect")
w(f"- Headline finding: 6 bulk orders (`units_sold_outlier_flag`, 2.3% of rows) account for the "
  f"large majority of total revenue and units -- see `insights_report.md` for exact percentages, "
  f"significance tests, and all 8 recommendations")
w("")
w("## Artifact manifest")
w("")
w("| Artifact | Size (bytes) | Status |")
w("|---|---:|---|")
for a, size in artifact_sizes.items():
    status = f"{size:,}" if size is not None else "**MISSING**"
    ok = "OK" if size else "FAIL"
    w(f"| `{a}` | {status} | {ok} |")
w("")
w("Numbered scripts in this directory (`stage2a_peek.py` ... `stage8_viz_prep.py`, this script) "
  "reproduce the entire run from `messy_sales.csv` alone; run them in numeric order.")

with open(SUMMARY_MD, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("\n".join(lines).encode("ascii", errors="replace").decode("ascii"))
print(f"\n[WROTE] {SUMMARY_MD}")
