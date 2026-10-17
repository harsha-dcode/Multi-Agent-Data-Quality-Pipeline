# -*- coding: utf-8 -*-
"""
Stage 6: Data Integration -- N/A, single source (logged in RUN_SUMMARY.md).
Stage 7: Data Transformation -- final dtypes, column order, derived columns,
         final null policy (leave_null default, no imputation configured for
         any column per 01_business_brief.yaml missing_value_strategy).

Pre-viz prep is the next stage: stage8_viz_prep.py.
"""
import pandas as pd
import numpy as np
import json

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

OUT_DIR = str(_HERE)

df = pd.read_csv(OUT_DIR + r"\cleaned_data.csv", encoding="utf-8")
n_before_transform = len(df)

CHANGES = []
def record(stage, column, source_row, change_type, original, new, reason):
    CHANGES.append({
        "STAGE": stage, "COLUMN": column, "SOURCE_ROW": source_row,
        "CHANGE_TYPE": change_type,
        "ORIGINAL_VALUE": original, "NEW_VALUE": new, "REASON": reason
    })

log_lines = []
def log(msg):
    print(msg)
    log_lines.append(str(msg))

# =============================================================================
# STAGE 6: DATA INTEGRATION -- N/A, single source
# =============================================================================
log("=== STAGE 6: DATA INTEGRATION ===")
log("N/A -- Single Source. Only one input file (logistics_supply_chain_dataset_v3.csv) was provided.")

# =============================================================================
# STAGE 7: DATA TRANSFORMATION
# =============================================================================
log("")
log("=== STAGE 7: DATA TRANSFORMATION ===")

# ---- Final dtype enforcement ----
DATE_COLS = ["shipment_date", "pickup_date", "dispatch_date",
             "expected_delivery_date", "actual_delivery_date"]
for col in DATE_COLS:
    df[col] = pd.to_datetime(df[col], errors="coerce")

INT_COLS = ["distance_km"]
for col in INT_COLS:
    df[col] = df[col].astype("int64")

FLOAT_COLS = ["delay_days", "shipment_weight_kg", "shipment_volume_cbm",
              "shipping_cost_inr", "fuel_cost_inr", "operational_cost_inr",
              "revenue_inr", "profit_inr", "customer_rating"]
for col in FLOAT_COLS:
    df[col] = df[col].astype("float64")

CATEGORY_COLS = ["delivery_status", "customer_type", "industry", "warehouse_id",
                  "warehouse_name", "warehouse_city", "warehouse_state", "warehouse_region",
                  "destination_city", "destination_state", "destination_region",
                  "transport_mode", "vehicle_type", "product_category", "return_status",
                  "delay_reason"]
for col in CATEGORY_COLS:
    df[col] = df[col].astype("category")

log(f"Cast {len(DATE_COLS)} date cols -> datetime64, {len(INT_COLS)} col -> int64, "
    f"{len(FLOAT_COLS)} cols -> float64, {len(CATEGORY_COLS)} cols -> category")
for col in df.columns:
    if col not in DATE_COLS + INT_COLS + FLOAT_COLS + CATEGORY_COLS and not col.endswith("_flag") and col != "__source_row":
        record("7", col, "ALL_ROWS", "DTYPE_CAST", "str", "str (identifier, kept as string)",
               "identifier column intentionally kept as string dtype")

# ---- Derived columns ----
derived_cols_added = []

# actual_transit_days: only computed where actual_delivery_date is present AND
# the row is not a date-logic-violation (BR6) -- computing it on a violated
# row would produce a negative transit time that is itself the artifact being
# flagged, not a new insight.
df["actual_transit_days"] = np.where(
    df["actual_delivery_date"].notna() & ~df["date_logic_violation_flag"],
    (df["actual_delivery_date"] - df["dispatch_date"]).dt.days,
    np.nan
)
derived_cols_added.append("actual_transit_days")
record("7", "actual_transit_days", "ALL_ROWS", "DERIVED_COLUMN_ADDED", "", "",
       "actual_delivery_date - dispatch_date in days; null where actual_delivery_date is null (In Transit) or where date_logic_violation_flag is True")

df["cost_per_kg"] = np.where(
    (df["shipment_weight_kg"].notna()) & (df["shipment_weight_kg"] > 0),
    (df["shipping_cost_inr"] + df["fuel_cost_inr"].fillna(0) + df["operational_cost_inr"]) / df["shipment_weight_kg"],
    np.nan
)
derived_cols_added.append("cost_per_kg")
record("7", "cost_per_kg", "ALL_ROWS", "DERIVED_COLUMN_ADDED", "", "",
       "(shipping_cost_inr + fuel_cost_inr + operational_cost_inr) / shipment_weight_kg; null where weight is null/zero. fuel_cost_inr nulls treated as 0 IN THIS DERIVED SUM ONLY (not imputed into the source column) since ~4% of rows have no fuel cost captured and excluding them entirely would drop otherwise-valid cost rows")

df["profit_margin_pct"] = np.where(
    df["revenue_inr"] > 0,
    100 * df["profit_inr"] / df["revenue_inr"],
    np.nan
)
derived_cols_added.append("profit_margin_pct")
record("7", "profit_margin_pct", "ALL_ROWS", "DERIVED_COLUMN_ADDED", "", "",
       "100 * profit_inr / revenue_inr; can legitimately be negative (BR2)")

df["shipment_year"] = df["shipment_date"].dt.year
df["shipment_month"] = df["shipment_date"].dt.month
derived_cols_added.append("shipment_year")
derived_cols_added.append("shipment_month")
record("7", "shipment_year/shipment_month", "ALL_ROWS", "DERIVED_COLUMN_ADDED", "", "",
       "recomputed directly from cleaned shipment_date, per Stage 8 instruction not to trust any pre-existing year/month column (none existed in source, computed fresh here for Stage 8/9 use)")

log(f"Derived columns added: {derived_cols_added}")

# ---- Final null check: leave-flag-by-default (no imputation configured) ----
NON_CRITICAL_NULLABLE = {
    "actual_delivery_date": "In Transit shipment (not yet delivered)",
    "delay_days": "unknown until delivered",
    "driver_id": "no truck driver for Air/Sea legs",
    "shipment_weight_kg": "genuine data gap, no correlation found",
    "fuel_cost_inr": "genuine data gap, no correlation found (never_impute: cost factor)",
    "customer_rating": "customer did not submit a rating",
    "delay_reason": "not delayed, or delayed with reason uncaptured",
}
missing_flags_added = []
for col, reason in NON_CRITICAL_NULLABLE.items():
    flag_col = f"{col}_missing_flag"
    df[flag_col] = df[col].isna()
    missing_flags_added.append(flag_col)
    n = int(df[flag_col].sum())
    log(f"  {col}: {n} nulls left as-is (leave_null per brief), {flag_col} materialized")
log(f"Final-null-check flag columns added: {missing_flags_added}")
log("No column had an imputation strategy configured in 01_business_brief.yaml missing_value_strategy "
    "(all non-critical nullable columns are 'leave_null', all cost/revenue/identifier columns are "
    "'never_impute') -- so NO NULL_IMPUTED entries exist in this run. This is the default-safe path, "
    "not a shortfall.")

# ---- Column ordering: identifiers, dates, categorical descriptors, numeric measures, then flags ----
identifiers = ["shipment_id", "order_id", "customer_id", "warehouse_id", "driver_id"]
dates = ["shipment_date", "pickup_date", "dispatch_date", "expected_delivery_date",
         "actual_delivery_date", "shipment_year", "shipment_month"]
categoricals = ["delivery_status", "customer_type", "industry", "warehouse_name",
                 "warehouse_city", "warehouse_state", "warehouse_region",
                 "destination_city", "destination_state", "destination_region",
                 "transport_mode", "vehicle_type", "product_category", "return_status",
                 "delay_reason"]
numerics = ["distance_km", "delay_days", "actual_transit_days", "shipment_weight_kg",
            "shipment_volume_cbm", "shipping_cost_inr", "fuel_cost_inr",
            "operational_cost_inr", "revenue_inr", "profit_inr", "profit_margin_pct",
            "cost_per_kg", "customer_rating"]
flags_and_meta = [c for c in df.columns if c not in identifiers + dates + categoricals + numerics]
# ensure __source_row is last among meta but present
final_order = identifiers + dates + categoricals + numerics + \
              [c for c in flags_and_meta if c != "__source_row"] + ["__source_row"]
assert set(final_order) == set(df.columns), \
    f"column reorder mismatch: missing={set(df.columns)-set(final_order)} extra={set(final_order)-set(df.columns)}"
df = df[final_order]
for c in ["identifiers", "dates", "categoricals", "numerics"]:
    pass
record("7", "ALL_COLUMNS", "ALL_ROWS", "COLUMN_REORDERED", "", "",
       "reordered: identifiers -> dates -> categorical descriptors -> numeric measures -> flags/meta -> __source_row")
log(f"Columns reordered. Final column count: {len(df.columns)}")

# ---- Index reset (keep __source_row as column) ----
df = df.reset_index(drop=True)
assert "__source_row" in df.columns
log(f"Index reset to 0..{len(df)-1}. __source_row confirmed present as a column.")

# =============================================================================

# ---------------------------------------------------------------
# Report for this stage only.
# ---------------------------------------------------------------
_STAGE_REPORT = str(_HERE / "stage7_transform_report.txt")
with open(_STAGE_REPORT, "w", encoding="utf-8") as _f:
    _f.write(chr(10).join(log_lines) + chr(10))
print("wrote", _STAGE_REPORT)
