#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
03_clean.py -- Stage 4 (Data Cleaning) for messy_sales.csv.

Executes 4.1 - 4.11 in the exact order specified: header normalization, null
standardization (with the ambiguity gate), string normalization, categorical fuzzy
matching (collision guard already cleared in 02_extract_and_profile.py), date parsing,
numeric cleaning, phone normalization, email validation/repair, impossible-negative
flagging, outlier/decimal-typo investigation, duplicate removal.

Produces:
  cleaned_data.csv   -- full audit trail, flagged rows kept
  change_log.csv     -- row-level log, one row per change, __source_row keyed
  03_clean_report.txt -- narrative report with all the "verify afterwards" checks
"""

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

import os
import re
import math
import datetime as dt
import pandas as pd
import numpy as np
from dateutil import parser as dtparser
from rapidfuzz import fuzz as rfuzz, process as rprocess

OUT_DIR = str(_HERE)
PICKLE_RAW = os.path.join(OUT_DIR, "_raw_with_source_row.pkl")
CLEANED_CSV = os.path.join(OUT_DIR, "cleaned_data.csv")
CHANGELOG_CSV = os.path.join(OUT_DIR, "change_log.csv")
REPORT = os.path.join(OUT_DIR, "03_clean_report.txt")

rpt = []
def log(s=""):
    rpt.append(str(s))

changes = []  # list of dicts: STAGE, COLUMN, SOURCE_ROW, CHANGE_TYPE, ORIGINAL_VALUE, NEW_VALUE, REASON
def log_change(stage, column, source_row, change_type, original, new, reason):
    changes.append({
        "STAGE": stage, "COLUMN": column, "SOURCE_ROW": source_row,
        "CHANGE_TYPE": change_type,
        "ORIGINAL_VALUE": "" if original is None else str(original),
        "NEW_VALUE": "" if new is None else str(new),
        "REASON": reason,
    })

df = pd.read_pickle(PICKLE_RAW).astype(object)  # object dtype avoids the pyarrow .at[] gotcha
log("=" * 78)
log("STAGE 4 -- DATA CLEANING")
log("=" * 78)
log(f"Loaded {len(df)} raw rows from {PICKLE_RAW}")

# =====================================================================================
# 4.1 HEADER NORMALIZATION
# =====================================================================================
RENAME = {
    "order_id": "order_id",
    "Order_Date": "order_date",
    "customer name": "customer_name",
    "Customer Email": "customer_email",
    "Phone Number": "phone_number",
    "region ": "region",
    "Product": "product",
    "channel": "channel",
    "Units Sold": "units_sold",
    "unit_price": "unit_price",
    "Total Revenue": "total_revenue",
}
log("\n--- 4.1 Header normalization ---")
for old, new in RENAME.items():
    if old != new:
        log(f"  {old!r} -> {new!r}")
    log_change(4.1, old, "ALL", "HEADER_RENAME", old, new,
               "snake_case normalization; trailing-space/embedded-space/casing removed")
df = df.rename(columns=RENAME)
df = df[["__source_row"] + list(RENAME.values())]  # fixed column order for the rest of cleaning

# =====================================================================================
# 4.2 NULL STANDARDIZATION (match on stripped, casefolded value; gate the ambiguous set)
# =====================================================================================
UNAMBIGUOUS = {"", " ", "?", "null", "none", "tbd", "undefined", "#n/a", "#value!", "#ref!", "n/a"}
AMBIGUOUS = {"na", "-", "unknown"}

# canonical sets used by the gate -- named explicitly per column, not inferred from frequency
CANON_SETS = {
    "region": {"north", "south", "east", "west", "northeast"},
    "product": {"alpha", "beta", "gamma", "delta"},
    "channel": {"retail", "wholesale", "online", "brick & mortar", "b2b", "b2c"},
}

def gate_verdict(col, token):
    """Returns (allow_as_real_value: bool, reason: str)."""
    if col == "product":
        return False, "product is a closed 4-value Greek-letter set (Alpha/Beta/Gamma/Delta); 'Unknown' cannot be a 5th member -> null disguise, not a real product."
    if col == "customer_name":
        return False, "customer_name is a free-text person name; 'Unknown' cannot be a real name -> null disguise."
    if col in ("region", "channel"):
        return False, f"{col} canonical set is {sorted(CANON_SETS[col])}; token {token!r} is not a member -> null disguise, not a real category."
    if col == "order_date":
        return False, "order_date is a date field; a bare token cannot be a valid date -> null disguise."
    if col == "phone_number":
        return False, "phone_number cannot legitimately be a bare punctuation/word token -> null disguise."
    if col in ("units_sold", "unit_price", "total_revenue"):
        return False, f"{col} is a numeric measure; a bare token cannot be a legitimate quantity -> null disguise."
    return False, "no documented canonical meaning for this token in this column -> null disguise (default: treat as missing, not guess a meaning)."

log("\n--- 4.2 Null standardization ---")
null_before = {}
null_after = {}
for col in [c for c in df.columns if c != "__source_row"]:
    null_before[col] = int(df[col].map(lambda v: str(v).strip() == "").sum())

for col in [c for c in df.columns if c != "__source_row"]:
    for idx in df.index:
        raw_val = df.at[idx, col]
        token = str(raw_val).strip().casefold()
        if token == "":
            continue  # already-blank cells are handled below in the unambiguous pass
        src_row = df.at[idx, "__source_row"]
        if token in UNAMBIGUOUS:
            if raw_val != np.nan:
                log_change(4.2, col, src_row, "NULL_STANDARDIZED", raw_val, None,
                           f"unambiguous null disguise token ({token!r})")
                df.at[idx, col] = np.nan
        elif token in AMBIGUOUS:
            allow, reason = gate_verdict(col, token)
            if not allow:
                log_change(4.2, col, src_row, "NULL_STANDARDIZED", raw_val, None,
                           f"ambiguity-guard GATE=NO: {reason}")
                df.at[idx, col] = np.nan
            else:
                log_change(4.2, col, src_row, "NULL_DISGUISE_RETAINED", raw_val, raw_val, reason)

# now count truly-blank (post null-standardization) as null too
for idx in df.index:
    for col in [c for c in df.columns if c != "__source_row"]:
        v = df.at[idx, col]
        if isinstance(v, str) and v.strip() == "":
            src_row = df.at[idx, "__source_row"]
            log_change(4.2, col, src_row, "NULL_STANDARDIZED", v, None, "blank/whitespace-only cell")
            df.at[idx, col] = np.nan

for col in [c for c in df.columns if c != "__source_row"]:
    null_after[col] = int(df[col].isna().sum())
    log(f"  {col:16s} null rate before: {null_before[col]:3d}/{len(df)}  ->  after: {null_after[col]:3d}/{len(df)}")

# =====================================================================================
# 4.3 STRING NORMALIZATION (strip, collapse internal whitespace, NFC)
# =====================================================================================
import unicodedata

log("\n--- 4.3 String normalization ---")
str_norm_count = 0
STR_COLS = ["order_id", "customer_name", "customer_email", "phone_number", "region", "product", "channel"]
for col in STR_COLS:
    for idx in df.index:
        v = df.at[idx, col]
        if not isinstance(v, str):
            continue
        nfc = unicodedata.normalize("NFC", v)
        collapsed = re.sub(r"\s+", " ", nfc.strip())
        if collapsed != v:
            src_row = df.at[idx, "__source_row"]
            log_change(4.3, col, src_row, "STRING_NORMALIZED", v, collapsed,
                       "stripped leading/trailing whitespace and collapsed internal whitespace")
            df.at[idx, col] = collapsed
            str_norm_count += 1
log(f"  Cells normalized (whitespace/NFC): {str_norm_count}")

# =====================================================================================
# 4.4 CATEGORICAL TYPO CORRECTION (fuzzy matching) -- collision guard already cleared
# =====================================================================================
log("\n--- 4.4 Categorical typo correction (fuzzy matching) ---")
log("  Collision guard result (from 02_extract_and_profile.py): NO collisions on region/")
log("  product/channel canonical sets -> fuzzy matching is safe for all three.")

CANON = {
    "region": ["North", "South", "East", "West", "Northeast"],
    "product": ["Alpha", "Beta", "Gamma", "Delta"],
    "channel": ["Retail", "Wholesale", "Online", "Brick & Mortar", "B2B", "B2C"],
}

def fuzzy_processor(x):
    return str(x).strip().lower()

def alnum_key(s):
    return re.sub(r"[^a-z0-9]", "", str(s).strip().lower())

def fuzzy_match_col(col, canon_list):
    n_auto = n_warn = n_unknown = n_alias = 0
    # Alias map: same alnum-fold approach as the collision guard itself. The guard already
    # proved (02_extract_and_profile.py) that no two canonicals collide under this fold for this
    # column, so a fold-match here is unambiguous -- it is not a guess, it is the same fact the
    # guard already verified, applied forward. This catches whitespace/hyphen-only variants
    # ("north east" -> "Northeast", "on-line"/"on line" -> "Online") that token_sort_ratio
    # under-scores because it treats the missing/extra space as a real token-boundary difference
    # (same failure class documented for insurance_provider in the healthcare lineage).
    canon_by_alnum = {alnum_key(c): c for c in canon_list}
    for idx in df.index:
        v = df.at[idx, col]
        if not isinstance(v, str) or v == "":
            continue
        src_row = df.at[idx, "__source_row"]
        # exact case-insensitive match first -- don't burn a fuzzy call on something already canonical
        exact = next((c for c in canon_list if c.lower() == v.strip().lower()), None)
        if exact is not None:
            if exact != v:
                log_change(4.4, col, src_row, "STRING_NORMALIZED", v, exact,
                           "exact case-insensitive match to canonical form")
                df.at[idx, col] = exact
            continue
        alias = canon_by_alnum.get(alnum_key(v))
        if alias is not None:
            log_change(4.4, col, src_row, "TYPO_CORRECTED", v, alias,
                       "whitespace/hyphen-insensitive alias match (alnum-folded key matches "
                       "exactly one canonical value; collision guard already proved this fold "
                       "is unambiguous for this column) -- not a fuzzy score, a direct alias")
            df.at[idx, col] = alias
            n_alias += 1
            continue
        match = rprocess.extractOne(
            v, canon_list,
            processor=fuzzy_processor,
            scorer=lambda a, b, **kw: rfuzz.token_sort_ratio(a, b),
        )
        src_row = df.at[idx, "__source_row"]
        if match is None:
            continue
        cand, score, _ = match
        if score >= 85:
            log_change(4.4, col, src_row, "TYPO_CORRECTED", v, cand, f"fuzzy token_sort_ratio={score:.1f} >= 85, auto-corrected")
            df.at[idx, col] = cand
            n_auto += 1
        elif score >= 70:
            log_change(4.4, col, src_row, "TYPO_CORRECTED", v, cand, f"WARNING: fuzzy token_sort_ratio={score:.1f} in 70-84 band, corrected with review flag")
            df.at[idx, col] = cand
            df.at[idx, f"{col}_fuzzy_review_flag"] = True
            n_warn += 1
        else:
            log_change(4.4, col, src_row, "OUTLIER_FLAGGED", v, v, f"fuzzy token_sort_ratio={score:.1f} < 70, UNKNOWN CATEGORY, left uncorrected")
            df.at[idx, f"{col}_unknown_category_flag"] = True
            n_unknown += 1
    log(f"  {col}: alias(whitespace/hyphen-fold)={n_alias}  auto-corrected(>=85)={n_auto}  warned(70-84)={n_warn}  unknown(<70)={n_unknown}")

for col, canon_list in CANON.items():
    if f"{col}_fuzzy_review_flag" not in df.columns:
        df[f"{col}_fuzzy_review_flag"] = False
    if f"{col}_unknown_category_flag" not in df.columns:
        df[f"{col}_unknown_category_flag"] = False
    fuzzy_match_col(col, canon_list)

log("\n  Post-match value_counts() + missing-canon check (behavioral rule 9 / spec 4.4 verify):")
for col, canon_list in CANON.items():
    vc = df[col].value_counts(dropna=True)
    log(f"\n  {col} value_counts:\n" + "\n".join(f"    {k!r}: {v}" for k, v in vc.items()))
    missing_canon = [c for c in canon_list if c not in vc.index]
    log(f"  {col} missing_canon (canonical values that disappeared entirely): {missing_canon}")
    if missing_canon:
        log(f"  *** WARNING: investigate -- a canonical value vanished after fuzzy matching. ***")

# =====================================================================================
# 4.5 DATE PARSING
# =====================================================================================
log("\n--- 4.5 Date parsing (order_date) ---")
n_parsed = n_excel_serial = n_unparseable = 0
EXCEL_EPOCH = dt.datetime(1899, 12, 30)
parsed_dates = {}  # idx -> python datetime, kept as OBJECTS -- never round-tripped through a
                    # formatted string and re-parsed. A mixed date-only / datetime-with-time
                    # column fed back through pd.to_datetime() without an explicit format lets
                    # pandas' format auto-detection lock onto the first row's shape and silently
                    # coerce every row that doesn't match it to NaT -- caught by comparing the
                    # null count after this step against the count of rows actually logged as
                    # unparseable (37 rows were silently lost this way on the first attempt).

for idx in df.index:
    v = df.at[idx, "order_date"]
    src_row = df.at[idx, "__source_row"]
    if not isinstance(v, str) or v == "":
        continue
    parsed = None
    fmt_detected = None
    # Excel serial: bare integer string, plausible range for 2020-2030ish dates (43000-48000)
    if re.match(r"^\d{5}$", v.strip()):
        serial = int(v.strip())
        try:
            parsed = EXCEL_EPOCH + dt.timedelta(days=serial)
            fmt_detected = "EXCEL_SERIAL"
            n_excel_serial += 1
        except Exception:
            parsed = None
    if parsed is None:
        try:
            parsed = dtparser.parse(v.strip(), dayfirst=True)
            fmt_detected = "PARSED(dayfirst=True)"
        except Exception:
            parsed = None
    if parsed is not None:
        new_val_str = parsed.strftime("%Y-%m-%d %H:%M:%S") if (parsed.hour or parsed.minute or parsed.second) else parsed.strftime("%Y-%m-%d")
        log_change(4.5, "order_date", src_row, "DATE_PARSED", v, new_val_str, f"format detected: {fmt_detected}")
        parsed_dates[idx] = parsed  # keep the actual datetime OBJECT, not the string
        n_parsed += 1
    else:
        log_change(4.5, "order_date", src_row, "DATE_PARSED", v, None,
                   "UNPARSEABLE -- could not be parsed as a valid calendar date (e.g. invalid day-of-month for that month/year); left as null, NOT guessed to a nearby valid date")
        df.at[idx, "order_date_unparseable_flag"] = True
        n_unparseable += 1

if "order_date_unparseable_flag" not in df.columns:
    df["order_date_unparseable_flag"] = False
df["order_date_unparseable_flag"] = df["order_date_unparseable_flag"].fillna(False)

log(f"  Parsed successfully: {n_parsed} (of which Excel-serial: {n_excel_serial})")
log(f"  Unparseable (flagged, left null): {n_unparseable}")
unparse_examples = [(r["SOURCE_ROW"], r["ORIGINAL_VALUE"]) for r in changes
                    if r["COLUMN"] == "order_date" and r["CHANGE_TYPE"] == "DATE_PARSED" and r["NEW_VALUE"] == ""]
log(f"  Unparseable examples: {unparse_examples[:10]}")
n_null_before_45 = int(df["order_date"].isna().sum())

# Build the final datetime column directly from the python datetime objects collected above --
# cells never touched by the loop (already null before 4.5) stay NaT; cells the loop parsed use
# the actual object, not a re-parsed string.
date_series = pd.Series([parsed_dates.get(idx, pd.NaT) for idx in df.index], index=df.index)
df["order_date"] = pd.to_datetime(date_series, errors="coerce")
n_null_after_45 = int(df["order_date"].isna().sum())
n_expected_null_after_45 = n_null_before_45 + n_unparseable
log(f"  VERIFY (behavioral rule 9): null count before 4.5 loop = {n_null_before_45}, "
    f"+ {n_unparseable} newly-unparseable this step = expected {n_expected_null_after_45}, "
    f"actual after datetime cast = {n_null_after_45}  "
    f"{'OK' if n_null_after_45 == n_expected_null_after_45 else '*** MISMATCH -- datetime cast silently dropped rows ***'}")
assert n_null_after_45 == n_expected_null_after_45, "order_date null count changed unexpectedly during dtype cast"

# =====================================================================================
# 4.6 NUMERIC CLEANING
# =====================================================================================
log("\n--- 4.6 Numeric cleaning ---")

def clean_numeric_cell(v):
    """Returns (parsed_float_or_None, notes_str_or_None)."""
    if not isinstance(v, str) or v.strip() == "":
        return None, None
    orig = v
    s = v.strip()
    notes = []
    # strip currency symbols anywhere in the string
    currency_chars = "$\u20b9\u20ac\u00a3"
    if any(ch in s for ch in currency_chars):
        s2 = "".join(ch for ch in s if ch not in currency_chars)
        s = s2.strip()
        notes.append("stripped currency symbol")
    # strip trailing Indian-rupee shorthand "/-"
    if s.endswith("/-"):
        s = s[:-2].strip()
        notes.append("stripped trailing '/-' (Indian rupee shorthand)")
    # strip a trailing unit-label word like "units" / "unit"
    m = re.match(r"^(-?[\d.,]+)\s*(units?|pcs?)?$", s, flags=re.IGNORECASE)
    if m and m.group(2):
        s = m.group(1)
        notes.append(f"stripped trailing unit-label {m.group(2)!r}")
    s = s.strip()
    if s == "":
        return None, "; ".join(notes) if notes else None
    # US/UK locale decision for this dataset (see 02_profile_report.txt survey): column is
    # overwhelmingly plain dot-decimal; comma, where present, is a thousands separator.
    # Applied uniformly per spec 4.6 -- never per-value.
    if "," in s:
        s = s.replace(",", "")
        notes.append("removed ',' as thousands separator (US/UK locale decision for this column)")
    try:
        f = float(s)
    except ValueError:
        return None, ("UNPARSEABLE: " + "; ".join(notes)) if notes else "UNPARSEABLE"
    return f, ("; ".join(notes) if notes else None)

for col in ["units_sold", "unit_price", "total_revenue"]:
    n_cleaned = n_unparseable_num = 0
    for idx in df.index:
        v = df.at[idx, col]
        if not isinstance(v, str):
            continue
        src_row = df.at[idx, "__source_row"]
        parsed, notes = clean_numeric_cell(v)
        if parsed is None and notes and notes.startswith("UNPARSEABLE"):
            log_change(4.6, col, src_row, "NUMERIC_CLEANED", v, None, f"could not parse as numeric: {notes}")
            df.at[idx, col] = np.nan
            n_unparseable_num += 1
        elif parsed is None:
            df.at[idx, col] = np.nan
        else:
            if notes:
                log_change(4.6, col, src_row, "NUMERIC_CLEANED", v, parsed, notes)
                n_cleaned += 1
            df.at[idx, col] = parsed
    log(f"  {col}: transformed(logged)={n_cleaned}  unparseable={n_unparseable_num}")

for col in ["units_sold", "unit_price", "total_revenue"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# =====================================================================================
# 4.7 PHONE NUMBER NORMALIZATION
# =====================================================================================
log("\n--- 4.7 Phone number normalization ---")
n_e164 = n_inferred = n_unknown_country = n_blank = 0
for idx in df.index:
    v = df.at[idx, "phone_number"]
    if not isinstance(v, str) or v.strip() == "":
        continue
    src_row = df.at[idx, "__source_row"]
    orig = v
    digits = re.sub(r"\D", "", v)
    new_val = None
    reason = None
    if digits.startswith("91") and len(digits) == 12:
        new_val = "+" + digits
        reason = "already carries 91 country-code prefix; formatted to E.164"
    elif len(digits) == 10 and digits[0] in "6789":
        new_val = "+91" + digits
        reason = ("country code inferred as +91: Stage-1 assumption A2 (Indian customer base "
                   "evidence: 134/312 phone cells already carry a 91 prefix, and unprefixed "
                   "10-digit numbers uniformly start 6-9, the valid Indian mobile range)")
        n_inferred += 1
    else:
        df.at[idx, "phone_number_country_unknown_flag"] = True
        n_unknown_country += 1
        log_change(4.7, "phone_number", src_row, "PHONE_COUNTRY_UNKNOWN", orig, orig,
                   f"digits={digits!r} do not match a recognized 10-digit-Indian-mobile or "
                   f"91-prefixed pattern; left as-is rather than guessing a country code")
        continue
    log_change(4.7, "phone_number", src_row, "PHONE_NORMALIZED", orig, new_val, reason)
    df.at[idx, "phone_number"] = new_val
    n_e164 += 1

if "phone_number_country_unknown_flag" not in df.columns:
    df["phone_number_country_unknown_flag"] = False
df["phone_number_country_unknown_flag"] = df["phone_number_country_unknown_flag"].fillna(False)
log(f"  Normalized to E.164: {n_e164} (of which country-code inferred: {n_inferred})")
log(f"  Flagged PHONE_COUNTRY_UNKNOWN: {n_unknown_country}")

# =====================================================================================
# 4.8 EMAIL VALIDATION, NORMALIZATION, DECLARED REPAIR
# =====================================================================================
log("\n--- 4.8 Email validation and normalization ---")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
n_norm = n_valid = n_invalid = n_repaired = 0
for idx in df.index:
    v = df.at[idx, "customer_email"]
    if not isinstance(v, str) or v.strip() == "":
        continue
    src_row = df.at[idx, "__source_row"]
    orig = v
    # normalization: lowercase + strip ALL whitespace (embedded whitespace cannot be part of a
    # real address; removing it does not change which mailbox is referenced) -- nothing else.
    normed = re.sub(r"\s+", "", v).lower()
    if normed != v:
        log_change(4.8, "customer_email", src_row, "EMAIL_NORMALIZED", orig, normed,
                   "lowercased and stripped whitespace (including embedded whitespace around '@')")
        df.at[idx, "customer_email"] = normed
        n_norm += 1
    cur = df.at[idx, "customer_email"]
    if EMAIL_RE.match(cur):
        n_valid += 1
        continue
    # declared repair, separate step: only for the specific, evidenced pattern -- a missing '@'
    # where the value otherwise ends in the dataset's single uniform domain "example.com" and the
    # character immediately before that domain is '.' rather than '@' (assumption A3 in the brief).
    m = re.match(r"^([a-z0-9._]+)\.example\.com$", cur)
    if m and "@" not in cur:
        repaired = m.group(1).rsplit(".", 0)[0]  # placeholder, replaced below
        # replace the LAST '.' before 'example.com' with '@'
        prefix = cur[: -len(".example.com")]
        repaired = prefix + "@example.com"
        log_change(4.8, "customer_email", src_row, "EMAIL_REPAIRED", cur, repaired,
                   "deterministic repair: value matches the dataset's single uniform domain "
                   "'example.com' via '.' where '@' belongs (assumption A3); NOT a guess because "
                   "the domain pattern is uniform across the whole file (291/312+21/312 case-"
                   "variant rows) and only the delimiter character is missing")
        df.at[idx, "customer_email"] = repaired
        df.at[idx, "customer_email_repaired_flag"] = True
        n_repaired += 1
        n_valid += 1  # repaired addresses are valid post-repair; NOT counted in as-received V7 rate
    else:
        log_change(4.8, "customer_email", src_row, "EMAIL_INVALID_FLAGGED", cur, cur,
                   "does not match RFC-5322-simplified pattern and does not match the declared "
                   "repair pattern; left as-is, not guessed")
        df.at[idx, "customer_email_invalid_flag"] = True
        n_invalid += 1

for c in ["customer_email_repaired_flag", "customer_email_invalid_flag"]:
    if c not in df.columns:
        df[c] = False
    df[c] = df[c].fillna(False)

log(f"  Normalized (case/whitespace): {n_norm}")
log(f"  Valid (post-normalization, PRE-repair, i.e. as-received): "
    f"{n_valid - n_repaired} / {int((df['customer_email'].notna()).sum())}")
log(f"  Repaired (declared, separate step): {n_repaired}")
log(f"  Invalid, flagged, left as-is: {n_invalid}")

# =====================================================================================
# 4.9 IMPOSSIBLE NEGATIVE VALUE FLAGGING
# =====================================================================================
log("\n--- 4.9 Impossible negative value flagging ---")
for col in ["units_sold", "unit_price", "total_revenue"]:
    flagcol = f"{col}_sign_flag"
    df[flagcol] = False
    neg_mask = df[col] < 0
    n_neg = int(neg_mask.sum())
    for idx in df.index[neg_mask]:
        src_row = df.at[idx, "__source_row"]
        log_change(4.9, col, src_row, "NEGATIVE_FLAGGED", df.at[idx, col], df.at[idx, col],
                   f"{col} < 0 is physically impossible for a sales order (business_rules.BR2); "
                   f"flagged, NOT sign-corrected -- sign could be a data-entry error OR reflect a "
                   f"different underlying mistake, and abs() would be a guess either way")
        df.at[idx, flagcol] = True
    log(f"  {col}: {n_neg} impossible negatives flagged (not corrected)")

# =====================================================================================
# 4.10 OUTLIER INVESTIGATION (decimal-typo detection)
# =====================================================================================
log("\n--- 4.10 Outlier investigation (decimal-typo detection) ---")

def investigate_outliers(col, sign_flag_col):
    valid = df[(df[sign_flag_col] == False) & df[col].notna()]
    median = valid[col].median()
    log(f"\n  Column: {col}  (median over non-null, non-sign-flagged values = {median:.4f})")
    if median <= 0:
        log(f"  median <= 0 -- ratio-to-median is meaningless, skipping 4.10 for this column.")
        return
    candidates = valid[valid[col] > 10 * median]
    log(f"  Candidates (> 10x median = {10*median:.2f}): {len(candidates)}")
    n_corrected = 0
    corrected_rows = []
    for idx in candidates.index:
        v = df.at[idx, col]
        src_row = df.at[idx, "__source_row"]
        applied = None
        for d in (10, 100, 1000):
            cand_val = v / d
            if 0.5 * median <= cand_val <= 2 * median:
                applied = d
                break
        if applied is not None:
            level = "WARNING" if applied == 1000 else "INFO"
            reason = (f"value/{applied} = {v/applied:.2f} lands in plausible band "
                      f"[{0.5*median:.2f}, {2*median:.2f}] around median {median:.2f}; "
                      f"classified LIKELY_DECIMAL_TYPO ({level})")
            log_change(4.10, col, src_row, "OUTLIER_DECIMAL_TYPO_CORRECTED", v, v / applied, reason)
            corrected_rows.append((src_row, v, v / applied, applied))
            df.at[idx, col] = v / applied
            n_corrected += 1
        else:
            log_change(4.10, col, src_row, "OUTLIER_FLAGGED", v, v,
                       f"no divisor (10/100/1000) lands the value in the plausible band around "
                       f"median {median:.2f}; classified STATISTICAL_OUTLIER, left untouched")
            df.at[idx, f"{col}_outlier_flag"] = True

    repair_rate = n_corrected / len(valid) if len(valid) else 0
    log(f"  Corrected as decimal typos: {n_corrected} ({repair_rate*100:.2f}% of {len(valid)} valid values)")
    if repair_rate > 0.01:
        log(f"  *** SANITY-CHECK TRIP: repair rate {repair_rate*100:.2f}% > 1% cap. ***")
        log(f"  Reverting all {n_corrected} corrections on this column -- reinterpreting them as a")
        log(f"  scale/segment finding (e.g. a genuine bulk-order cluster) rather than typos.")
        for src_row, orig_v, new_v, applied in corrected_rows:
            # revert: find the row by src_row and restore
            ridx = df.index[df["__source_row"] == src_row][0]
            df.at[ridx, col] = orig_v
            df.at[ridx, f"{col}_outlier_flag"] = True
            log_change(4.10, col, src_row, "OUTLIER_FLAGGED", orig_v, orig_v,
                       "REVERTED decimal-typo correction: column-wide repair rate exceeded the 1% "
                       "sanity cap, indicating a real scale/segment cluster, not typos. Classified "
                       "STATISTICAL_OUTLIER instead.")
        n_corrected = 0
    before_median, before_q1, before_q3 = median, valid[col].quantile(.25), valid[col].quantile(.75)
    after_valid = df[(df[sign_flag_col] == False) & df[col].notna()]
    after_median = after_valid[col].median()
    after_q1, after_q3 = after_valid[col].quantile(.25), after_valid[col].quantile(.75)
    log(f"  Median before: {before_median:.4f}  after: {after_median:.4f}  "
        f"(delta {abs(after_median-before_median)/before_median*100:.3f}%)")
    log(f"  IQR before: {before_q3-before_q1:.4f}  after: {after_q3-after_q1:.4f}")

for col in ["unit_price", "units_sold"]:
    if f"{col}_outlier_flag" not in df.columns:
        df[f"{col}_outlier_flag"] = False
    investigate_outliers(col, f"{col}_sign_flag")
    df[f"{col}_outlier_flag"] = df[f"{col}_outlier_flag"].fillna(False)

log("\n  total_revenue: deliberately NOT run through the self-referential 4.10 divisor test.")
log("  Per feedback-outlier-judgment (incident 2), a self-referential median/divisor test on a")
log("  column that has an INDEPENDENT cross-check available (here: units_sold * unit_price) is")
log("  the wrong tool -- it can be fooled by coincidence. total_revenue is cross-checked against")
log("  revenue_calculated instead (business_rules.BR1), below, and never divisor-corrected.")

# non-integer units_sold flag (BR6) -- flag, do not round, keep float64
df["units_sold_non_integer_flag"] = False
non_int_mask = df["units_sold"].notna() & (df["units_sold"] % 1 != 0)
for idx in df.index[non_int_mask]:
    src_row = df.at[idx, "__source_row"]
    log_change(4.10, "units_sold", src_row, "OUTLIER_FLAGGED", df.at[idx, "units_sold"], df.at[idx, "units_sold"],
               "non-integer unit count (business_rules.BR6): flagged, NOT rounded -- rounding would "
               "guess which side of .5 the true count was on; column kept float64")
    df.at[idx, "units_sold_non_integer_flag"] = True
log(f"\n  units_sold non-integer values flagged (not rounded): {int(non_int_mask.sum())}")

# =====================================================================================
# BR1 CROSS-COLUMN CHECK: total_revenue vs units_sold * unit_price
# =====================================================================================
log("\n--- Cross-column check (business_rules.BR1): total_revenue vs units_sold * unit_price ---")
df["revenue_calculated"] = df["units_sold"] * df["unit_price"]
df["revenue_mismatch_flag"] = False
both_present = df["total_revenue"].notna() & df["revenue_calculated"].notna()
tol = 0.01  # 1% relative tolerance, absorbs float rounding already present in the source data
diff = (df["total_revenue"] - df["revenue_calculated"]).abs()
rel_diff = diff / df["revenue_calculated"].replace(0, np.nan).abs()
mismatch_mask = both_present & (rel_diff > tol) & (~df["total_revenue_sign_flag"]) & (~df["unit_price_sign_flag"])
n_mismatch = int(mismatch_mask.sum())
n_comparable = int(both_present.sum())
df.loc[mismatch_mask, "revenue_mismatch_flag"] = True
log(f"  Rows with both total_revenue and revenue_calculated present (comparable): {n_comparable}")
log(f"  Rows disagreeing by more than {tol*100:.0f}%: {n_mismatch} "
    f"({n_mismatch/n_comparable*100:.2f}% of comparable rows)" if n_comparable else "  n/a")
if n_mismatch:
    mm = df.loc[mismatch_mask, ["__source_row", "total_revenue", "revenue_calculated"]].copy()
    mm["ratio"] = mm["total_revenue"] / mm["revenue_calculated"]
    log("  Ratio distribution of mismatches (total_revenue / revenue_calculated):")
    log("    " + mm["ratio"].describe().to_string().replace("\n", "\n    "))
    near_clean_ratios = mm["ratio"].apply(lambda r: min(abs(r-100), abs(r-50), abs(r-0.1), abs(r-0.01), abs(r-10)) < 0.5)
    log(f"  Mismatches clustering at a clean scalar multiple (~100x/50x/10x/0.1x/0.01x): "
        f"{int(near_clean_ratios.sum())} / {n_mismatch}")
    log("  DECISION: total_revenue is NOT recomputed/overwritten. Which of the three fields is")
    log("  actually wrong cannot be determined from this data alone (BR1). revenue_mismatch_flag")
    log("  marks every disagreeing row; revenue_calculated is retained as a derived column so any")
    log("  downstream consumer can compare both without the pipeline having guessed a winner.")
    for _, r in mm.head(20).iterrows():
        log(f"    source_row={int(r['__source_row'])}: total_revenue={r['total_revenue']:.2f}  "
            f"revenue_calculated={r['revenue_calculated']:.2f}  ratio={r['ratio']:.4f}")
    for idx in df.index[mismatch_mask]:
        src_row = df.at[idx, "__source_row"]
        log_change("BR1", "total_revenue", src_row, "OUTLIER_FLAGGED",
                   df.at[idx, "total_revenue"], df.at[idx, "total_revenue"],
                   f"revenue_mismatch: total_revenue != units_sold*unit_price beyond {tol*100:.0f}% "
                   f"tolerance (calculated={df.at[idx,'revenue_calculated']:.2f}); flagged, NOT corrected")

# =====================================================================================
# 4.11 DUPLICATE REMOVAL
# =====================================================================================
log("\n--- 4.11 Duplicate removal ---")
compare_cols = [c for c in df.columns if c != "__source_row" and not c.endswith("_flag")]
before_n = len(df)

dup_mask_exact = df[compare_cols].duplicated(keep="first")
exact_dup_rows = df.loc[dup_mask_exact, "__source_row"].tolist()
for idx in df.index[dup_mask_exact]:
    src_row = df.at[idx, "__source_row"]
    log_change(4.11, "ALL", src_row, "DUPLICATE_REMOVED", "(full row)", "(removed)",
               "exact duplicate of an earlier row across every non-flag column after full "
               "normalization (4.1-4.10); first occurrence kept")
df_dedup = df.loc[~dup_mask_exact].copy()
n_exact_removed = len(exact_dup_rows)
log(f"  Exact post-normalization duplicate rows removed: {n_exact_removed}")

# PK-conflict exception: same order_id, EVERY other compare_col identical, differs only in
# customer_name capitalization -> mechanical removal, logged, not a guess.
near_dup_flag_rows = []
pk_conflict_removed = []
other_cols = [c for c in compare_cols if c not in ("order_id", "customer_name")]
for oid, grp in df_dedup.groupby(df_dedup["order_id"].astype(str)):
    if len(grp) < 2:
        continue
    # identical on every column except customer_name?
    same_other = grp[other_cols].astype(str).apply(lambda col: col.nunique(dropna=False) == 1).all()
    names_lower = grp["customer_name"].astype(str).str.lower()
    same_when_lowered = names_lower.nunique(dropna=False) == 1
    diff_case_only = names_lower.astype(str).ne(grp["customer_name"].astype(str)).any() or grp["customer_name"].nunique(dropna=False) > 1
    if same_other and same_when_lowered and grp["customer_name"].nunique(dropna=False) > 1:
        keep_idx = grp.index[0]
        drop_idx = grp.index[1:]
        for di in drop_idx:
            src_row = df_dedup.at[di, "__source_row"]
            log_change(4.11, "ALL", src_row, "DUPLICATE_REMOVED", "(full row)", "(removed)",
                       f"same order_id ({oid}) as source_row {df_dedup.at[keep_idx,'__source_row']}, "
                       f"every column identical except customer_name capitalization ("
                       f"{df_dedup.at[keep_idx,'customer_name']!r} vs {df_dedup.at[di,'customer_name']!r}) "
                       f"-- symmetric evidence of a formatting-only duplicate, not a real conflict "
                       f"(spec 4.11 clear primary-key-conflict exception)")
            pk_conflict_removed.append(src_row)
        df_dedup = df_dedup.drop(index=drop_idx)
    elif not same_other and len(grp) > 1:
        for di in grp.index:
            src_row = df_dedup.at[di, "__source_row"]
            log_change(4.11, "order_id", src_row, "NEAR_DUPLICATE_FLAGGED", oid, oid,
                       f"order_id {oid} repeats across {len(grp)} rows with at least one other "
                       f"column genuinely differing (not just case/whitespace) -- flagged for "
                       f"human review, NOT auto-deleted; no clear primary-key-conflict resolution exists")
            near_dup_flag_rows.append(src_row)

df_dedup["near_duplicate_flag"] = df_dedup["__source_row"].isin(near_dup_flag_rows)
log(f"  PK-conflict (customer_name-case-only) rows removed: {len(pk_conflict_removed)}")
log(f"  Rows flagged NEAR_DUPLICATE_FLAGGED (order_id repeats, real conflict, kept for review): {len(near_dup_flag_rows)}")

df = df_dedup.reset_index(drop=True)
after_n = len(df)
log(f"\n  Row count: {before_n} -> {after_n} ({before_n-after_n} removed total)")

# =====================================================================================
# WRITE OUTPUTS
# =====================================================================================
bool_flag_cols = [c for c in df.columns if c.endswith("_flag")]
for c in bool_flag_cols:
    df[c] = df[c].fillna(False).astype(bool)

log("\n--- Flag registry (materialized boolean columns) ---")
for c in sorted(bool_flag_cols):
    log(f"  {c}: True count = {int(df[c].sum())}")

df.to_csv(CLEANED_CSV, index=False, encoding="utf-8")
log(f"\n[WROTE] {CLEANED_CSV}  shape={df.shape}")

chg_df = pd.DataFrame(changes, columns=["STAGE", "COLUMN", "SOURCE_ROW", "CHANGE_TYPE",
                                         "ORIGINAL_VALUE", "NEW_VALUE", "REASON"])
chg_df.to_csv(CHANGELOG_CSV, index=False, encoding="utf-8")
log(f"[WROTE] {CHANGELOG_CSV}  rows={len(chg_df)}")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(rpt) + "\n")
print(f"[WROTE] {REPORT}")
print(("\n".join(rpt[-80:])).encode("ascii", errors="replace").decode("ascii"))
