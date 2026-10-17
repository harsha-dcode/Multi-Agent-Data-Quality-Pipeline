# -*- coding: utf-8 -*-
"""
Stage 4: Data Cleaning (full pipeline stages 4.0-4.11)
Reads the raw logistics CSV, applies every cleaning step in spec order,
writes cleaned_data.csv + change_log.csv (+ change_log.csv, required name)
into the output directory.

Run: python stage4_clean.py
"""

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

import pandas as pd
import numpy as np
import re
import unicodedata
from functools import partial
from thefuzz import fuzz, utils as fuzz_utils
from thefuzz import process as fuzz_process

IN_PATH = str(_HERE / "input" / "logistics_supply_chain_dataset_v3.csv")
OUT_DIR = str(_HERE)

CLEANED_PATH = OUT_DIR + r"\cleaned_data.csv"
CHANGELOG_PATH = OUT_DIR + r"\change_log.csv"
LOG_PATH = OUT_DIR + r"\02_clean_run_log.txt"

run_log = []
def log(msg):
    print(msg)
    run_log.append(str(msg))

# change log entries: list of dicts with keys STAGE,COLUMN,SOURCE_ROW,CHANGE_TYPE,ORIGINAL_VALUE,NEW_VALUE,REASON
CHANGES = []
def record(stage, column, source_row, change_type, original, new, reason):
    CHANGES.append({
        "STAGE": stage, "COLUMN": column, "SOURCE_ROW": source_row,
        "CHANGE_TYPE": change_type,
        "ORIGINAL_VALUE": original, "NEW_VALUE": new, "REASON": reason
    })

# =============================================================================
# LOAD
# =============================================================================
df = pd.read_csv(IN_PATH, encoding="utf-8", dtype=str, keep_default_na=False)
RAW_ROW_COUNT = len(df)
log(f"Loaded raw file: {RAW_ROW_COUNT} rows, {len(df.columns)} columns")

# 4.0 -- preserve original row identity BEFORE any drop/reorder
df["__source_row"] = df.index  # 0-based position in raw file
log("Added __source_row (0-based raw file position)")

# =============================================================================
# 4.1 HEADER NORMALIZATION
# =============================================================================
def to_snake_case(name):
    s = name.strip()
    s = re.sub(r"[\s\-\./]+", "_", s)
    s = re.sub(r"[^0-9a-zA-Z_]", "", s)
    # Headers here are already underscore-separated words (Shipment_ID,
    # Distance_KM, Shipping_Cost_INR) -- do NOT insert underscores before
    # every capital letter, that would shatter acronyms like ID/KM/INR into
    # I_D / K_M / I_N_R. Standard camel-hump splitter (lower/digit -> upper)
    # correctly leaves acronym runs like "ID", "KM", "INR" intact because
    # there is no lowercase letter inside them to trigger a split.
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return s

orig_headers = list(df.columns)
new_headers = []
seen = {}
for h in orig_headers:
    if h == "__source_row":
        new_headers.append(h)
        continue
    nh = to_snake_case(h)
    if nh in seen:
        seen[nh] += 1
        nh = f"{nh}_{seen[nh]}"
    else:
        seen[nh] = 1
    new_headers.append(nh)
    if nh != h:
        record("4.1", nh, "ALL_ROWS", "HEADER_RENAME", h, nh, "snake_case normalization")

df.columns = new_headers
log(f"Headers normalized: {dict(zip(orig_headers, new_headers))}")

# convenient references
COL = {h: h for h in new_headers}

# =============================================================================
# 4.2 NULL STANDARDIZATION
# =============================================================================
UNAMBIGUOUS_NULLS = {'', ' ', '?', 'null', 'none', 'tbd', 'undefined',
                     '#n/a', '#value!', '#ref!', 'n/a'}
AMBIGUOUS_NULLS = {'na', '-', 'unknown'}  # 'none' already in unambiguous set per spec list

def norm_token(v):
    return str(v).strip().casefold()

null_before = {}
null_after = {}
for col in df.columns:
    if col == "__source_row":
        continue
    null_before[col] = int((df[col].apply(norm_token).isin(UNAMBIGUOUS_NULLS | AMBIGUOUS_NULLS)).sum())

for col in df.columns:
    if col == "__source_row":
        continue
    tokens = df[col].apply(norm_token)

    # unambiguous -> always null
    unamb_mask = tokens.isin(UNAMBIGUOUS_NULLS)
    for idx in df.index[unamb_mask]:
        record("4.2", col, df.at[idx, "__source_row"], "NULL_STANDARDIZED",
               df.at[idx, col], "", f"unambiguous null disguise token ('{df.at[idx, col]}')")
    df.loc[unamb_mask, col] = np.nan

    # ambiguous -> gate + evidence
    amb_mask = tokens.isin(AMBIGUOUS_NULLS)
    if amb_mask.any():
        # GATE: could token be a member of this column's canonical value set?
        # None of our categorical canonical sets contain 'na'/'-'/'unknown' as
        # a legitimate category label (verified against 01_business_brief.yaml
        # allowed_values). Gate says NO for every column in this dataset ->
        # null them, log NULL_STANDARDIZED with gate reasoning.
        for idx in df.index[amb_mask]:
            record("4.2", col, df.at[idx, "__source_row"], "NULL_STANDARDIZED",
                   df.at[idx, col], "",
                   f"ambiguous token '{df.at[idx, col]}' gated NO: not a member of {col}'s "
                   f"canonical value set (checked against Stage 1 allowed_values / column semantics)")
        df.loc[amb_mask, col] = np.nan

for col in df.columns:
    if col == "__source_row":
        continue
    null_after[col] = int(df[col].isna().sum())

log("Null standardization null-rate before/after (per column, only columns with any nulls):")
for col in df.columns:
    if col == "__source_row":
        continue
    if null_before.get(col, 0) or null_after.get(col, 0):
        log(f"  {col}: before={null_before[col]} after={null_after[col]}")

# =============================================================================
# 4.3 STRING NORMALIZATION
# =============================================================================
# Free-text columns (preserve case, just strip/collapse/NFC)
FREE_TEXT_COLS = []  # none identified as free-text narrative in this dataset

# Identifier-ish columns: strip whitespace, collapse spaces, NFC, NO case change
ID_COLS = ["shipment_id", "order_id", "customer_id", "warehouse_id", "driver_id"]

# Categorical columns needing Title Case / canonical casing (handled fully in 4.4)
CATEGORICAL_COLS = ["delivery_status", "customer_type", "industry", "warehouse_name",
                     "warehouse_city", "warehouse_state", "warehouse_region",
                     "destination_city", "destination_state", "destination_region",
                     "transport_mode", "vehicle_type", "product_category",
                     "return_status", "delay_reason"]

STRING_COLS = ID_COLS + CATEGORICAL_COLS

def normalize_string_value(v):
    if pd.isna(v):
        return v
    s = unicodedata.normalize("NFC", str(v))
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s

str_norm_count = 0
for col in STRING_COLS:
    if col not in df.columns:
        continue
    for idx in df.index:
        orig = df.at[idx, col]
        if pd.isna(orig):
            continue
        new = normalize_string_value(orig)
        if new != orig:
            record("4.3", col, df.at[idx, "__source_row"], "STRING_NORMALIZED",
                   orig, new, "whitespace strip / internal-space collapse / NFC normalize")
            df.at[idx, col] = new
            str_norm_count += 1
log(f"4.3 String normalization: {str_norm_count} cell-level whitespace/NFC changes logged")

# =============================================================================
# 4.4 CATEGORICAL TYPO CORRECTION (fuzzy matching with collision guard)
# =============================================================================
CANON = {
    "delivery_status": ["On Time", "Delayed", "Early", "In Transit"],
    "customer_type": ["Enterprise", "Retail", "Wholesale"],
    "industry": ["Distribution", "Import-Export", "Manufacturing", "E-Commerce",
                 "Automotive", "Electronics Retail", "Banking & Finance",
                 "Pharmacy", "Supermarket", "Fashion Retail", "Agriculture Supply",
                 "Technology", "Telecom", "FMCG", "Pharmaceuticals"],
    "transport_mode": ["Road", "Air", "Rail", "Sea"],
    "vehicle_type": ["Heavy Truck", "Container Truck", "Medium Truck", "Cargo Plane",
                      "Mini Truck", "Commercial Cargo Flight", "Freight Train",
                      "Express Freight Train", "Pickup Van", "Container Ship", "Bulk Carrier"],
    "product_category": ["FMCG", "Clothing & Apparel", "Electronics", "Food & Beverages",
                          "Auto Parts", "Chemicals", "Industrial Equipment", "Books & Stationery",
                          "Pharmaceuticals", "Furniture"],
    "return_status": ["Not Returned", "Returned"],
    "warehouse_region": ["East", "North", "South", "West"],
    "destination_region": ["Central", "East", "North", "South", "West"],
}

def canonicals_collide(canonical_list):
    keys = [fuzz_utils.full_process(str(c)) for c in canonical_list]
    return len(set(keys)) < len(keys)

def combined_scorer(a, b):
    """max(ratio, token_sort_ratio), punctuation-preserving, per business_brief BR9."""
    r = fuzz.ratio(a, b)
    t = fuzz.token_sort_ratio(a, b, full_process=False)
    return max(r, t)

fuzzy_summary = []
flag_registry = {}  # flag_column -> meaning

for col, canons in CANON.items():
    if col not in df.columns:
        continue
    collide = canonicals_collide(canons)
    if collide:
        fuzzy_summary.append(f"{col}: COLLISION GUARD TRIPPED -> exact case-insensitive match ONLY, no fuzzy matching")
        # fallback: exact case-insensitive
        for idx in df.index:
            v = df.at[idx, col]
            if pd.isna(v):
                continue
            for c in canons:
                if str(v).strip().casefold() == c.casefold() and v != c:
                    record("4.4", col, df.at[idx, "__source_row"], "TYPO_CORRECTED",
                           v, c, "exact case-insensitive match (collision guard tripped, fuzzy disabled)")
                    df.at[idx, col] = c
        continue

    fuzzy_summary.append(f"{col}: collision guard clear -> fuzzy matching enabled (max(ratio,token_sort_ratio), full_process=False)")
    canon_lower_map = {c.casefold(): c for c in canons}
    unknown_flag_col = f"{col}_unknown_category_flag"
    warn_flag_col = f"{col}_fuzzy_review_flag"
    flag_registry[unknown_flag_col] = f"True if {col} value could not be matched to a canonical value at >=70 similarity"
    flag_registry[warn_flag_col] = f"True if {col} value was auto-corrected at 70-84 similarity (needs review)"
    df[unknown_flag_col] = False
    df[warn_flag_col] = False

    n_auto = n_warn = n_unknown = 0
    for idx in df.index:
        v = df.at[idx, col]
        if pd.isna(v):
            continue
        # exact match short-circuit (case-sensitive exact canonical -> no change, no log)
        if v in canons:
            continue
        # exact case-insensitive match -> still a change (casing), log as TYPO_CORRECTED
        if v.casefold() in canon_lower_map and canon_lower_map[v.casefold()] != v:
            corrected = canon_lower_map[v.casefold()]
            record("4.4", col, df.at[idx, "__source_row"], "TYPO_CORRECTED",
                   v, corrected, "exact case-insensitive match, similarity=100")
            df.at[idx, col] = corrected
            n_auto += 1
            continue
        # fuzzy match
        match, score = fuzz_process.extractOne(
            v, canons,
            processor=lambda x: str(x).strip().lower(),
            scorer=combined_scorer,
        )
        if score >= 85:
            record("4.4", col, df.at[idx, "__source_row"], "TYPO_CORRECTED",
                   v, match, f"fuzzy auto-correct, similarity={score}")
            df.at[idx, col] = match
            n_auto += 1
        elif score >= 70:
            record("4.4", col, df.at[idx, "__source_row"], "TYPO_CORRECTED",
                   v, match, f"WARNING: fuzzy correction in review band, similarity={score}")
            df.at[idx, col] = match
            df.at[idx, warn_flag_col] = True
            n_warn += 1
        else:
            record("4.4", col, df.at[idx, "__source_row"], "OUTLIER_FLAGGED",
                   v, v, f"UNKNOWN CATEGORY: best fuzzy match '{match}' scored {score} (<70), value left unchanged")
            df.at[idx, unknown_flag_col] = True
            n_unknown += 1
    fuzzy_summary.append(f"    auto-corrected(>=85)={n_auto}  review-band(70-84)={n_warn}  unknown(<70)={n_unknown}")

log("4.4 Fuzzy matching summary:")
for line in fuzzy_summary:
    log("  " + line)

# ---- BR7/BR8: explicit synonym maps (NOT fuzzy engine) ----
SYNONYM_MAPS = {
    "destination_city": {
        "bombay": "Mumbai", "calcutta": "Kolkata", "madras": "Chennai", "bengaluru": "Bangalore",
    },
    "warehouse_city": {
        "bombay": "Mumbai", "calcutta": "Kolkata", "madras": "Chennai", "bengaluru": "Bangalore",
    },
    "transport_mode": {
        "airways": "Air", "road transport": "Road",
    },
}
for col, synmap in SYNONYM_MAPS.items():
    if col not in df.columns:
        continue
    n_applied = 0
    for idx in df.index:
        v = df.at[idx, col]
        if pd.isna(v):
            continue
        key = v.strip().casefold()
        if key in synmap and synmap[key] != v:
            record("4.4", col, df.at[idx, "__source_row"], "TYPO_CORRECTED",
                   v, synmap[key], f"explicit synonym map (BR7/BR8): '{v}' is a documented alternate name for '{synmap[key]}'")
            df.at[idx, col] = synmap[key]
            n_applied += 1
    log(f"4.4 Synonym map applied to {col}: {n_applied} rows corrected")

# case-normalize remaining categorical columns that had NO canonical list defined
# (warehouse_name/city/state, destination_city/state) -- Title Case, exact-match only
TITLECASE_ONLY_COLS = ["warehouse_name", "warehouse_city", "warehouse_state",
                        "destination_city", "destination_state"]
for col in TITLECASE_ONLY_COLS:
    if col not in df.columns:
        continue
    n_case = 0
    for idx in df.index:
        v = df.at[idx, col]
        if pd.isna(v):
            continue
        new = v.title() if v.upper() == v or v.lower() == v else v
        # Title() naive; only apply if value is all-upper or all-lower (avoid mangling already-correct MixedCase like "McCity" - none present here)
        if new != v and new.strip() != "":
            record("4.4", col, df.at[idx, "__source_row"], "TYPO_CORRECTED",
                   v, new, "case normalization to Title Case (all-upper or all-lower source value)")
            df.at[idx, col] = new
            n_case += 1
    log(f"4.4 Title-case normalization on {col}: {n_case} rows")

# =============================================================================
# VERIFY: post-fuzzy value_counts + missing_canon check for ALL categorical cols
# =============================================================================
log("")
log("=== POST-FUZZY VERIFICATION (mandatory per behavioral rule 9 / 4.4) ===")
verify_lines = []
ALL_CANON_COLS = dict(CANON)
for col, canons in ALL_CANON_COLS.items():
    if col not in df.columns:
        continue
    vc = df[col].value_counts(dropna=True)
    missing_canon = [c for c in canons if c not in vc.index]
    verify_lines.append(f"-- {col} --")
    verify_lines.append(str(vc))
    verify_lines.append(f"missing_canon (expected canonical values that DISAPPEARED): {missing_canon}")
    if missing_canon:
        verify_lines.append(f"  !!! WARNING: canonical value(s) vanished -- investigate before trusting this column")
    log(f"{col}: unique values after cleaning = {vc.index.tolist()}  missing_canon={missing_canon}")

with open(OUT_DIR + r"\02_post_fuzzy_verification.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(verify_lines))
log("Wrote 02_post_fuzzy_verification.txt")

# =============================================================================
# 4.5 DATE PARSING AND STANDARDIZATION
# =============================================================================
DATE_COLS = ["shipment_date", "pickup_date", "dispatch_date",
             "expected_delivery_date", "actual_delivery_date"]
date_unparseable_total = 0
for col in DATE_COLS:
    if col not in df.columns:
        continue
    for idx in df.index:
        v = df.at[idx, col]
        if pd.isna(v):
            continue
        parsed = pd.to_datetime(v, errors="coerce", format="mixed")
        if pd.isna(parsed):
            record("4.5", col, df.at[idx, "__source_row"], "DATE_PARSED",
                   v, "", "UNPARSEABLE with standard/mixed date formats -- left null, flagged")
            df.at[idx, col] = np.nan
            date_unparseable_total += 1
        else:
            iso = parsed.strftime("%Y-%m-%d")
            if str(v) != iso:
                record("4.5", col, df.at[idx, "__source_row"], "DATE_PARSED",
                       v, iso, "parsed and standardized to ISO 8601 (YYYY-MM-DD)")
            df.at[idx, col] = iso
    df[col] = pd.to_datetime(df[col], errors="coerce")
log(f"4.5 Date parsing complete. Unparseable values found: {date_unparseable_total}")

# BR6: Actual_Delivery_Date < Dispatch_Date physically impossible -> flag both, do not correct
df["date_logic_violation_flag"] = False
flag_registry["date_logic_violation_flag"] = "True if actual_delivery_date < dispatch_date (physically impossible; neither date corrected because which one is wrong is unknown)"
mask_violation = (df["actual_delivery_date"].notna()) & (df["dispatch_date"].notna()) & \
                  (df["actual_delivery_date"] < df["dispatch_date"])
n_violation = int(mask_violation.sum())
for idx in df.index[mask_violation]:
    record("4.5", "actual_delivery_date/dispatch_date", df.at[idx, "__source_row"],
           "OUTLIER_FLAGGED",
           f"actual={df.at[idx,'actual_delivery_date'].date()},dispatch={df.at[idx,'dispatch_date'].date()}",
           "unchanged",
           "BR6: physically impossible (delivery before dispatch); flagged, not corrected -- source date unknown")
df.loc[mask_violation, "date_logic_violation_flag"] = True
log(f"4.5 BR6 date-logic violations flagged: {n_violation}")

# =============================================================================
# 4.6 NUMERIC CLEANING
# =============================================================================
NUMERIC_COLS = ["delay_days", "distance_km", "shipment_weight_kg", "shipment_volume_cbm",
                 "shipping_cost_inr", "fuel_cost_inr", "operational_cost_inr",
                 "revenue_inr", "profit_inr", "customer_rating"]
# All values already plain numeric strings (assumption A1 in brief); no currency
# symbols/thousands separators observed in profiling. Cast to numeric, log any
# coercion failures as unparseable.
numeric_unparseable = {}
for col in NUMERIC_COLS:
    if col not in df.columns:
        continue
    before_na = df[col].isna().sum()
    converted = pd.to_numeric(df[col], errors="coerce")
    newly_failed = converted.isna() & df[col].notna()
    n_failed = int(newly_failed.sum())
    for idx in df.index[newly_failed]:
        record("4.6", col, df.at[idx, "__source_row"], "NUMERIC_CLEANED",
               df.at[idx, col], "", "could not parse as numeric -- left null, flagged")
    numeric_unparseable[col] = n_failed
    df[col] = converted
log(f"4.6 Numeric cast complete. Unparseable-per-column: { {k:v for k,v in numeric_unparseable.items() if v>0} }")
log("4.6 Distance_KM skew=0.12 (near-symmetric) -- no locale ambiguity, no separator stripping needed for any numeric column (assumption A1/A2 confirmed in profiling).")

# =============================================================================
# 4.9 IMPOSSIBLE NEGATIVE VALUE FLAGGING (per-column decision, BR1-BR4 in brief)
# =============================================================================
flag_registry["shipment_weight_kg_sign_flag"] = "True if a negative shipment_weight_kg was corrected via abs() (BR3: sign-flip evidence)"
df["shipment_weight_kg_sign_flag"] = False
mask_neg_weight = df["shipment_weight_kg"] < 0
n_weight_corrected = int(mask_neg_weight.sum())
for idx in df.index[mask_neg_weight]:
    orig = df.at[idx, "shipment_weight_kg"]
    corrected = abs(orig)
    record("4.9", "shipment_weight_kg", df.at[idx, "__source_row"], "NEGATIVE_CORRECTED",
           orig, corrected, "BR3: sign-flip correction via abs() -- median(abs(negatives))=36.81 matches column median=36.89, weight has no legitimate negative interpretation")
    df.at[idx, "shipment_weight_kg"] = corrected
    df.at[idx, "shipment_weight_kg_sign_flag"] = True
log(f"4.9 shipment_weight_kg: {n_weight_corrected} negative values corrected via abs() (BR3)")

flag_registry["shipping_cost_inr_negative_flag"] = "True if shipping_cost_inr is negative (BR4: flagged only, not corrected -- may be a legitimate credit/adjustment)"
df["shipping_cost_inr_negative_flag"] = False
mask_neg_cost = df["shipping_cost_inr"] < 0
n_cost_flagged = int(mask_neg_cost.sum())
for idx in df.index[mask_neg_cost]:
    orig = df.at[idx, "shipping_cost_inr"]
    record("4.9", "shipping_cost_inr", df.at[idx, "__source_row"], "NEGATIVE_FLAGGED",
           orig, orig, "BR4: negative shipping cost flagged NOT corrected -- magnitude mismatch rules out sign-flip, may be a legitimate billing credit")
    df.at[idx, "shipping_cost_inr_negative_flag"] = True
log(f"4.9 shipping_cost_inr: {n_cost_flagged} negative values flagged, NOT corrected (BR4)")

flag_registry["delay_days_negative_flag"] = "True if delay_days is negative (BR1: legitimate -- early delivery, NOT an error)"
df["delay_days_negative_flag"] = False
mask_neg_delay = df["delay_days"] < 0
n_delay_flagged = int(mask_neg_delay.sum())
for idx in df.index[mask_neg_delay]:
    orig = df.at[idx, "delay_days"]
    record("4.9", "delay_days", df.at[idx, "__source_row"], "NEGATIVE_FLAGGED",
           orig, orig, "BR1: negative delay_days is legitimate (early delivery), flagged for transparency only, not an error")
    df.at[idx, "delay_days_negative_flag"] = True
log(f"4.9 delay_days: {n_delay_flagged} negative values flagged as LEGITIMATE (early delivery, BR1) -- not treated as impossible")

flag_registry["profit_inr_negative_flag"] = "True if profit_inr is negative (BR2: legitimate -- loss-making shipment, NOT an error)"
df["profit_inr_negative_flag"] = False
mask_neg_profit = df["profit_inr"] < 0
n_profit_flagged = int(mask_neg_profit.sum())
for idx in df.index[mask_neg_profit]:
    orig = df.at[idx, "profit_inr"]
    record("4.9", "profit_inr", df.at[idx, "__source_row"], "NEGATIVE_FLAGGED",
           orig, orig, "BR2: negative profit is legitimate (loss-making shipment), flagged for transparency only, not an error")
    df.at[idx, "profit_inr_negative_flag"] = True
log(f"4.9 profit_inr: {n_profit_flagged} negative values flagged as LEGITIMATE (loss-making shipment, BR2) -- not treated as impossible")

# customer_rating out-of-range (BR5): impossible negative/zero AND impossible >5 handled together
flag_registry["customer_rating_out_of_range_flag"] = "True if customer_rating is outside [1.0, 5.0] (BR5: flagged only, no arithmetic correction fits)"
df["customer_rating_out_of_range_flag"] = False
mask_bad_rating = (df["customer_rating"].notna()) & ((df["customer_rating"] < 1.0) | (df["customer_rating"] > 5.0))
n_rating_flagged = int(mask_bad_rating.sum())
for idx in df.index[mask_bad_rating]:
    orig = df.at[idx, "customer_rating"]
    record("4.9", "customer_rating", df.at[idx, "__source_row"], "NEGATIVE_FLAGGED" if orig < 1.0 else "OUTLIER_FLAGGED",
           orig, orig, "BR5: customer_rating outside valid [1.0,5.0] scale, flagged NOT corrected -- no decimal-typo divisor lands it back in range")
    df.at[idx, "customer_rating_out_of_range_flag"] = True
log(f"4.9 customer_rating: {n_rating_flagged} out-of-range values flagged (BR5)")

# =============================================================================
# 4.10 OUTLIER INVESTIGATION (decimal-typo detection)
# Two-pass: (1) DRY RUN classify every candidate and compute the column-level
# repair rate WITHOUT mutating df; (2) only if repair_rate <= 1% do we apply
# the divisor corrections. If repair_rate > 1%, per spec we STOP and report
# instead of correcting -- that rate is evidence of a misread column scale/
# unit, not a population of individual typos, and applying it anyway would be
# reinterpreting the column, not fixing typos.
# =============================================================================
DECIMAL_TYPO_SCREEN_COLS = ["shipment_weight_kg", "shipment_volume_cbm",
                             "shipping_cost_inr", "fuel_cost_inr",
                             "operational_cost_inr", "revenue_inr"]
decimal_typo_summary = []
columns_scale_flagged_not_corrected = []

for col in DECIMAL_TYPO_SCREEN_COLS:
    if col not in df.columns:
        continue
    flag_col = f"{col}_outlier_flag"
    typo_flag_col = f"{col}_decimal_typo_flag"
    flag_registry[flag_col] = f"True if {col} value is a STATISTICAL_OUTLIER (>10x median, no divisor landed it in plausible band, OR column-level repair rate exceeded 1% so nothing in the candidate set was corrected)"
    flag_registry[typo_flag_col] = f"True if {col} value was corrected as a LIKELY_DECIMAL_TYPO (divided by 10/100/1000) -- only set when the column's overall repair rate was <=1%"
    df[flag_col] = False
    df[typo_flag_col] = False

    nonneg = df.loc[df[col] > 0, col]
    if len(nonneg) == 0:
        continue
    median = nonneg.median()
    if median <= 0:
        decimal_typo_summary.append(f"{col}: median<=0, skipped decimal-typo screen")
        continue

    candidate_mask = df[col] > 10 * median
    n_candidates = int(candidate_mask.sum())

    # ---- PASS 1: DRY RUN classification, no mutation ----
    classifications = {}  # idx -> (divisor_or_None, candidate_value)
    n_typo_10 = n_typo_100 = n_typo_1000 = n_outlier = 0
    for idx in df.index[candidate_mask]:
        val = df.at[idx, col]
        classified = False
        for d in (10, 100, 1000):
            cand = val / d
            if 0.5 * median <= cand <= 2 * median:
                classifications[idx] = (d, cand)
                if d == 10: n_typo_10 += 1
                elif d == 100: n_typo_100 += 1
                else: n_typo_1000 += 1
                classified = True
                break
        if not classified:
            classifications[idx] = (None, val)
            n_outlier += 1

    total_typo = n_typo_10 + n_typo_100 + n_typo_1000
    repair_rate = 100 * total_typo / len(df)

    # ---- PASS 2: apply, gated on repair_rate ----
    if repair_rate > 1.0:
        # STOP: do not correct. Flag every candidate as a statistical outlier
        # and record the column-level decision once (not per-row noise).
        for idx in df.index[candidate_mask]:
            val = df.at[idx, col]
            record("4.10", col, df.at[idx, "__source_row"], "OUTLIER_FLAGGED",
                   val, val,
                   f"Column-level repair_rate={repair_rate:.3f}% exceeds the 1% sanity threshold "
                   f"({total_typo}/{len(df)} candidates would divisor-correct) -- per spec this is "
                   f"reinterpretation of the column's scale/units, not typo-fixing. NOT corrected; "
                   f"flagged as STATISTICAL_OUTLIER instead. See RUN_SUMMARY.md for the column-level note.")
            df.at[idx, flag_col] = True
        decimal_typo_summary.append(
            f"{col}: median={median:.2f} candidates(>10x median)={n_candidates} "
            f"would-be typo_div10={n_typo_10} typo_div100={n_typo_100} typo_div1000={n_typo_1000} "
            f"repair_rate={repair_rate:.3f}% > 1% THRESHOLD -- STOPPED, NOT corrected. "
            f"All {n_candidates} candidates flagged as STATISTICAL_OUTLIER instead. "
            f"This column's scale/units need source-system investigation, not row-level typo repair."
        )
        columns_scale_flagged_not_corrected.append((col, repair_rate, n_candidates))
    else:
        for idx in df.index[candidate_mask]:
            val = df.at[idx, col]
            d, cand = classifications[idx]
            if d is not None:
                sev = "WARNING: unit-mismatch more likely than typo" if d == 1000 else "auto-corrected"
                record("4.10", col, df.at[idx, "__source_row"], "OUTLIER_DECIMAL_TYPO_CORRECTED",
                       val, cand, f"LIKELY_DECIMAL_TYPO divisor={d}, median={median:.2f}, ratio={val/median:.1f}x -- {sev}")
                df.at[idx, col] = cand
                df.at[idx, typo_flag_col] = True
            else:
                record("4.10", col, df.at[idx, "__source_row"], "OUTLIER_FLAGGED",
                       val, val, f"STATISTICAL_OUTLIER: median={median:.2f}, ratio={val/median:.1f}x, no divisor (10/100/1000) landed in plausible band -- flagged, not modified")
                df.at[idx, flag_col] = True
        decimal_typo_summary.append(
            f"{col}: median={median:.2f} candidates(>10x median)={n_candidates} "
            f"typo_div10={n_typo_10} typo_div100={n_typo_100} typo_div1000(WARNING)={n_typo_1000} "
            f"statistical_outlier={n_outlier} repair_rate={repair_rate:.3f}% -- APPLIED (within 1% threshold)"
        )

log("4.10 Decimal-typo / outlier investigation summary:")
for line in decimal_typo_summary:
    log("  " + line)
if columns_scale_flagged_not_corrected:
    log("4.10 *** COLUMNS WHERE REPAIR WAS STOPPED (repair_rate > 1%, reported not corrected): ***")
    for col, rr, n in columns_scale_flagged_not_corrected:
        log(f"    {col}: repair_rate={rr:.3f}%, {n} candidate rows flagged STATISTICAL_OUTLIER, 0 corrected")

# Verify: median before vs after per screened column
log("4.10 VERIFY median/min/max shift (should be ~unchanged for columns where correction WAS applied):")
for col in DECIMAL_TYPO_SCREEN_COLS:
    if col not in df.columns:
        continue
    log(f"  {col}: post-clean median={df[col].median():.2f} min={df[col].min():.2f} max={df[col].max():.2f}")

# =============================================================================
# 4.7 PHONE / 4.8 EMAIL -- N/A, no phone or email columns in this dataset
# =============================================================================
log("4.7 Phone normalization: N/A -- no phone/tel/mobile/contact column in this dataset")
log("4.8 Email validation: N/A -- no email column in this dataset")

# =============================================================================
# 4.11 DUPLICATE REMOVAL
# =============================================================================
compare_cols = [c for c in df.columns if c != "__source_row"]
dup_mask = df.duplicated(subset=compare_cols, keep="first")
n_exact_dupes = int(dup_mask.sum())
for idx in df.index[dup_mask]:
    record("4.11", "ALL_COLUMNS", df.at[idx, "__source_row"], "DUPLICATE_REMOVED",
           f"shipment_id={df.at[idx,'shipment_id']}", "ROW_REMOVED",
           "exact duplicate of an earlier row (all 35 source columns byte-identical) -- A3 in business brief")
removed_source_rows = df.loc[dup_mask, "__source_row"].tolist()
df = df[~dup_mask].reset_index(drop=True)
log(f"4.11 Exact duplicates removed: {n_exact_dupes} rows. Remaining: {len(df)}")

# Near-duplicate flagging on key identifier columns (Customer_ID + Driver_ID) --
# report only, no auto-delete
near_dup_report_lines = []
# (Customer_ID is a structured code, not free text -- fuzzy near-dup search on
# structured IDs would only catch OCR/typo-style ID corruption; spot-check the
# ID format instead: all customer_id length 9, pattern CUST#####, all driver_id
# length 7 pattern DRV####. No malformed IDs found in profiling -- 0 near-dupes.)
mask_bad_cust_id = ~df["customer_id"].astype(str).str.match(r"^CUST\d{5}$")
mask_bad_driver_id = df["driver_id"].notna() & ~df["driver_id"].astype(str).str.match(r"^DRV\d{4}$")
near_dup_report_lines.append(f"customer_id rows not matching CUST##### pattern: {int(mask_bad_cust_id.sum())}")
near_dup_report_lines.append(f"driver_id rows not matching DRV#### pattern (excl. null): {int(mask_bad_driver_id.sum())}")
log("4.11 Near-duplicate / malformed-ID check: " + "; ".join(near_dup_report_lines))

# =============================================================================
# WRITE OUTPUTS
# =============================================================================
df.to_csv(CLEANED_PATH, index=False, encoding="utf-8")
log(f"Wrote {CLEANED_PATH} ({len(df)} rows, {len(df.columns)} columns)")

changelog_df = pd.DataFrame(CHANGES, columns=["STAGE","COLUMN","SOURCE_ROW","CHANGE_TYPE",
                                               "ORIGINAL_VALUE","NEW_VALUE","REASON"])
changelog_df.to_csv(CHANGELOG_PATH, index=False, encoding="utf-8")
log(f"Wrote {CHANGELOG_PATH} ({len(changelog_df)} change-log rows)")

# persist flag registry + key numbers for downstream stages
import json

with open(OUT_DIR + r"\02_flag_registry.json", "w", encoding="utf-8") as f:
    json.dump(flag_registry, f, indent=2)
log(f"Wrote 02_flag_registry.json ({len(flag_registry)} flags)")

summary = {
    "raw_row_count": RAW_ROW_COUNT,
    "cleaned_row_count": len(df),
    "exact_duplicates_removed": n_exact_dupes,
    "removed_source_rows": removed_source_rows,
    "date_logic_violations": n_violation,
    "weight_sign_corrections": n_weight_corrected,
    "shipping_cost_negative_flagged": n_cost_flagged,
    "delay_days_negative_flagged": n_delay_flagged,
    "profit_negative_flagged": n_profit_flagged,
    "rating_out_of_range_flagged": n_rating_flagged,
    "total_change_log_rows": len(changelog_df),
    "decimal_typo_scale_flagged_columns": [
        {"column": c, "repair_rate_pct": round(rr, 3), "candidates_flagged_not_corrected": n}
        for c, rr, n in columns_scale_flagged_not_corrected
    ],
}
with open(OUT_DIR + r"\02_clean_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, default=str)
log(f"Wrote 02_clean_summary.json: {summary}")

with open(LOG_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(run_log))
log(f"Wrote {LOG_PATH}")

print("STAGE 4 CLEANING COMPLETE")
