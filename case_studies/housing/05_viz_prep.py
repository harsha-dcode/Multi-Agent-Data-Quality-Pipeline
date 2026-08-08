# -*- coding: utf-8 -*-
"""
Stage 8: Pre-Viz Prep. Reads cleaned_data.csv, writes viz_ready.csv.
Filter ONLY physically impossible values; KEEP statistical oddities.
"""
import sys
import pandas as pd
import numpy as np
import json

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = str(_HERE)
report = []
def rlog(s):
    report.append(s)
    print(s)

df = pd.read_csv(f"{BASE}\\cleaned_data.csv", encoding="utf-8", parse_dates=["listing_date"])
with open(f"{BASE}\\_flag_registry.json", encoding="utf-8") as jf:
    flag_registry = json.load(jf)

rlog("STAGE 8 PRE-VIZ PREP")
rlog(f"\nInput (cleaned_data.csv): {len(df)} rows")

# Inventory flags actually present on the dataframe
rlog("\nFlag inventory (from Stage 4 flag registry, confirmed against actual dataframe columns):")
flag_cols_present = [c for c in df.columns if c.endswith("_flag")]
if not flag_cols_present:
    raise RuntimeError("BUG: zero flag columns found on cleaned_data.csv -- flags were not materialized. See Stage 4.0.")
for c in flag_cols_present:
    true_count = int(df[c].sum())
    meaning = flag_registry.get(c, "(no registry entry -- investigate)")
    rlog(f"  {c}: True count={true_count} | meaning: {meaning}")

# ---------------------------------------------------------------------
# Decide filter vs keep, per flag, with justification
# ---------------------------------------------------------------------
rlog("\nFilter-vs-keep decisions:")

# FILTER: total_area_sign_flag -- a negative area cannot be charted honestly (physically impossible)
filter_mask = pd.Series(False, index=df.index)

reason_log = {}

m = df["total_area_sign_flag"]
filter_mask |= m
reason_log["total_area_sign_flag"] = f"FILTER ({m.sum()} rows) -- negative total_area is physically impossible; a chart bucketing/summing area would be actively wrong if it included these."

# FILTER: built_year_future_flag -- physically impossible (0 rows in this dataset, but the rule stands)
m = df["built_year_future_flag"]
filter_mask |= m
reason_log["built_year_future_flag"] = f"FILTER ({m.sum()} rows) -- built_year in the future is physically impossible."

# KEEP: total_area_outlier_flag -- statistical oddity (real large estates), not an error
reason_log["total_area_outlier_flag"] = f"KEEP ({int(df['total_area_outlier_flag'].sum())} rows) -- genuinely large properties exist in every property_type (BR4); dropping them would understate real price/area variance, not correct an error."

# KEEP: price_per_sqm_outlier_flag -- explained by total_area being small, not an error
reason_log["price_per_sqm_outlier_flag"] = f"KEEP ({int(df['price_per_sqm_outlier_flag'].sum())} rows) -- mathematically explained by final_sale_price/total_area (BR6); the underlying row is legitimate."

# KEEP: final_sale_price_outlier_flag / listing_price_outlier_flag -- genuine luxury listings, cross-checked
reason_log["final_sale_price_outlier_flag"] = f"KEEP ({int(df['final_sale_price_outlier_flag'].sum())} rows) -- cross-checked against listing_price, genuine luxury listings (BR5). Excluding them would bias any price distribution/mean downward and hide the luxury segment entirely."
reason_log["listing_price_outlier_flag"] = f"KEEP ({int(df['listing_price_outlier_flag'].sum())} rows) -- cross-checked against final_sale_price, genuine luxury listings (BR9). Same reasoning as final_sale_price_outlier_flag."

# KEEP: land_area_outlier_flag (0 rows currently, but stands as a rule) -- statistical, not impossible
reason_log["land_area_outlier_flag"] = f"KEEP ({int(df['land_area_outlier_flag'].sum())} rows) -- statistical outlier only, no divisor test passed so nothing was corrected or judged impossible."

# KEEP: land_area_decimal_typo_flag -- this WAS already corrected upstream in Stage 4.10, the
# flag just documents that a value was changed; the row itself is not excluded from charts.
reason_log["land_area_decimal_typo_flag"] = f"KEEP ({int(df['land_area_decimal_typo_flag'].sum())} rows) -- value was already corrected in Stage 4.10 (divided by 10, landed in-band); the corrected value is safe to chart, this flag is provenance only."

for k, v in reason_log.items():
    rlog(f"  {k}: {v}")

viz = df[~filter_mask].copy()
rlog(f"\nRows filtered (physically impossible only): {filter_mask.sum()}")
rlog(f"viz_ready row count: {len(df)} -> {len(viz)} ({filter_mask.sum()} dropped, {filter_mask.sum()/len(df)*100:.2f}%)")

# ---------------------------------------------------------------------
# Recompute derived date parts from the cleaned date column (never trust
# a pre-existing derived column) -- already done in Stage 7, but Stage 8
# recomputes/re-verifies here on the filtered frame to be safe.
# ---------------------------------------------------------------------
recomputed_year = viz["listing_date"].dt.year
recomputed_month = viz["listing_date"].dt.month
mismatch_year = (recomputed_year != viz["listing_year"]).sum()
mismatch_month = (recomputed_month != viz["listing_month"]).sum()
rlog(f"\nRecomputed listing_year/listing_month from listing_date, cross-checked against Stage-7 derived columns: "
     f"{mismatch_year} year mismatches, {mismatch_month} month mismatches (expected 0, since Stage 7 already derived these the same way)")
viz["listing_year"] = recomputed_year
viz["listing_month"] = recomputed_month

viz.to_csv(f"{BASE}\\viz_ready.csv", index=False, encoding="utf-8")
rlog(f"\nWrote viz_ready.csv: {viz.shape[0]} rows x {viz.shape[1]} cols")

with open(f"{BASE}\\05_viz_prep_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(report))

print("\n05_viz_prep.py COMPLETE")
