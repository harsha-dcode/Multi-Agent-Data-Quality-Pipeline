# -*- coding: utf-8 -*-
"""
Stage 8: PRE-VIZ PREP
Filter ONLY physically-impossible rows (per run instructions): discharge before admission, or a
null in a column a chart is keyed to. KEEP statistical oddities (age>110, unresolved fuzzy
matches, QA mismatches, near-duplicate collisions) - a genuinely large/odd value is data, not an
error, and dropping it would lie by omission. Recompute derived date parts (already done fresh
in Stage 7 from the cleaned date_of_admission - inherited, not re-trusted from raw).
"""
import pandas as pd
import json
import os

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

OUT_DIR = str(_HERE)

report = []
def rprint(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    report.append(s)

df = pd.read_csv(os.path.join(OUT_DIR, "cleaned_data.csv"), encoding="utf-8", low_memory=False)
with open(os.path.join(OUT_DIR, "03_flag_registry.json"), "r", encoding="utf-8") as f:
    FLAG_REGISTRY = json.load(f)

rows_before = len(df)
rprint(f"cleaned_data.csv loaded: {df.shape}")

# ---- Inventory every flag column against the registry (mandatory check) ----
flag_cols_in_df = [c for c in df.columns if c.endswith("_flag")]
rprint(f"\nFlag inventory: {len(flag_cols_in_df)} flag columns present in dataframe, {len(FLAG_REGISTRY)} in registry")
missing_from_df = set(FLAG_REGISTRY) - set(flag_cols_in_df)
missing_from_registry = set(flag_cols_in_df) - set(FLAG_REGISTRY)
rprint(f"  registered-but-missing-from-df: {missing_from_df}")
rprint(f"  present-in-df-but-unregistered: {missing_from_registry}")
assert not missing_from_df, "BUG: a registered flag is missing from the dataframe - Stage 8 cannot proceed safely"
for c in flag_cols_in_df:
    rprint(f"  {c}: True count = {int(df[c].sum())}  -- {FLAG_REGISTRY.get(c, '(unregistered)')}")

# =====================================================================================
# FILTER decision: physically impossible ONLY.
# =====================================================================================
rprint("\n--- FILTER vs KEEP decisions ---")

# 1) discharge_date < date_of_admission -> physically impossible -> FILTER
filter_mask = df["discharge_before_admission_flag"].astype(bool)
rprint(f"FILTER: discharge_before_admission_flag = True -> {int(filter_mask.sum())} rows "
       f"(physically impossible: a discharge cannot precede the admission it belongs to)")

# 2) null in a column a chart is keyed to: date_of_admission (time-series axis) and
#    admission_type / billing_amount (both critical, both commonly used as chart keys/measures)
# A chart keyed to a null date has no x-axis position; a chart keyed to a null admission_type has
# no category to bucket into. billing_amount nulls are KEPT for non-financial charts (e.g. LOS by
# condition) but any row null on date_of_admission or admission_type cannot be placed in ANY
# standard chart in this dataset, so they are filtered here.
null_key_mask = df["date_of_admission"].isna() | df["admission_type"].isna()
rprint(f"FILTER: null in a chart-keying column (date_of_admission or admission_type) -> {int(null_key_mask.sum())} rows")

combined_filter = filter_mask | null_key_mask
rprint(f"FILTER (union, dedup): {int(combined_filter.sum())} rows total")

# ---- KEEP explicitly (statistical oddities, not physically impossible) ----
keep_cols = [
    "age_domain_outlier_flag", "gender_unresolved_category_flag", "blood_type_unresolved_category_flag",
    "medical_condition_unresolved_category_flag", "insurance_provider_unresolved_category_flag",
    "test_results_unresolved_category_flag", "medication_unresolved_category_flag",
    "length_of_stay_qa_mismatch_flag", "near_duplicate_composite_key_flag",
    "billing_amount_sign_flag", "date_of_admission_ambiguous_date_flag", "discharge_date_ambiguous_date_flag",
]
for c in keep_cols:
    if c in df.columns:
        rprint(f"KEEP (statistical oddity, not physically impossible): {c} = {int(df[c].sum())} rows retained")

viz = df[~combined_filter].copy()
rows_after = len(viz)
rprint(f"\nviz_ready row count: {rows_before} -> {rows_after} "
       f"({rows_before - rows_after} dropped, {100*(rows_before-rows_after)/rows_before:.2f}%)")

# Recompute derived date parts fresh from the (already-cleaned) date_of_admission for the viz subset
# rather than trusting any carried-over value (defensive re-derivation, per Stage 8 spec).
viz["date_of_admission"] = pd.to_datetime(viz["date_of_admission"], errors="coerce")
viz["admission_year"] = viz["date_of_admission"].dt.year
viz["admission_month"] = viz["date_of_admission"].dt.month
viz["admission_yearmonth"] = viz["date_of_admission"].dt.strftime("%Y-%m")
rprint("Derived date parts (admission_year/month/yearmonth) recomputed fresh from date_of_admission for the viz subset.")

viz.to_csv(os.path.join(OUT_DIR, "viz_ready.csv"), index=False, encoding="utf-8")
rprint(f"\nviz_ready.csv written: {viz.shape}")

with open(os.path.join(OUT_DIR, "06_stage8_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(report))
print("\n=== 06_viz_prep.py COMPLETE ===")
