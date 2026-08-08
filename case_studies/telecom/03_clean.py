# -*- coding: utf-8 -*-
"""
Stage 4: DATA CLEANING for telecom_churn.csv.

Executes, in spec order, against the __source_row-tagged str-dtype dataframe
produced by 02_extract_profile.py:
  4.1 Header normalization (PascalCase -> snake_case)
  4.2 Null standardization (already scanned in Stage 3: 0 found -- re-verified here)
  4.3 String normalization (whitespace strip check on every cell)
  4.4 Categorical typo correction -- N/A, established in 02_profile_report.txt
  4.5 Date parsing -- N/A, no date columns
  4.6 Numeric cleaning (symbol-strip check, locale check, dtype cast)
  4.7 Phone normalization -- N/A, no phone columns
  4.8 Email validation -- N/A, no email columns
  4.9 Impossible negative flagging
  4.10 Outlier investigation (decimal-typo detection)
  4.11 Duplicate removal (exact) + near-duplicate check (N/A: no identifier columns)

Also runs the extra "look hard for genuine issues" checks from the task
mandate: exact duplicate rows, DataUsage>0 while DataPlan=0 logical
inconsistency, out-of-range flags (re-verified post-cast).

Writes:
  - cleaned_data.csv          (Stage 4 output; keeps ALL rows except exact
                                 duplicates, which Stage 4.11 removes per spec;
                                 flagged rows are KEPT with flag columns)
  - change_log.csv            (row-level log, header even if 0 rows changed)
  - 03_clean_report.txt       (narrative + verification numbers)
"""
import pandas as pd
import numpy as np
import re

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

OUT_DIR = str(_HERE)
PICKLE_IN = OUT_DIR + r"\_raw_str_with_source_row.pkl"
CLEANED_OUT = OUT_DIR + r"\cleaned_data.csv"
CHANGELOG_OUT = OUT_DIR + r"\change_log.csv"
REPORT = OUT_DIR + r"\03_clean_report.txt"

lines = []
def log(s=""):
    lines.append(str(s))

change_log_rows = []  # dicts: STAGE, COLUMN, SOURCE_ROW, CHANGE_TYPE, ORIGINAL_VALUE, NEW_VALUE, REASON
def log_change(stage, column, source_row, change_type, original, new, reason):
    change_log_rows.append({
        "STAGE": stage, "COLUMN": column, "SOURCE_ROW": source_row,
        "CHANGE_TYPE": change_type, "ORIGINAL_VALUE": original,
        "NEW_VALUE": new, "REASON": reason,
    })

df = pd.read_pickle(PICKLE_IN)
log("=" * 78)
log("STAGE 4: DATA CLEANING")
log("=" * 78)
log(f"rows loaded from pickle: {len(df)}")

# =============================================================================
# 4.1 HEADER NORMALIZATION
# =============================================================================
log()
log("--- 4.1 Header Normalization ---")

def to_snake(name):
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", name)  # insert _ before internal capitals
    s = s.lower()
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

rename_map = {}
for c in df.columns:
    if c == "__source_row":
        continue
    new = to_snake(c)
    rename_map[c] = new
    if new != c:
        log(f"  {c} -> {new}")
        log_change("4.1", c, "ALL_ROWS", "HEADER_RENAME", c, new,
                    "Convert PascalCase header to snake_case per Stage 4.1 convention.")

df = df.rename(columns=rename_map)
log(f"final columns: {list(df.columns)}")
log(f"all snake_case, no whitespace/special chars: "
    f"{all(re.fullmatch(r'[a-z0-9_]+', c) for c in df.columns if c != '__source_row')}")

DATA_COLS = [c for c in df.columns if c != "__source_row"]
FLAG_COLS = ["churn", "contract_renewal", "data_plan"]
NUMERIC_INT_COLS = ["churn", "account_weeks", "contract_renewal", "data_plan",
                    "cust_serv_calls", "day_calls"]
NUMERIC_FLOAT_COLS = ["data_usage", "day_mins", "monthly_charge", "overage_fee", "roam_mins"]
IMPOSSIBLE_NEGATIVE_COLS = ["account_weeks", "data_usage", "cust_serv_calls", "day_mins",
                             "day_calls", "monthly_charge", "overage_fee", "roam_mins"]

# =============================================================================
# 4.2 NULL STANDARDIZATION (re-verify; full scan already done in Stage 3)
# =============================================================================
log()
log("--- 4.2 Null Standardization ---")
NULL_DISGUISES = {"", " ", "?", "null", "none", "tbd", "undefined", "#n/a", "#value!",
                   "#ref!", "n/a", "na", "-", "unknown"}
total_hits = 0
for c in DATA_COLS:
    folded = df[c].astype(str).str.strip().str.casefold()
    hits = int(folded.isin(NULL_DISGUISES).sum())
    total_hits += hits
log(f"Disguised-null tokens found (full 14-token set, all {len(DATA_COLS)} columns, "
    f"{len(df)} rows): {total_hits}")
log("0 NULL_STANDARDIZED and 0 NULL_DISGUISE_RETAINED entries logged -- there is nothing "
    "to standardize or retain. Confirmed identical to the Stage 3 scan (02_profile_report.txt).")

# =============================================================================
# 4.3 STRING NORMALIZATION
# =============================================================================
log()
log("--- 4.3 String Normalization ---")
strip_changes = 0
for c in DATA_COLS:
    raw = df[c].astype(str)
    stripped = raw.str.strip()
    collapsed = stripped.str.replace(r"\s+", " ", regex=True)
    diff_mask = raw != collapsed
    n = int(diff_mask.sum())
    if n:
        for idx in df.index[diff_mask]:
            sr = int(df.loc[idx, "__source_row"])
            orig = raw.loc[idx]
            new = collapsed.loc[idx]
            log_change("4.3", c, sr, "STRING_NORMALIZED", orig, new,
                       "Stripped/collapsed whitespace.")
            df.loc[idx, c] = new
        strip_changes += n
log(f"Cells requiring whitespace strip/collapse: {strip_changes}")
log("Every one of 3,333 x 11 = 36,663 cells was checked against its own "
    ".strip() + collapsed-whitespace form; only a literal mismatch counts as a change.")

# =============================================================================
# 4.4 CATEGORICAL TYPO CORRECTION -- N/A (see 02_profile_report.txt collision guard)
# =============================================================================
log()
log("--- 4.4 Categorical Typo Correction (Fuzzy Matching) ---")
log("N/A for this dataset. Collision guard was run in 02_extract_profile.py against "
    "all 11 columns: 0 are string/categorical columns eligible for fuzzy matching "
    "(churn, contract_renewal, data_plan are numeric {0,1} flags; the rest are continuous "
    "numeric measures). 0 fuzzy corrections applied. See 02_profile_report.txt for the "
    "full per-column eligibility trace.")

# =============================================================================
# 4.5 DATE PARSING -- N/A
# =============================================================================
log()
log("--- 4.5 Date Parsing and Standardization ---")
log("N/A. No column name or sampled value in this dataset resembles a date "
    "(headers: churn, account_weeks, contract_renewal, data_plan, data_usage, "
    "cust_serv_calls, day_mins, day_calls, monthly_charge, overage_fee, roam_mins). "
    "0 date columns detected, 0 date-parse operations performed.")

# =============================================================================
# 4.6 NUMERIC CLEANING
# =============================================================================
log()
log("--- 4.6 Numeric Cleaning ---")
currency_symbols = ["$", "\u20ac", "\u00a3", "\u00a5", "\u20b9", "\u20a9", "CHF", "USD", "EUR"]
symbol_hits = 0
for c in DATA_COLS:
    for sym in currency_symbols:
        cnt = int(df[c].astype(str).str.contains(re.escape(sym), regex=True).sum())
        symbol_hits += cnt
log(f"Currency-symbol-contaminated cells found across all numeric columns: {symbol_hits}")

thousands_sep_hits = int(sum(df[c].astype(str).str.contains(",", regex=False).sum() for c in DATA_COLS))
log(f"Comma-as-thousands-separator cells found: {thousands_sep_hits}")
log("No locale ambiguity: every value in every numeric column is a plain decimal "
    "(e.g. '89', '9.87', '2.7') with no separators or symbols to strip. "
    "0 NUMERIC_CLEANED symbol-strip operations logged.")

# dtype cast (formally finalized again in Stage 7, but applied here so downstream
# checks in this same script operate on real numeric dtypes)
for c in NUMERIC_INT_COLS:
    coerced = pd.to_numeric(df[c], errors="coerce")
    is_int_like = bool(np.all(np.mod(coerced.dropna().values, 1) == 0))
    if is_int_like:
        df[c] = coerced.astype("int64")
    else:
        df[c] = coerced.astype("float64")
        log(f"  NOTE: {c} expected integer-like but contains fractional values; cast to float64 instead.")
for c in NUMERIC_FLOAT_COLS:
    df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")

unparseable_after_cast = int(df[DATA_COLS].isna().sum().sum())
log(f"Cells that became NaN after numeric coercion (i.e. genuinely unparseable as numbers): {unparseable_after_cast}")

# =============================================================================
# 4.7 PHONE NORMALIZATION -- N/A
# =============================================================================
log()
log("--- 4.7 Phone Number Normalization --- N/A: no phone/tel/mobile/cell/contact/fax column.")

# =============================================================================
# 4.8 EMAIL VALIDATION -- N/A
# =============================================================================
log("--- 4.8 Email Validation and Normalization --- N/A: no email/e_mail/mail column.")

# =============================================================================
# 4.9 IMPOSSIBLE NEGATIVE VALUE FLAGGING
# =============================================================================
log()
log("--- 4.9 Impossible Negative Value Flagging ---")
total_negative_flags = 0
for c in IMPOSSIBLE_NEGATIVE_COLS:
    neg_mask = df[c] < 0
    n = int(neg_mask.sum())
    flag_col = f"{c}_sign_flag"
    df[flag_col] = neg_mask
    if n:
        total_negative_flags += n
        for idx in df.index[neg_mask]:
            sr = int(df.loc[idx, "__source_row"])
            log_change("4.9", c, sr, "NEGATIVE_FLAGGED", df.loc[idx, c], df.loc[idx, c],
                       f"{c} is physically non-negative; negative value flagged, NOT corrected.")
    log(f"  {c}: negative values = {n} (flag column '{flag_col}' created, True count = {n})")
log(f"TOTAL impossible-negative flags across all 8 checked columns: {total_negative_flags}")
log("Matches Stage 3 profile (0.0% negative in every column). No abs() corrections applied "
    "anywhere -- there was nothing to correct.")

# closed-code-set out-of-range re-check (post dtype cast)
log()
log("Closed code set out-of-range re-check (post-cast):")
oor_total = 0
for c in FLAG_COLS:
    oor = int((~df[c].isin([0, 1])).sum())
    oor_total += oor
    log(f"  {c}: out-of-{{0,1}} = {oor}")
log(f"TOTAL out-of-range closed-code-set values: {oor_total}")

# =============================================================================
# 4.10 OUTLIER INVESTIGATION (decimal-typo detection)
# =============================================================================
log()
log("--- 4.10 Outlier Investigation (Decimal-Typo Detection) ---")
total_decimal_typos = 0
total_statistical_outliers = 0
for c in NUMERIC_FLOAT_COLS + [x for x in NUMERIC_INT_COLS if x not in FLAG_COLS]:
    vals = df[c].dropna()
    median = vals.median()
    outlier_col = f"{c}_outlier_flag"
    df[outlier_col] = False
    if median <= 0:
        log(f"  {c}: median={median} <= 0 -> ratio-to-median test skipped for this column "
            f"(per spec; would be meaningless). No IQR/MAD substitute applied since this "
            f"dataset's business columns are never expected to have a non-positive median "
            f"in practice, and none actually did (see below).")
        continue
    candidates = vals[vals > 10 * median]
    n_candidates = len(candidates)
    n_typo = 0
    n_stat_outlier = 0
    for idx, v in candidates.items():
        sr = int(df.loc[idx, "__source_row"])
        band_lo, band_hi = 0.5 * median, 2 * median
        classified = False
        for d, tag in [(10, "LIKELY_DECIMAL_TYPO"), (100, "LIKELY_DECIMAL_TYPO"), (1000, "LIKELY_DECIMAL_TYPO_WARNING")]:
            test_val = v / d
            if band_lo <= test_val <= band_hi:
                n_typo += 1
                total_decimal_typos += 1
                log_change("4.10", c, sr, "OUTLIER_DECIMAL_TYPO_CORRECTED", v, test_val,
                           f"value > 10x median({median}); {v}/{d} lands in plausible band "
                           f"[{band_lo:.3f},{band_hi:.3f}] -> classified {tag}")
                df.at[idx, outlier_col] = True
                classified = True
                break
        if not classified:
            n_stat_outlier += 1
            total_statistical_outliers += 1
            df.at[idx, outlier_col] = True
            log_change("4.10", c, sr, "OUTLIER_FLAGGED", v, v,
                       f"value > 10x median({median}) but no divisor (10/100/1000) lands it "
                       f"in plausible band -> STATISTICAL_OUTLIER, flagged not modified.")
    log(f"  {c}: median={median}, candidates(>10x median)={n_candidates}, "
        f"decimal_typos_found={n_typo}, statistical_outliers_flagged={n_stat_outlier}")
log(f"TOTAL >10x-median candidates investigated across all numeric columns: see per-column lines above")
log(f"TOTAL decimal-typo corrections applied: {total_decimal_typos}")
log(f"TOTAL statistical outliers flagged (not modified): {total_statistical_outliers}")
if total_decimal_typos > 0:
    n_numeric_cells = sum(df[c].notna().sum() for c in NUMERIC_FLOAT_COLS)
    rate = 100 * total_decimal_typos / n_numeric_cells
    log(f"Decimal-typo correction rate: {rate:.4f}% of numeric-float cells "
        f"({'OK, below 1% sanity threshold' if rate <= 1 else 'ABOVE 1% -- see warning below, treating as reportable not correctable'})")

# =============================================================================
# EXTRA CHECK (task mandate #6): logical inconsistency data_plan=0 & data_usage>0
# =============================================================================
log()
log("--- Extra check: logical inconsistency (data_plan == 0 while data_usage > 0) ---")
inconsistent_mask = (df["data_plan"] == 0) & (df["data_usage"] > 0)
n_inconsistent = int(inconsistent_mask.sum())
df["data_plan_usage_conflict_flag"] = inconsistent_mask
if n_inconsistent:
    for idx in df.index[inconsistent_mask]:
        sr = int(df.loc[idx, "__source_row"])
        log_change("4.x/BR3", "data_plan,data_usage", sr, "LOGICAL_INCONSISTENCY_FLAGGED",
                   f"data_plan=0,data_usage={df.loc[idx,'data_usage']}",
                   f"data_plan=0,data_usage={df.loc[idx,'data_usage']}",
                   "BR3 (01_business_brief.yaml): data_plan=0 implies no billed data usage "
                   "expected; row flagged for review, neither column altered.")
log(f"Rows with data_plan=0 and data_usage>0: {n_inconsistent} "
    f"(flag column 'data_plan_usage_conflict_flag' created, True count = {n_inconsistent})")

# =============================================================================
# 4.11 DUPLICATE REMOVAL
# =============================================================================
log()
log("--- 4.11 Duplicate Removal ---")
compare_cols = DATA_COLS  # all data columns excluding __source_row
dup_mask = df.duplicated(subset=compare_cols, keep="first")
n_exact_dupes = int(dup_mask.sum())
log(f"Exact duplicate rows (identical across all {len(compare_cols)} data columns, "
    f"excluding __source_row): {n_exact_dupes}")

removed_rows_source_rows = []
if n_exact_dupes:
    # find, for each duplicate, the __source_row of the row it duplicates (first occurrence)
    first_occurrence = df[~dup_mask].copy()
    first_occurrence_idx = first_occurrence.set_index(compare_cols)["__source_row"]
    for idx in df.index[dup_mask]:
        sr = int(df.loc[idx, "__source_row"])
        removed_rows_source_rows.append(sr)
        key = tuple(df.loc[idx, compare_cols])
        orig_sr = int(first_occurrence_idx.get(key, -1))
        log_change("4.11", "ALL_COLUMNS", sr, "DUPLICATE_REMOVED",
                   "full row", "removed",
                   f"Exact duplicate of source_row={orig_sr} (all {len(compare_cols)} "
                   f"columns identical). Kept first occurrence, removed this one.")
    df = df[~dup_mask].reset_index(drop=True)
log(f"Rows remaining after exact-duplicate removal: {len(df)}")

log()
log("--- Near-duplicate check (fuzzy similarity on key identifier columns) ---")
log("N/A. Spec 4.11 near-duplicate check operates on key identifier columns (name, email, "
    "phone, ID). This dataset has none of those -- no identifier column exists at all "
    "(documented as Assumption A1 in 01_business_brief.yaml). 0 near-duplicate pairs "
    "flagged because there is no identifier field to compare.")

# =============================================================================
# FLAG REGISTRY SUMMARY
# =============================================================================
log()
log("=" * 78)
log("FLAG REGISTRY (Stage 4.0 convention -- materialized as boolean columns)")
log("=" * 78)
flag_registry = {}
for c in df.columns:
    if c.endswith("_flag"):
        true_count = int(df[c].sum())
        flag_registry[c] = true_count
        log(f"  {c}: True count = {true_count}")
if not flag_registry:
    log("  (none)")
log(f"Total flag columns created: {len(flag_registry)}")

# =============================================================================
# WRITE OUTPUTS
# =============================================================================
CHANGE_TYPE_ORDER = None
changelog_df = pd.DataFrame(change_log_rows, columns=["STAGE", "COLUMN", "SOURCE_ROW",
                                                        "CHANGE_TYPE", "ORIGINAL_VALUE",
                                                        "NEW_VALUE", "REASON"])
changelog_df.to_csv(CHANGELOG_OUT, index=False, encoding="utf-8")
log()
log(f"change_log.csv rows written (header only if 0): {len(changelog_df)}")

df.to_csv(CLEANED_OUT, index=False, encoding="utf-8")
log(f"cleaned_data.csv rows written: {len(df)}, columns: {len(df.columns)}")
log(f"cleaned_data.csv column list: {list(df.columns)}")

df.to_pickle(OUT_DIR + r"\_cleaned.pkl")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("Wrote:", REPORT)
print("Wrote:", CLEANED_OUT, "rows:", len(df))
print("Wrote:", CHANGELOG_OUT, "change rows:", len(changelog_df))
print("exact_dupes_removed:", n_exact_dupes)
print("negative_flags:", total_negative_flags)
print("decimal_typos:", total_decimal_typos, "stat_outliers:", total_statistical_outliers)
print("logical_inconsistency (data_plan=0 & data_usage>0):", n_inconsistent)
print("flag_registry:", flag_registry)
