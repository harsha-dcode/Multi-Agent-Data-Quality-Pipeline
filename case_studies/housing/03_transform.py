# -*- coding: utf-8 -*-
"""
Stage 6 (Integration -- N/A, single source) + Stage 7 (Transformation).
Reads _intermediate_post_stage4.csv, writes cleaned_data.csv (final artifact).
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

rlog("STAGE 6 INTEGRATION: N/A -- Single Source (house_50k_sample.csv only)")

df = pd.read_csv(f"{BASE}\\_intermediate_post_stage4.csv", encoding="utf-8")
rlog(f"\nSTAGE 7 TRANSFORMATION: loaded {df.shape[0]} rows x {df.shape[1]} cols from post-Stage-4 intermediate")

with open(f"{BASE}\\_flag_registry.json", encoding="utf-8") as jf:
    flag_registry = json.load(jf)

# ---------------------------------------------------------------------
# Final dtype enforcement
# ---------------------------------------------------------------------
rlog("\nFinal dtype enforcement:")
INT_COLS = ["property_id", "bedrooms", "bathrooms", "floors", "parking_spots", "built_year",
            "days_on_market", "price_revision_count"]
STRING_ID_COLS = ["postal_code"]  # identifier, not a quantity -- kept as string per brief column_types
# (postal_code has no leading-zero risk in this data -- observed range [10000,99995], always 5
# digits -- but it is still semantically an ID, not something to sum/average, so it is not cast
# to int64 even though it would round-trip losslessly as one)
FLOAT_COLS = ["total_area", "land_area", "latitude", "longitude", "interest_rate", "inflation_index",
              "housing_index", "luxury_demand_index", "final_sale_price", "listing_price",
              "price_per_sqm", "hoa_fee", "property_tax"] + [f"noise_{i}" for i in range(15)]
CATEGORY_COLS = ["country", "property_type", "condition", "city", "currency"]
DATE_COLS = ["listing_date"]
BOOL_COLS = [c for c in df.columns if c.endswith("_flag")]

for c in INT_COLS:
    df[c] = pd.to_numeric(df[c], errors="raise").astype("int64")
for c in STRING_ID_COLS:
    df[c] = df[c].astype("int64").astype(str)  # normalize representation, then keep as identifier string
for c in FLOAT_COLS:
    df[c] = pd.to_numeric(df[c], errors="raise").astype("float64")
for c in CATEGORY_COLS:
    df[c] = df[c].astype("category")
for c in DATE_COLS:
    df[c] = pd.to_datetime(df[c])
for c in BOOL_COLS:
    df[c] = df[c].astype(bool)
rlog(f"  int64: {INT_COLS}")
rlog(f"  string (identifier, not quantity): {STRING_ID_COLS}")
rlog(f"  float64: {FLOAT_COLS}")
rlog(f"  category: {CATEGORY_COLS}")
rlog(f"  datetime64: {DATE_COLS}")
rlog(f"  bool (flags): {BOOL_COLS}")
rlog(f"  string (kept as object -- free text / district / __source_row is int): title, description, district")

# ---------------------------------------------------------------------
# Derived columns
# ---------------------------------------------------------------------
rlog("\nDerived columns:")
CURRENT_YEAR = 2026
CURRENT_DATE = pd.Timestamp("2026-07-29")

df["property_age_years"] = CURRENT_YEAR - df["built_year"]
rlog("  property_age_years = 2026 - built_year")

df["listing_year"] = df["listing_date"].dt.year
df["listing_month"] = df["listing_date"].dt.month
rlog("  listing_year / listing_month RECOMPUTED from the cleaned listing_date column (Stage 8 requirement -- never trust a pre-existing derived date part)")

df["price_to_listing_ratio"] = df["final_sale_price"] / df["listing_price"]
rlog("  price_to_listing_ratio = final_sale_price / listing_price (the same ratio used for the BR5/BR9 decimal-typo cross-checks -- exposed as a real KPI for Stage 9)")

df["listing_days_since_run_date"] = (CURRENT_DATE - df["listing_date"]).dt.days
rlog("  listing_days_since_run_date = days between listing_date and this pipeline run date (2026-07-29)")

# ---------------------------------------------------------------------
# Final null check -- flag by default, impute only on explicit instruction
# ---------------------------------------------------------------------
rlog("\nFinal null check:")
null_counts = df.isna().sum()
any_nulls = null_counts[null_counts > 0]
if len(any_nulls) == 0:
    rlog("  0 nulls in any column post-cleaning -- no imputation needed or performed (matches brief: 0 null disguises found in Stage 3 profiling, missing_value_strategy per column is moot on this run)")
else:
    rlog(f"  WARNING: nulls found where none were expected: {any_nulls.to_dict()}")

# ---------------------------------------------------------------------
# Column ordering: identifiers, dates, categorical descriptors, numeric measures, flags, free text
# ---------------------------------------------------------------------
ordered = (
    ["__source_row", "property_id"] +
    ["listing_date", "listing_year", "listing_month", "listing_days_since_run_date"] +
    ["country", "city", "district", "postal_code", "property_type", "condition", "currency"] +
    ["bedrooms", "bathrooms", "floors", "parking_spots", "built_year", "property_age_years"] +
    ["total_area", "land_area", "latitude", "longitude"] +
    ["final_sale_price", "listing_price", "price_to_listing_ratio", "price_per_sqm",
     "hoa_fee", "property_tax", "days_on_market", "price_revision_count"] +
    ["interest_rate", "inflation_index", "housing_index", "luxury_demand_index"] +
    ["title", "description"] +
    BOOL_COLS +
    [f"noise_{i}" for i in range(15)]
)
missing_from_order = set(df.columns) - set(ordered)
extra_in_order = set(ordered) - set(df.columns)
rlog(f"\nColumn reorder: {len(ordered)} columns placed; unaccounted-for columns: {missing_from_order if missing_from_order else 'NONE'}; "
     f"phantom columns in order list not in df: {extra_in_order if extra_in_order else 'NONE'}")
assert not missing_from_order, f"Column(s) missing from reorder list: {missing_from_order}"
assert not extra_in_order, f"Column(s) in reorder list but not in df: {extra_in_order}"
df = df[ordered]

# ---------------------------------------------------------------------
# Index reset -- keep __source_row as a column
# ---------------------------------------------------------------------
df = df.reset_index(drop=True)
assert "__source_row" in df.columns, "__source_row lost during transform!"
rlog(f"\nIndex reset to clean 0..{len(df)-1}; __source_row column confirmed present (min={df['__source_row'].min()}, max={df['__source_row'].max()}, nunique={df['__source_row'].nunique()})")

# ---------------------------------------------------------------------
# Write final cleaned_data.csv
# ---------------------------------------------------------------------
df.to_csv(f"{BASE}\\cleaned_data.csv", index=False, encoding="utf-8")
rlog(f"\nWrote cleaned_data.csv: {df.shape[0]} rows x {df.shape[1]} cols")
rlog(f"Final columns: {list(df.columns)}")

with open(f"{BASE}\\03_transform_report.txt", "w", encoding="utf-8") as rf:
    rf.write("\n".join(report))

print("\n03_transform.py COMPLETE")
