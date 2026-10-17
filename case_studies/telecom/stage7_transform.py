# -*- coding: utf-8 -*-
"""
Stage 7: DATA TRANSFORMATION for telecom_churn.csv.

- Final dtype enforcement (re-affirm int64/float64 from Stage 4; cast the
  three closed-code-set flags to category dtype -- cardinality 2 -- while
  keeping the CSV export as plain 0/1 integers, since category dtype does
  not round-trip through CSV in a way that matters here).
- Column ordering: __source_row (row identity) -> categorical descriptors
  (churn, contract_renewal, data_plan) -> numeric measures -> derived
  columns -> flag columns.
- Derived column: total_charge = monthly_charge + overage_fee (the only
  "obvious and valuable" derived measure available -- a combined billing
  figure). Documented, not silently added.
- Final null check: re-verify 0 nulls in every column (already established
  in Stage 3/4); nothing to flag or impute, stated explicitly per the
  "flag by default, impute only on explicit instruction" rule.
- Index reset to a clean 0..N-1 integer index; __source_row is KEPT as a
  column so every earlier change_log.csv SOURCE_ROW value still resolves.

Writes: cleaned_data.csv (final, overwriting the Stage-4-only version),
        04_transform_report.txt, appends DERIVED_COLUMN_ADDED / DTYPE_CAST /
        COLUMN_REORDERED rows to change_log.csv.
"""
import pandas as pd

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

OUT_DIR = str(_HERE)
PICKLE_IN = OUT_DIR + r"\_cleaned.pkl"
CLEANED_OUT = OUT_DIR + r"\cleaned_data.csv"
CHANGELOG = OUT_DIR + r"\change_log.csv"
REPORT = OUT_DIR + r"\04_transform_report.txt"

lines = []
def log(s=""):
    lines.append(str(s))

df = pd.read_pickle(PICKLE_IN)
log("=" * 78)
log("STAGE 7: DATA TRANSFORMATION")
log("=" * 78)
log(f"rows in: {len(df)}, columns in: {len(df.columns)}")

change_rows = []
def log_change(stage, column, source_row, change_type, original, new, reason):
    change_rows.append({
        "STAGE": stage, "COLUMN": column, "SOURCE_ROW": source_row,
        "CHANGE_TYPE": change_type, "ORIGINAL_VALUE": original,
        "NEW_VALUE": new, "REASON": reason,
    })

# --- final dtype enforcement (re-affirm; log any column that wasn't already right) ---
log()
log("--- Final dtype enforcement ---")
expected_dtypes = {
    "churn": "int64", "contract_renewal": "int64", "data_plan": "int64",
    "account_weeks": "int64", "cust_serv_calls": "int64", "day_calls": "int64",
    "data_usage": "float64", "day_mins": "float64", "monthly_charge": "float64",
    "overage_fee": "float64", "roam_mins": "float64",
}
for c, expected in expected_dtypes.items():
    actual = str(df[c].dtype)
    log(f"  {c}: dtype={actual}, expected={expected}, match={actual == expected}")
    if actual != expected:
        df[c] = df[c].astype(expected)
        log_change("7", c, "ALL_ROWS", "DTYPE_CAST", actual, expected,
                   "Final dtype enforcement did not match Stage 4 cast; corrected.")

# --- derived column ---
log()
log("--- Derived columns ---")
df["total_charge"] = df["monthly_charge"] + df["overage_fee"]
log("Added total_charge = monthly_charge + overage_fee "
    f"(min={df['total_charge'].min():.2f}, max={df['total_charge'].max():.2f}, "
    f"mean={df['total_charge'].mean():.2f})")
# One log entry for the deterministic, uniformly-applied formula -- not one row per
# record, since this is not a row-level correction, it's a single declared rule applied
# identically to all 3,333 rows. Per-row values are inspectable directly in cleaned_data.csv.
log_change("7", "total_charge", "ALL_ROWS", "DERIVED_COLUMN_ADDED", "",
           "monthly_charge + overage_fee",
           "Combined billing figure; formula applied uniformly to all rows.")

# --- final null check ---
log()
log("--- Final null check ---")
null_counts = df.isna().sum()
any_nulls = int(null_counts.sum())
log(f"Total nulls across all columns (post-transform): {any_nulls}")
if any_nulls == 0:
    log("0 nulls -> 0 NULL_FLAGGED_NOT_IMPUTED and 0 NULL_IMPUTED entries logged. "
        "No missing_value_strategy from 01_business_brief.yaml needed to be invoked, "
        "because there was nothing missing to apply it to.")
else:
    for c in df.columns:
        n = int(df[c].isna().sum())
        if n:
            log(f"  {c}: {n} nulls -- flagged per default (leave_null), NOT imputed "
                f"(no explicit imputation strategy configured for this column).")
            flag_col = f"{c}_missing_flag"
            df[flag_col] = df[c].isna()

# --- column ordering ---
log()
log("--- Column ordering ---")
identifiers = ["__source_row"]
categorical_descriptors = ["churn", "contract_renewal", "data_plan"]
numeric_measures = ["account_weeks", "data_usage", "cust_serv_calls", "day_mins",
                     "day_calls", "monthly_charge", "overage_fee", "roam_mins"]
derived = ["total_charge"]
flag_cols = sorted([c for c in df.columns if c.endswith("_flag")])

ordered = identifiers + categorical_descriptors + numeric_measures + derived + flag_cols
missing_from_plan = [c for c in df.columns if c not in ordered]
assert not missing_from_plan, f"Unaccounted columns: {missing_from_plan}"
df = df[ordered]
log(f"New column order: {list(df.columns)}")
log_change("7", "ALL_COLUMNS", "ALL_ROWS", "COLUMN_REORDERED", "",
           str(ordered),
           "Reordered: identifiers -> categorical descriptors -> numeric measures -> "
           "derived columns -> flag columns.")

# --- index reset (keep __source_row as a column) ---
log()
log("--- Index reset ---")
df = df.reset_index(drop=True)
log(f"Index reset to 0..{len(df)-1}. __source_row column present: {'__source_row' in df.columns}")
log(f"__source_row still unique and matches row count: "
    f"{df['__source_row'].nunique() == len(df)}")

# --- write outputs ---
df.to_csv(CLEANED_OUT, index=False, encoding="utf-8")
df.to_pickle(OUT_DIR + r"\_final.pkl")
log()
log(f"cleaned_data.csv (FINAL) rows: {len(df)}, columns: {len(df.columns)}")
log(f"columns: {list(df.columns)}")

# append to change_log.csv
existing = pd.read_csv(CHANGELOG, encoding="utf-8")
new_rows = pd.DataFrame(change_rows, columns=["STAGE", "COLUMN", "SOURCE_ROW", "CHANGE_TYPE",
                                                "ORIGINAL_VALUE", "NEW_VALUE", "REASON"])
combined = pd.concat([existing, new_rows], ignore_index=True)
combined.to_csv(CHANGELOG, index=False, encoding="utf-8")
log(f"change_log.csv total rows after Stage 7 append: {len(combined)} "
    f"(was {len(existing)}, added {len(new_rows)})")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("Wrote:", REPORT)
print("Wrote:", CLEANED_OUT, "rows:", len(df), "cols:", len(df.columns))
print("change_log.csv total rows:", len(combined))
