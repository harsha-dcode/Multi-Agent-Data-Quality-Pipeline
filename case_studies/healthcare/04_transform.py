# -*- coding: utf-8 -*-
"""
Stage 6 (Data Integration - N/A, single source) + Stage 7 (Data Transformation)
Reads 03_intermediate_cleaned.csv, applies:
  - BR6: drop pre-existing admission_year/admission_month/admission_yearmonth, recompute from
    cleaned date_of_admission; quantify disagreement with the dropped columns before dropping.
  - Final dtype enforcement
  - Column reordering (identifiers -> dates -> categorical -> numeric)
  - Final null check (leave_null default per brief missing_value_strategy; NO imputation occurred
    anywhere in this run, so no *_imputed columns are created - stated explicitly)
  - Index reset (0-based), __source_row preserved as a column
Appends to change_log.csv / change_log.csv (same files, append mode).
Writes: cleaned_data.csv (final deliverable), 04_stage7_report.txt
"""
import pandas as pd
import numpy as np
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

extra_log = []
def log(stage, column, source_row, change_type, orig, new, reason):
    extra_log.append({
        "STAGE": stage, "COLUMN": column, "SOURCE_ROW": source_row,
        "CHANGE_TYPE": change_type, "ORIGINAL_VALUE": orig, "NEW_VALUE": new, "REASON": reason
    })

df = pd.read_csv(os.path.join(OUT_DIR, "03_intermediate_cleaned.csv"), encoding="utf-8", low_memory=False)
rprint(f"Loaded 03_intermediate_cleaned.csv: {df.shape}")

with open(os.path.join(OUT_DIR, "03_flag_registry.json"), "r", encoding="utf-8") as f:
    FLAG_REGISTRY = json.load(f)

rprint("\nSTAGE 6: DATA INTEGRATION - N/A, Single Source (only one input file was provided: "
       "healthcare_dataset_dirty_export.csv). No join/merge performed.")

# =====================================================================================
# STAGE 7: TRANSFORMATION
# =====================================================================================

# ---- BR6: drop distrusted pre-existing derived date-part columns, recompute from cleaned date_of_admission ----
df["date_of_admission"] = pd.to_datetime(df["date_of_admission"], errors="coerce")
df["discharge_date"] = pd.to_datetime(df["discharge_date"], errors="coerce")

# quantify disagreement between old admission_year (raw, pre-existing) and year(date_of_admission)
old_year = pd.to_numeric(df["admission_year"], errors="coerce")
new_year_from_date = df["date_of_admission"].dt.year
comparable = old_year.notna() & new_year_from_date.notna()
disagree = comparable & (old_year != new_year_from_date)
rprint(f"\nBR6 disagreement check: pre-existing admission_year vs year(cleaned date_of_admission): "
       f"{int(comparable.sum())} rows comparable, {int(disagree.sum())} disagree "
       f"({100*disagree.sum()/comparable.sum():.2f}% of comparable rows)")

n_dropped_cols_rows = len(df)
for c in ["admission_year", "admission_month", "admission_yearmonth"]:
    log("Stage7", c, "ALL", "DERIVED_COLUMN_ADDED", "pre-existing raw column", "DROPPED",
        f"BR6: pre-existing derived column dropped - disagreed with date_of_admission on "
        f"{int(disagree.sum())}/{int(comparable.sum())} comparable rows and is not trustworthy; "
        f"replaced by a same-named column recomputed directly from the CLEANED date_of_admission below")
    df = df.drop(columns=[c])

df["admission_year"] = df["date_of_admission"].dt.year
df["admission_month"] = df["date_of_admission"].dt.month
df["admission_yearmonth"] = df["date_of_admission"].dt.strftime("%Y-%m")
for c in ["admission_year", "admission_month", "admission_yearmonth"]:
    log("Stage7", c, "ALL", "DERIVED_COLUMN_ADDED", "", "recomputed from cleaned date_of_admission",
        "BR6: recomputed derived column (replaces dropped, distrusted pre-existing raw column)")
rprint("admission_year / admission_month / admission_yearmonth: dropped pre-existing raw columns, "
       "recomputed fresh from cleaned date_of_admission (BR6)")

# ---- additional derived column: length_of_stay_recomputed (QA cross-check, already flagged in Stage4;
# exposing the recomputed value itself here as a documented derived column, not overwriting source) ----
df["length_of_stay_recomputed_days"] = (df["discharge_date"] - df["date_of_admission"]).dt.days
log("Stage7", "length_of_stay_recomputed_days", "ALL", "DERIVED_COLUMN_ADDED", "",
    "discharge_date - date_of_admission (days)",
    "QA-only derived column exposing the date-based recomputation used for length_of_stay_qa_mismatch_flag in Stage 4.10; source length_of_stay is authoritative and unchanged")
rprint("length_of_stay_recomputed_days: derived column added (QA reference only, source length_of_stay untouched)")

# ---- Final dtype enforcement ----
rprint("\nFinal dtype enforcement:")
dtype_before = df.dtypes.copy()
NUMERIC_FLOAT = ["age", "billing_amount", "room_number", "length_of_stay", "length_of_stay_recomputed_days",
                  "admission_year", "admission_month"]
for c in NUMERIC_FLOAT:
    df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    log("Stage7", c, "ALL", "DTYPE_CAST", str(dtype_before.get(c)), "float64", "final dtype enforcement")

CATEGORY_COLS = ["gender", "blood_type", "medical_condition", "admission_type", "insurance_provider",
                  "test_results", "medication"]
for c in CATEGORY_COLS:
    df[c] = df[c].astype("category")
    log("Stage7", c, "ALL", "DTYPE_CAST", str(dtype_before.get(c)), "category", "final dtype enforcement - low cardinality categorical")

for c in ["date_of_admission", "discharge_date"]:
    log("Stage7", c, "ALL", "DTYPE_CAST", str(dtype_before.get(c)), "datetime64[ns]", "final dtype enforcement (already datetime from parsing)")

flag_cols = [c for c in df.columns if c.endswith("_flag")]
for c in flag_cols:
    df[c] = df[c].astype(bool)
rprint(f"  {len(NUMERIC_FLOAT)} numeric cols -> float64, {len(CATEGORY_COLS)} cols -> category, "
      f"2 date cols -> datetime64[ns], {len(flag_cols)} flag cols -> bool")

# ---- Final null check: leave_null default (per brief), flag REQUIRES_MANUAL_REVIEW, NO imputation ----
rprint("\nFinal null check (per brief missing_value_strategy - all columns are never_impute or leave_null; "
       "ZERO imputation performed in this run, so ZERO *_imputed columns are created):")
requires_review = []
for c in df.columns:
    if c == "__source_row" or c.endswith("_flag"):
        continue
    n_null = int(df[c].isna().sum())
    if n_null > 0:
        missing_flag_col = f"{c}_missing_flag"
        df[missing_flag_col] = df[c].isna()
        FLAG_REGISTRY[missing_flag_col] = f"True if {c} is null in the final cleaned dataset - left null per brief missing_value_strategy (never_impute/leave_null), not filled"
        requires_review.append((c, n_null))
        for idx in df[df[c].isna()].index:
            row = df.loc[idx, "__source_row"]
            log("Stage7", c, row, "NULL_FLAGGED_NOT_IMPUTED", "", "", "leave_null/never_impute per brief - left null, flagged for manual review, not guessed")
        rprint(f"  {c}: {n_null} nulls -> REQUIRES_MANUAL_REVIEW, {missing_flag_col} set")

# ---- Column reordering: identifiers -> dates -> categorical -> numeric -> flags ----
ID_COLS = ["__source_row", "name", "doctor", "hospital", "room_number"]
DATE_COLS = ["date_of_admission", "discharge_date", "admission_year", "admission_month", "admission_yearmonth"]
CAT_COLS_ORDER = ["gender", "blood_type", "medical_condition", "admission_type", "insurance_provider", "test_results", "medication"]
NUM_COLS_ORDER = ["age", "billing_amount", "length_of_stay", "length_of_stay_recomputed_days"]
rest = [c for c in df.columns if c not in ID_COLS + DATE_COLS + CAT_COLS_ORDER + NUM_COLS_ORDER]
final_order = ID_COLS + DATE_COLS + CAT_COLS_ORDER + NUM_COLS_ORDER + rest
final_order = [c for c in final_order if c in df.columns]
df = df[final_order]
log("Stage7", "ALL", "ALL", "COLUMN_REORDERED", "", "", "identifiers -> dates -> categorical descriptors -> numeric measures -> flags")
rprint(f"\nColumn reordering applied: {len(final_order)} columns")

# ---- Final re-dedup: dropping the distrusted admission_year/month/yearmonth raw columns (BR6)
# removes the only distinguishing values between some row pairs that were near-duplicates in the
# raw file already (same name/date/doctor/hospital/billing_amount casing-normalized identically),
# so they collapse to EXACT duplicates only now. This is the same phenomenon documented for the
# Stage-4 dedup (normalizing away noise reveals previously-hidden true duplicates) - it must be
# re-checked here because Stage 7 changes the column set after Stage 4's dedup already ran.
dedup_cols_final = [c for c in df.columns if c != "__source_row"]
post_transform_dup_mask = df.duplicated(subset=dedup_cols_final, keep="first")
n_post_transform_dup = int(post_transform_dup_mask.sum())
if n_post_transform_dup > 0:
    for idx in df[post_transform_dup_mask].index:
        row = df.loc[idx, "__source_row"]
        log("Stage7", "ALL", row, "DUPLICATE_REMOVED", "", "",
            "exact full-row duplicate discovered ONLY after Stage 7 dropped the distrusted "
            "admission_year/admission_month/admission_yearmonth raw columns (BR6) - this row pair "
            "agreed on every other cleaned column and differed only in those now-removed columns; "
            "kept first occurrence by __source_row order")
    df = df[~post_transform_dup_mask].copy()
rprint(f"\nPost-transform re-dedup (triggered by BR6 column drop): {n_post_transform_dup} additional exact duplicates removed")

# ---- Index reset, __source_row preserved as a column ----
df = df.reset_index(drop=True)
assert "__source_row" in df.columns, "CRITICAL: __source_row missing after index reset!"
rprint(f"\nIndex reset to 0-based; __source_row CONFIRMED present as a column (verified: {'__source_row' in df.columns})")

df.to_csv(os.path.join(OUT_DIR, "cleaned_data.csv"), index=False, encoding="utf-8")
rprint(f"\ncleaned_data.csv written: {df.shape}")

# append this stage's log entries to the canonical change log files
extra_df = pd.DataFrame(extra_log, columns=["STAGE","COLUMN","SOURCE_ROW","CHANGE_TYPE","ORIGINAL_VALUE","NEW_VALUE","REASON"])
extra_df.to_csv(os.path.join(OUT_DIR, "change_log.csv"), mode="a", header=False, index=False, encoding="utf-8")
extra_df.to_csv(os.path.join(OUT_DIR, "change_log.csv"), mode="a", header=False, index=False, encoding="utf-8")
rprint(f"Appended {len(extra_df)} Stage 6/7 change-log entries to change_log.csv / change_log.csv")

with open(os.path.join(OUT_DIR, "03_flag_registry.json"), "w", encoding="utf-8") as f:
    json.dump(FLAG_REGISTRY, f, indent=2)
rprint(f"03_flag_registry.json updated: {len(FLAG_REGISTRY)} total flags")

with open(os.path.join(OUT_DIR, "04_stage7_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(report))
print("\n=== 04_transform.py COMPLETE ===")
print("Final cleaned_data.csv shape:", df.shape)
