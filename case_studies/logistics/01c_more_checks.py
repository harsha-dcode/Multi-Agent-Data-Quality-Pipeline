
from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

import pandas as pd
import numpy as np
import os
from thefuzz import fuzz, utils
from functools import partial

IN_PATH = str(_HERE / "input" / "logistics_supply_chain_dataset_v3.csv")
OUT_DIR = str(_HERE)
OUT_PATH = os.path.join(OUT_DIR, "01c_more_checks_report.txt")

df = pd.read_csv(IN_PATH, encoding="utf-8", dtype=str, keep_default_na=False)
lines = []

# Delay_Days negative vs Delivery_Status
delay_num = pd.to_numeric(df['Delay_Days'].replace('', np.nan), errors='coerce')
neg_delay_mask = delay_num < 0
lines.append("=== Delay_Days negative vs Delivery_Status ===")
lines.append(str(df.loc[neg_delay_mask, 'Delivery_Status'].str.strip().str.upper().value_counts()))
lines.append("")

# Shipping_Cost negative abs median vs overall median
cost_num = pd.to_numeric(df['Shipping_Cost_INR'].replace('', np.nan), errors='coerce')
neg_cost = cost_num[cost_num < 0]
pos_cost = cost_num[cost_num > 0]
lines.append("=== Shipping_Cost_INR sign-flip evidence check ===")
lines.append(f"median(abs(negatives))={neg_cost.abs().median():.2f}, median(all positives)={pos_cost.median():.2f}")
lines.append(f"mean(abs(negatives))={neg_cost.abs().mean():.2f}, mean(all positives)={pos_cost.mean():.2f}")
lines.append("-> large magnitude mismatch means NOT simple sign-flip, treat as flagged anomaly not corrected")
lines.append("")

# Collision guard test for each categorical column - canonical lists
canon_sets = {
    'Delivery_Status': ['On Time', 'Delayed', 'Early', 'In Transit'],
    'Customer_Type': ['Enterprise', 'Retail', 'Wholesale'],
    'Transport_Mode': ['Road', 'Air', 'Rail', 'Sea'],
    'Product_Category': ['FMCG', 'Clothing & Apparel', 'Electronics', 'Food & Beverages',
                          'Auto Parts', 'Chemicals', 'Industrial Equipment', 'Books & Stationery',
                          'Pharmaceuticals', 'Furniture'],
    'Vehicle_Type': ['Heavy Truck', 'Container Truck', 'Medium Truck', 'Cargo Plane',
                      'Mini Truck', 'Commercial Cargo Flight', 'Freight Train',
                      'Express Freight Train', 'Pickup Van', 'Container Ship', 'Bulk Carrier'],
    'Industry': ['Distribution', 'Import-Export', 'Manufacturing', 'E-Commerce', 'Automotive',
                 'Electronics Retail', 'Banking & Finance', 'Pharmacy', 'Supermarket',
                 'Fashion Retail', 'Agriculture Supply', 'Technology', 'Telecom',
                 'FMCG', 'Pharmaceuticals'],
    'Return_Status': ['Not Returned', 'Returned'],
    'Warehouse_Region': ['East', 'North', 'South', 'West'],
    'Destination_Region': ['Central', 'East', 'North', 'South', 'West'],
}

lines.append("=== COLLISION GUARD: canonicals_collide check per categorical column ===")
def canonicals_collide(canonical_list):
    keys = [utils.full_process(str(c)) for c in canonical_list]
    return len(set(keys)) < len(keys), keys

for col, canons in canon_sets.items():
    collide, keys = canonicals_collide(canons)
    lines.append(f"{col}: collide={collide}  processed_keys={keys}")
    if collide:
        # find which ones collided
        from collections import Counter
        cnt = Counter(keys)
        collided_keys = [k for k, v in cnt.items() if v > 1]
        lines.append(f"  !!! COLLISION on processed key(s): {collided_keys}")
lines.append("")

# Pairwise similarity matrix for near-miss checks (token_sort_ratio, full_process=False, punctuation preserved)
lines.append("=== Pairwise token_sort_ratio (punctuation-preserving) within each canonical set - look for high cross-canonical similarity (risk of miscorrection) ===")
for col, canons in canon_sets.items():
    lines.append(f"-- {col} --")
    for i in range(len(canons)):
        for j in range(i+1, len(canons)):
            score = fuzz.token_sort_ratio(canons[i], canons[j], full_process=False)
            if score >= 60:
                lines.append(f"  {canons[i]!r} vs {canons[j]!r}: {score}")
lines.append("")

# Test specific messy values against canonical Product_Category set with punctuation-preserving scorer
lines.append("=== Product_Category messy value -> best canonical match (punctuation-preserving scorer) ===")
messy_pc = ['ELECTRONICS', 'Clothing', 'clothing & apparel', 'Apparel & Clothing', 'electronics', 'Electronic']
from thefuzz import process as fuzz_process

for v in messy_pc:
    match = fuzz_process.extractOne(
        v, canon_sets['Product_Category'],
        processor=lambda x: str(x).strip().lower(),
        scorer=partial(fuzz.token_sort_ratio, full_process=False),
    )
    lines.append(f"  {v!r} -> {match}")
lines.append("")

# Test Delivery_Status messy values
lines.append("=== Delivery_Status messy value -> best canonical match ===")
messy_ds = ['On time', 'on time', 'ON TIME', 'On-Time', 'delay', 'delayed', 'early', 'DELAYED', 'EARLY']
for v in messy_ds:
    match = fuzz_process.extractOne(
        v, canon_sets['Delivery_Status'],
        processor=lambda x: str(x).strip().lower(),
        scorer=partial(fuzz.token_sort_ratio, full_process=False),
    )
    lines.append(f"  {v!r} -> {match}")
lines.append("")

# Test Customer_Type messy values
lines.append("=== Customer_Type messy value -> best canonical match ===")
messy_ct = ['RETAIL', 'WHOLESALE', 'whole sale', 'retail', 'wholesale']
for v in messy_ct:
    match = fuzz_process.extractOne(
        v, canon_sets['Customer_Type'],
        processor=lambda x: str(x).strip().lower(),
        scorer=partial(fuzz.token_sort_ratio, full_process=False),
    )
    lines.append(f"  {v!r} -> {match}")
lines.append("")

# Test Transport_Mode messy values
lines.append("=== Transport_Mode messy value -> best canonical match ===")
messy_tm = ['road', 'ROAD', 'Road Transport', 'air', 'Airways', 'AIR']
for v in messy_tm:
    match = fuzz_process.extractOne(
        v, canon_sets['Transport_Mode'],
        processor=lambda x: str(x).strip().lower(),
        scorer=partial(fuzz.token_sort_ratio, full_process=False),
    )
    lines.append(f"  {v!r} -> {match}")
lines.append("")

# Destination_City historical-name / case variants (need explicit synonym map, not fuzzy - test fuzzy would fail on Bombay->Mumbai etc)
lines.append("=== Destination_City known variants (case + historical names) ===")
city_variants = ['BANGALORE', 'Bangalore', 'Bengaluru', 'bangalore', 'CHENNAI', 'Chennai', 'chennai',
                  'Calcutta', 'Kolkata', 'kolkata', 'MUMBAI', 'Mumbai', 'mumbai', 'Bombay', 'Madras']
canon_cities = ['Agra','Ahmedabad','Amritsar','Bangalore','Bhopal','Bhubaneswar','Chandigarh','Chennai',
                'Coimbatore','Delhi','Guwahati','Hyderabad','Indore','Jaipur','Kochi','Kolkata','Lucknow',
                'Mumbai','Nagpur','Nashik','Patna','Pune','Raipur','Ranchi','Surat','Thiruvananthapuram',
                'Vadodara','Varanasi','Visakhapatnam']
for v in city_variants:
    match = fuzz_process.extractOne(
        v, canon_cities,
        processor=lambda x: str(x).strip().lower(),
        scorer=partial(fuzz.token_sort_ratio, full_process=False),
    )
    lines.append(f"  {v!r} -> {match}")

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("done")
