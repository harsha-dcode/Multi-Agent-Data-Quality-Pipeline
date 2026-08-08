"""
Supplementary Stage 3 checks: correlations that inform Stage 1 business rules
and Stage 4 cleaning decisions (not_critical columns, negative-value legitimacy).
"""
import pandas as pd
import numpy as np
import os

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

IN_PATH = str(_HERE / "input" / "logistics_supply_chain_dataset_v3.csv")
OUT_DIR = str(_HERE)
OUT_PATH = os.path.join(OUT_DIR, "01b_correlation_report.txt")

df = pd.read_csv(IN_PATH, encoding="utf-8", dtype=str, keep_default_na=False)

lines = []

# 1. Actual_Delivery_Date null vs Delivery_Status
mask_null_actual = df['Actual_Delivery_Date'].str.strip() == ''
lines.append("=== Actual_Delivery_Date null vs Delivery_Status (normalized upper) ===")
lines.append(str(df.loc[mask_null_actual, 'Delivery_Status'].str.strip().str.upper().value_counts()))
lines.append("")

# 2. Delay_Days null vs Delivery_Status
mask_null_delay = df['Delay_Days'].str.strip() == ''
lines.append("=== Delay_Days null vs Delivery_Status ===")
lines.append(str(df.loc[mask_null_delay, 'Delivery_Status'].str.strip().str.upper().value_counts()))
lines.append(f"Overlap (both Actual_Delivery_Date and Delay_Days null, same rows?): {(mask_null_actual == mask_null_delay).all()}")
lines.append("")

# 3. Driver_ID null vs Transport_Mode
mask_null_driver = df['Driver_ID'].str.strip() == ''
lines.append("=== Driver_ID null vs Transport_Mode (normalized upper) ===")
lines.append(str(df.loc[mask_null_driver, 'Transport_Mode'].str.strip().str.upper().value_counts()))
lines.append(f"Total Driver_ID null: {mask_null_driver.sum()}")
lines.append(f"Total non-Road-ish transport modes (Air/Rail/Sea variants): checking overlap")
road_variants = {'ROAD', 'ROAD TRANSPORT'}
non_road_mask = ~df['Transport_Mode'].str.strip().str.upper().isin(road_variants)
lines.append(f"Rows with non-road transport mode: {non_road_mask.sum()}")
lines.append(f"Rows with null driver AND non-road transport: {(mask_null_driver & non_road_mask).sum()}")
lines.append(f"Rows with null driver AND road transport (unexpected): {(mask_null_driver & ~non_road_mask).sum()}")
lines.append(f"Rows with non-null driver AND non-road transport (unexpected): {(~mask_null_driver & non_road_mask).sum()}")
lines.append("")

# 4. Fuel_Cost_INR null vs Transport_Mode
mask_null_fuel = df['Fuel_Cost_INR'].str.strip() == ''
lines.append("=== Fuel_Cost_INR null vs Transport_Mode (normalized upper) ===")
lines.append(str(df.loc[mask_null_fuel, 'Transport_Mode'].str.strip().str.upper().value_counts()))
lines.append("")

# 5. Delay_Reason null vs Delivery_Status
mask_null_reason = df['Delay_Reason'].str.strip() == ''
lines.append("=== Delay_Reason null vs Delivery_Status (normalized upper) ===")
lines.append(str(df.loc[mask_null_reason, 'Delivery_Status'].str.strip().str.upper().value_counts()))
lines.append("=== Delay_Reason NON-null vs Delivery_Status (normalized upper) ===")
lines.append(str(df.loc[~mask_null_reason, 'Delivery_Status'].str.strip().str.upper().value_counts()))
lines.append("")

# 6. Exact duplicate rows
dup_mask = df.duplicated(keep=False)
lines.append(f"=== Exact duplicate rows (all 35 cols identical) ===")
lines.append(f"Total rows involved in exact duplication: {dup_mask.sum()}")
lines.append(f"Distinct duplicate groups: {df[dup_mask].drop_duplicates().shape[0]}")
lines.append("")

# 7. Shipment_ID duplicate check
dup_shp = df[df.duplicated(subset=['Shipment_ID'], keep=False)]
lines.append(f"=== Shipment_ID duplicate value rows ===")
lines.append(f"Rows sharing a Shipment_ID with another row: {len(dup_shp)}")
lines.append(f"Distinct Shipment_ID values involved: {dup_shp['Shipment_ID'].nunique()}")
# check if these are exact dupes or different data under same ID
sample_dup_id = dup_shp['Shipment_ID'].iloc[0] if len(dup_shp) else None
if sample_dup_id:
    sub = df[df['Shipment_ID'] == sample_dup_id]
    lines.append(f"Sample duplicated Shipment_ID {sample_dup_id}:")
    lines.append(sub.to_string())
    # are ALL duplicate-ID groups exact full-row duplicates, or different data?
    full_dupe_ids = 0
    partial_dupe_ids = 0
    for sid, grp in dup_shp.groupby('Shipment_ID'):
        if grp.drop(columns=['Shipment_ID']).duplicated(keep=False).all():
            full_dupe_ids += 1
        else:
            partial_dupe_ids += 1
    lines.append(f"Shipment_ID groups where all other columns are identical too (true exact dupes): {full_dupe_ids}")
    lines.append(f"Shipment_ID groups where other columns DIFFER (same ID, different shipment data - ID collision, not dupe): {partial_dupe_ids}")
lines.append("")

# 8. Product_Category value counts detail
lines.append("=== Product_Category exact value_counts (case-sensitive, stripped) ===")
lines.append(str(df['Product_Category'].str.strip().value_counts()))
lines.append("")

# 9. Delivery date sanity: Actual < Dispatch (impossible)
d_dispatch = pd.to_datetime(df['Dispatch_Date'], errors='coerce')
d_actual = pd.to_datetime(df['Actual_Delivery_Date'].replace('', np.nan), errors='coerce')
d_expected = pd.to_datetime(df['Expected_Delivery_Date'], errors='coerce')
d_pickup = pd.to_datetime(df['Pickup_Date'], errors='coerce')
d_shipment = pd.to_datetime(df['Shipment_Date'], errors='coerce')

impossible_actual_before_dispatch = (d_actual < d_dispatch).sum()
lines.append(f"Rows where Actual_Delivery_Date < Dispatch_Date (impossible): {impossible_actual_before_dispatch}")
impossible_dispatch_before_pickup = (d_dispatch < d_pickup).sum()
lines.append(f"Rows where Dispatch_Date < Pickup_Date (impossible): {impossible_dispatch_before_pickup}")
impossible_pickup_before_shipment = (d_pickup < d_shipment).sum()
lines.append(f"Rows where Pickup_Date < Shipment_Date (impossible): {impossible_pickup_before_shipment}")
lines.append("")

# 10. Customer_Rating out-of-range values detail
rating_num = pd.to_numeric(df['Customer_Rating'].replace('', np.nan), errors='coerce')
lines.append("=== Customer_Rating out-of-range (expect 1.0-5.0) ===")
lines.append(f"Below 1.0 (and not null): {(rating_num < 1.0).sum()}")
lines.append(f"Above 5.0: {(rating_num > 5.0).sum()}")
lines.append(f"Values > 5.0 detail: {sorted(rating_num[rating_num > 5.0].unique().tolist())}")
lines.append(f"Values < 1.0 (excl NaN) detail: {sorted(rating_num[(rating_num < 1.0)].dropna().unique().tolist())}")
lines.append("")

# 11. Negative Shipment_Weight_KG detail
weight_num = pd.to_numeric(df['Shipment_Weight_KG'].replace('', np.nan), errors='coerce')
lines.append("=== Shipment_Weight_KG negative detail ===")
neg_w = weight_num[weight_num < 0]
lines.append(f"Count negative: {len(neg_w)}")
lines.append(f"Negative values sample (first 20): {sorted(neg_w.unique().tolist())[:20]}")
lines.append(f"Abs of negatives vs overall median comparison: median(abs(neg))={neg_w.abs().median()}, overall median={weight_num.median()}")
lines.append("")

# 12. Negative Shipping_Cost_INR detail
cost_num = pd.to_numeric(df['Shipping_Cost_INR'].replace('', np.nan), errors='coerce')
neg_c = cost_num[cost_num < 0]
lines.append("=== Shipping_Cost_INR negative detail ===")
lines.append(f"Count negative: {len(neg_c)}")
lines.append(f"Sample: {sorted(neg_c.unique().tolist())[:20]}")
lines.append("")

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("done")
