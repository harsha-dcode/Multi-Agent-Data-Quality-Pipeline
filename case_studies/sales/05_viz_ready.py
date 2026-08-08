#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
05_viz_ready.py -- Stage 8 (Pre-Viz Prep): produce viz_ready.csv from cleaned_data.csv.

Filter-vs-keep rule (per business brief BR2 and the standing unattended-run convention):
FILTER rows flagged for a value that is PHYSICALLY IMPOSSIBLE for a sales order (negative
units_sold / unit_price / total_revenue). KEEP everything else, including statistical
outliers, fuzzy-review-band corrections, revenue_mismatch rows, and near-duplicates --
none of those are impossible, they are merely uncertain, and dropping them would throw away
real rows on a judgment call a chart consumer should be able to see, not have hidden.
"""
import os
import pandas as pd

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

OUT_DIR = str(_HERE)
CLEANED_CSV = os.path.join(OUT_DIR, "cleaned_data.csv")
VIZ_CSV = os.path.join(OUT_DIR, "viz_ready.csv")
REPORT = os.path.join(OUT_DIR, "05_viz_ready_report.txt")

df = pd.read_csv(CLEANED_CSV, parse_dates=["order_date"])

lines = []
def log(s=""):
    lines.append(str(s))

flag_cols = [c for c in df.columns if c.endswith("_flag")]
log("=" * 78)
log("STAGE 8 -- PRE-VIZ PREP")
log("=" * 78)
log(f"\nFlag inventory (from cleaned_data.csv, {len(df)} rows):")
for c in sorted(flag_cols):
    log(f"  {c}: True count = {int(df[c].sum())}")

if not flag_cols:
    raise SystemExit("BUG: zero flag columns found on cleaned_data.csv -- Stage 4 flags were "
                      "not materialized as dataframe columns. Refusing to produce viz_ready.csv "
                      "silently identical to cleaned_data.csv.")

IMPOSSIBLE_FLAGS = ["units_sold_sign_flag", "unit_price_sign_flag", "total_revenue_sign_flag"]
STATISTICAL_FLAGS = [c for c in flag_cols if c not in IMPOSSIBLE_FLAGS]

log(f"\nFILTER (physically impossible) flags: {IMPOSSIBLE_FLAGS}")
log(f"KEEP (statistical/uncertain, not impossible) flags: {STATISTICAL_FLAGS}")
log("\nReasoning per KEEP flag:")
log("  *_outlier_flag / units_sold_non_integer_flag: a large-but-real order or an odd count is")
log("    still a real order -- statistically unusual, not impossible.")
log("  *_fuzzy_review_flag / *_unknown_category_flag: a lower-confidence categorical correction")
log("    still has SOME value in the row; the correction is uncertain, the row is not invalid.")
log("  order_date_unparseable_flag: the date is unusable for a time-series cut, but the order's")
log("    revenue/volume is still real and countable in a non-time-series aggregate; a BI tool")
log("    can decide per-chart whether to exclude it, which is a charting decision, not a data one.")
log("  phone_number_country_unknown_flag / customer_email_*: contact metadata, not a sales measure.")
log("  revenue_mismatch_flag: BOTH total_revenue and revenue_calculated exist and disagree --")
log("    that's genuinely ambiguous, not impossible; dropping it would silently pick a side.")
log("  near_duplicate_flag: a real conflict with no clear resolution -- kept for visibility, not")
log("    auto-resolved by deletion.")

impossible_mask = df[IMPOSSIBLE_FLAGS].any(axis=1)
n_before = len(df)
n_dropped = int(impossible_mask.sum())
viz = df.loc[~impossible_mask].copy()
n_after = len(viz)

log(f"\nRow count: {n_before} -> {n_after} ({n_dropped} dropped, {n_dropped/n_before*100:.2f}%)")

# recompute derived date parts from the cleaned order_date rather than trusting anything upstream
# (there is no pre-existing year/month column in this source, so this is a fresh derivation, not
# a distrust-and-recompute situation -- still done here per spec, for anything downstream that
# wants a period cut).
viz["order_year"] = viz["order_date"].dt.year
viz["order_month"] = viz["order_date"].dt.month
viz["order_yearmonth"] = viz["order_date"].dt.to_period("M").astype(str)
viz.loc[viz["order_date"].isna(), ["order_year", "order_month", "order_yearmonth"]] = pd.NA

viz.to_csv(VIZ_CSV, index=False, encoding="utf-8")
log(f"\n[WROTE] {VIZ_CSV}  shape={viz.shape}")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines).encode("ascii", errors="replace").decode("ascii"))
print(f"\n[WROTE] {REPORT}")
