#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
02_extract_and_profile.py -- Stage 2 (full extraction) + Stage 3 (data profiling).

Loads the raw CSV the "safe" way established in 00_peek.py (encoding='utf-8-sig',
dtype=str, keep_default_na=False), adds the __source_row identity column (spec 4.0),
and produces a full column-by-column profile: null-disguise survey, cardinality,
numeric/date/string stats, and the fuzzy-matching collision guard for every
categorical column named in the business brief.
"""
import os
import re
import pandas as pd
from thefuzz import utils as fuzz_utils

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

IN_PATH = str(_HERE / "input" / "messy_sales.csv")
OUT_DIR = str(_HERE)
REPORT = os.path.join(OUT_DIR, "02_profile_report.txt")
PICKLE_RAW = os.path.join(OUT_DIR, "_raw_with_source_row.pkl")

lines = []
def log(s=""):
    lines.append(str(s))

# ---- Stage 2: extraction ----
df = pd.read_csv(IN_PATH, encoding="utf-8-sig", dtype=str, keep_default_na=False)
df.insert(0, "__source_row", range(len(df)))  # 0-based row number in the raw file (spec 4.0)

log("=" * 78)
log("STAGE 2 -- FULL EXTRACTION")
log("=" * 78)
log(f"Loaded with encoding='utf-8-sig', dtype=str, keep_default_na=False")
log(f"Shape (rows, cols, excl. __source_row): ({df.shape[0]}, {df.shape[1]-1})")
log(f"Columns (raw, as-is): {[c for c in df.columns if c != '__source_row']}")

df.to_pickle(PICKLE_RAW)  # hand off to 03_clean.py so it doesn't re-parse and can trust __source_row

# ---- Null disguise superset from spec 4.2/Stage 3 ----
UNAMBIGUOUS_NULLS = {"", " ", "?", "null", "none", "tbd", "undefined", "#n/a", "#value!", "#ref!", "n/a"}
AMBIGUOUS_NULLS = {"na", "-", "unknown"}
FULL_DISGUISE_SET = {
    "", " ", "-", "?", "n/a", "na", "null", "none", "tbd", "unknown", "undefined",
    "#n/a", "#value!", "#ref!",
}

log("\n" + "=" * 78)
log("STAGE 3 -- DATA PROFILING")
log("=" * 78)

data_cols = [c for c in df.columns if c != "__source_row"]

def is_disguise(v):
    return str(v).strip().casefold() in FULL_DISGUISE_SET

log("\n--- Per-column null-disguise survey (case-insensitive, stripped match) ---")
disguise_counts = {}
for col in data_cols:
    vc = df[col].map(lambda v: str(v).strip().casefold())
    counts = {}
    for tok in FULL_DISGUISE_SET:
        n = (vc == tok).sum()
        if n > 0:
            counts[tok] = int(n)
    disguise_counts[col] = counts
    total = sum(counts.values())
    log(f"  {col:16s} total disguise-token cells: {total:4d}   breakdown: {counts}")

log("\n--- Ambiguity-guard evaluation (na/-/unknown) ---")
log("  product column 'Unknown': gate = closed 4-value Greek-letter set (Alpha/Beta/Gamma/Delta);")
log("  'Unknown' cannot be a 5th member of that set -> GATE SAYS NO -> treat as null disguise.")
prod_unknown_ct = int((df["Product"].str.strip().str.casefold() == "unknown").sum())
log(f"  Product=='Unknown' (case-insensitive) count: {prod_unknown_ct}")
cust_unknown_ct = int((df["customer name"].str.strip().str.casefold() == "unknown").sum())
log(f"  customer name=='Unknown' count: {cust_unknown_ct}  (free-text name column -> 'Unknown' cannot be a real name -> GATE NO)")
log("  channel column: no 'na'/'-'/'unknown' tokens expected as a real category value; verifying below.")
for col in ["region ", "channel"]:
    vals_na = int((df[col].str.strip().str.casefold() == "na").sum())
    vals_dash = int((df[col].str.strip() == "-").sum())
    log(f"  {col!r}: 'na'-token cells={vals_na}, '-'-token cells={vals_dash}")

# ---- Cardinality / top values per column ----
log("\n--- Cardinality and top-10 values (raw, unnormalized) ---")
for col in data_cols:
    nunique = df[col].nunique(dropna=False)
    top10 = df[col].value_counts(dropna=False).head(10)
    log(f"\n  {col!r}: {nunique} unique raw values")
    for val, cnt in top10.items():
        log(f"      {val!r}: {cnt}")

# ---- Categorical canonical survey + collision guard ----
log("\n" + "=" * 78)
log("COLLISION GUARD -- run BEFORE any fuzzy matching (spec 4.4 mandatory guard)")
log("=" * 78)

CANON = {
    "region": ["North", "South", "East", "West", "Northeast"],
    "product": ["Alpha", "Beta", "Gamma", "Delta"],
    "channel": ["Retail", "Wholesale", "Online", "Brick & Mortar", "B2B", "B2C"],
}

def canonicals_collide(canonical_list):
    keys = [fuzz_utils.full_process(str(c)) for c in canonical_list]
    collided = len(set(keys)) < len(keys)
    return collided, keys

for col_label, canon_list in CANON.items():
    collided, keys = canonicals_collide(canon_list)
    log(f"\n  Column: {col_label}")
    log(f"    Canonical values: {canon_list}")
    log(f"    full_process() keys: {keys}")
    log(f"    COLLISION DETECTED: {collided}")
    if collided:
        log(f"    -> DO NOT FUZZY MATCH THIS COLUMN. Exact/case-insensitive matching only.")
    else:
        log(f"    -> Safe to fuzzy match at threshold 85 (token_sort_ratio, full_process=False + "
            f"punctuation-preserving processor).")

# ---- Numeric column raw survey (units_sold, unit_price, total_revenue) ----
log("\n" + "=" * 78)
log("NUMERIC COLUMNS -- raw-string survey (parsing happens in Stage 4)")
log("=" * 78)
for col in ["Units Sold", "unit_price", "Total Revenue"]:
    sample_nonblank = [v for v in df[col].tolist() if str(v).strip() != ""][:15]
    log(f"\n  {col!r} sample raw values (first 15 non-blank): {sample_nonblank}")
    currency_chars = "$\u20b9\u20ac\u00a3"
    has_currency = df[col].map(lambda v: any(ch in str(v) for ch in currency_chars)).sum()
    has_unit_suffix = df[col].str.contains(r"[a-zA-Z]", regex=True, na=False).sum()
    has_comma_decimal = df[col].str.contains(r"\d,\d{2}\b", regex=True, na=False).sum()
    log(f"    cells containing a currency symbol ($/Rupee/EUR/GBP): {int(has_currency)}")
    log(f"    cells containing any letters (unit suffix / non-numeric noise): {int(has_unit_suffix)}")
    log(f"    cells matching comma-as-decimal pattern (\\d,\\d\\d boundary): {int(has_comma_decimal)}")

# ---- Date column raw survey ----
log("\n" + "=" * 78)
log("DATE COLUMN -- raw-string survey (Order_Date)")
log("=" * 78)
sample_dates = [v for v in df["Order_Date"].tolist() if str(v).strip() != ""][:20]
log(f"  Sample raw values (first 20 non-blank): {sample_dates}")
n_blank_dates = int((df["Order_Date"].str.strip() == "").sum())
n_digit_only = int(df["Order_Date"].str.match(r"^\d{5}$").sum())
log(f"  Blank date cells: {n_blank_dates}")
log(f"  5-digit-numeric cells (likely Excel serials): {n_digit_only}")

# ---- Email / phone raw survey ----
log("\n" + "=" * 78)
log("EMAIL / PHONE -- raw-string survey")
log("=" * 78)
email_col = "Customer Email"
no_at = int((~df[email_col].str.contains("@", na=False)) & (df[email_col].str.strip() != "")).__int__() if False else int(((~df[email_col].str.contains("@", regex=False)) & (df[email_col].str.strip() != "")).sum())
log(f"  customer email cells with NO '@' (and non-blank): {no_at}")
uniform_domain = int(df[email_col].str.contains("example.com", regex=False, na=False).sum())
log(f"  cells containing 'example.com': {uniform_domain} / {len(df)}")

phone_col = "Phone Number"
plus91 = int(df[phone_col].str.contains(r"\+?91", regex=True, na=False).sum())
ten_digit_69 = int(df[phone_col].str.replace(r"\D", "", regex=True).str.match(r"^[6-9]\d{9}$").sum())
log(f"  phone cells containing '91' country-code fragment: {plus91}")
log(f"  phone cells whose digits-only form is a 10-digit number starting 6-9 (valid Indian mobile pattern): {ten_digit_69}")

# ---- Row-level duplication preview ----
log("\n" + "=" * 78)
log("DUPLICATE PREVIEW (raw, before any normalization)")
log("=" * 78)
dup_full_row = int(df[data_cols].duplicated(keep=False).sum())
dup_order_id = int(df["order_id"].duplicated(keep=False).sum())
log(f"  Rows that are exact full-row duplicates of another row (raw strings): {dup_full_row}")
log(f"  Rows whose order_id value repeats elsewhere in the file: {dup_order_id}")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("\n".join(lines).encode("ascii", errors="replace").decode("ascii")[:3000])
print(f"\n[WROTE] {REPORT}")
print(f"[WROTE] {PICKLE_RAW}")
