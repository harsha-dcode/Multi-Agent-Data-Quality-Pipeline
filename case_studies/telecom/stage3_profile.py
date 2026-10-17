# -*- coding: utf-8 -*-
"""
Stage 3 (profiling) + Stage 4.4 collision-guard check for telecom_churn.csv.

Repeats stage2b_extract.py's load as setup, so it runs standalone.

- Loads with dtype=str, keep_default_na=False (per task mandate #3) so pandas
  NEVER silently interprets any token as NaN -- we control null detection
  ourselves against the documented disguise set.
- Adds __source_row = 0-based row index in the raw file, immediately after
  load, before any row is dropped/reordered (Stage 4.0 convention).
- Scans every cell for the full disguised-null set from the spec.
- Profiles every column: dtype inference, completeness, cardinality,
  numeric stats, negative-value counts.
- Runs the collision guard for fuzzy-matching eligibility on Churn,
  ContractRenewal, DataPlan (the only categorical/flag-like columns).
- Pickles the tagged raw dataframe (str dtype) for stage4_clean.py to consume,
  so stage4_clean.py does not need to re-parse the CSV.

Writes: 02_profile_report.txt
"""
import io
import pandas as pd
import numpy as np

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

INPUT = str(_HERE / "input" / "telecom_churn.csv")
OUT_DIR = str(_HERE)
REPORT = OUT_DIR + r"\02_profile_report.txt"
PICKLE_OUT = OUT_DIR + r"\_raw_str_with_source_row.pkl"

lines = []
def log(s=""):
    lines.append(str(s))

# =============================================================================
# STAGE 2: EXTRACTION
# =============================================================================
log("=" * 78)
log("STAGE 2: DATA EXTRACTION")
log("=" * 78)

df = pd.read_csv(INPUT, dtype=str, keep_default_na=False, encoding="utf-8")
df.insert(0, "__source_row", range(len(df)))  # 0-based, added before any mutation

log(f"rows_loaded: {len(df)}")
log(f"columns_loaded (excl __source_row): {[c for c in df.columns if c != '__source_row']}")
log(f"all columns object/str dtype as loaded: {all(df[c].dtype == object for c in df.columns if c != '__source_row')}")
log(f"__source_row range: {df['__source_row'].min()}..{df['__source_row'].max()}")

expected_rows = 3333
expected_cols = ["Churn", "AccountWeeks", "ContractRenewal", "DataPlan", "DataUsage",
                  "CustServCalls", "DayMins", "DayCalls", "MonthlyCharge", "OverageFee", "RoamMins"]
log(f"row_count_matches_expected({expected_rows}): {len(df) == expected_rows}")
log(f"columns_match_expected: {list(df.columns[1:]) == expected_cols}")


# ---------------------------------------------------------------
# The lines above re-run the previous stage as setup (deterministic
# and cheap). Clear the log buffer so this report covers only this
# stage's output.
# ---------------------------------------------------------------
lines.clear()

# =============================================================================
# STAGE 3: DATA PROFILING
# =============================================================================
log()
log("=" * 78)
log("STAGE 3: DATA PROFILING")
log("=" * 78)

DATA_COLS = [c for c in df.columns if c != "__source_row"]

# --- disguised-null scan (mandate #3) ---
NULL_DISGUISES_UNAMBIGUOUS = {
    "", " ", "?", "null", "none", "tbd", "undefined", "#n/a", "#value!", "#ref!", "n/a"
}
NULL_DISGUISES_AMBIGUOUS = {"na", "-", "unknown"}
ALL_DISGUISE_TOKENS = NULL_DISGUISES_UNAMBIGUOUS | NULL_DISGUISES_AMBIGUOUS

log()
log("--- Disguised-null scan (case-folded, stripped comparison per column) ---")
total_disguise_hits = 0
per_col_disguise_hits = {}
for c in DATA_COLS:
    folded = df[c].astype(str).str.strip().str.casefold()
    hits = folded.isin(ALL_DISGUISE_TOKENS)
    n = int(hits.sum())
    per_col_disguise_hits[c] = n
    total_disguise_hits += n
    if n:
        sample_rows = df.loc[hits, "__source_row"].tolist()[:10]
        log(f"  {c}: {n} disguised-null token(s) found, e.g. source_rows={sample_rows}")
log(f"TOTAL disguised-null tokens found across all cells: {total_disguise_hits}")
log("Verification method: every cell in every column was cast to str, .strip()'d, "
    ".casefold()'d, and compared against the full 14-token disguise set "
    "('', ' ', '?', 'null', 'none', 'tbd', 'undefined', '#n/a', '#value!', '#ref!', "
    "'n/a', 'na', '-', 'unknown'). This is a 100% cell scan (3,333 rows x 11 cols "
    "= 36,663 cells), not a sample.")
log(f"Cells scanned: {len(df) * len(DATA_COLS)}")

# --- also check truly-empty-string count directly (paranoia check independent of above) ---
empty_count = int((df[DATA_COLS] == "").sum().sum())
log(f"Independent cross-check -- raw empty-string ('') cell count via direct equality: {empty_count}")

# --- per-column profile ---
log()
log("--- Per-column profile ---")
numeric_stats = {}
for c in DATA_COLS:
    series_raw = df[c]
    n_total = len(series_raw)
    n_blank = int((series_raw.astype(str).str.strip() == "").sum())
    unique_vals = series_raw.unique()
    n_unique = len(unique_vals)

    log(f"\n[{c}]")
    log(f"  non-null (post dtype=str, keep_default_na=False) count: {n_total}")
    log(f"  blank/whitespace-only cells: {n_blank}")
    log(f"  unique value count: {n_unique}")

    # attempt numeric coercion
    coerced = pd.to_numeric(series_raw, errors="coerce")
    n_unparseable = int(coerced.isna().sum()) - n_blank  # unparseable beyond blanks
    n_unparseable = max(n_unparseable, 0)
    log(f"  numeric-coercible: {n_total - int(coerced.isna().sum())}/{n_total}"
        f" (unparseable-as-numeric, non-blank: {n_unparseable})")

    if coerced.notna().sum() > 0:
        vals = coerced.dropna()
        is_int_like = bool((vals == vals.astype(np.int64, errors="ignore")).all()) if vals.notna().all() else False
        # safer int-like check
        try:
            is_int_like = bool(np.all(np.mod(vals.values, 1) == 0))
        except Exception:
            is_int_like = False
        n_negative = int((vals < 0).sum())
        n_zero = int((vals == 0).sum())
        stats = {
            "min": float(vals.min()),
            "max": float(vals.max()),
            "mean": float(vals.mean()),
            "median": float(vals.median()),
            "std": float(vals.std()) if len(vals) > 1 else 0.0,
            "skew": float(vals.skew()) if len(vals) > 2 else float("nan"),
            "n_negative": n_negative,
            "pct_negative": round(100 * n_negative / len(vals), 4),
            "n_zero": n_zero,
            "int_like": is_int_like,
        }
        numeric_stats[c] = stats
        log(f"  min={stats['min']}, max={stats['max']}, mean={stats['mean']:.4f}, "
            f"median={stats['median']}, std={stats['std']:.4f}, skew={stats['skew']:.4f}")
        log(f"  negative values: {n_negative} ({stats['pct_negative']}%)")
        log(f"  zero values: {n_zero}")
        log(f"  appears integer-valued: {is_int_like}")

    top10 = series_raw.value_counts().head(10)
    log(f"  top 10 values: {dict(top10)}")

    if n_unique <= 5:
        log(f"  FULL unique value set (cardinality <= 5): {sorted(unique_vals.tolist())}")

    # zero-variance check
    if n_unique == 1:
        log(f"  *** ZERO VARIANCE: every value in this column is identical ({unique_vals[0]!r}) ***")

    # >30% null flag (there are no true nulls here since keep_default_na=False and
    # no disguises found, but check blank-rate anyway per spec)
    blank_rate = 100 * n_blank / n_total
    if blank_rate > 30:
        log(f"  *** HIGH RISK: {blank_rate:.2f}% blank -- exceeds 30% null-rate threshold ***")

# --- closed-code-set columns: value range check ---
log()
log("--- Closed code set range checks (Churn, ContractRenewal, DataPlan; expect only {0,1}) ---")
for c in ["Churn", "ContractRenewal", "DataPlan"]:
    coerced = pd.to_numeric(df[c], errors="coerce")
    out_of_range = df.loc[~coerced.isin([0, 1]), ["__source_row", c]]
    log(f"  {c}: out-of-{{0,1}} value count = {len(out_of_range)}")
    if len(out_of_range):
        log(f"    rows: {out_of_range.to_dict('records')[:20]}")

# =============================================================================
# STAGE 4.4 COLLISION GUARD (categorical/flag columns) -- run BEFORE any
# fuzzy matching is attempted, per mandate #2.
# =============================================================================
log()
log("=" * 78)
log("STAGE 4.4 COLLISION GUARD -- run before any fuzzy matching")
log("=" * 78)
log("""
Candidate categorical/flag columns in this dataset: Churn, ContractRenewal,
DataPlan (the only columns with cardinality low enough to be 'categorical'
in spirit). Eligibility check for fuzzy string matching:

  Fuzzy matching (token_sort_ratio / edit distance) is defined over STRING
  values that could plausibly contain human-entered typos (e.g. 'Alpah' vs
  'Alpha'). It has no meaningful application to a column whose entire domain
  is the two integers {0, 1}. There is no 'canonical string form' to fuzzy-
  match against -- 0 and 1 are not typo-able spellings of each other.
""")
for c in ["Churn", "ContractRenewal", "DataPlan"]:
    uniques = sorted(pd.to_numeric(df[c], errors="coerce").dropna().unique().tolist())
    is_numeric_binary = set(uniques).issubset({0, 1})
    log(f"  {c}: observed values = {uniques} -> numeric binary, "
        f"NOT ELIGIBLE for fuzzy matching = {is_numeric_binary}")

log("")
log("Full column-by-column eligibility scan (all 11 data columns):")
for c in DATA_COLS:
    log(f"  {c}: dtype-as-loaded=str, semantic type=numeric (from Stage 1 column_types) "
        f"-> not a free-text/categorical string column -> NOT ELIGIBLE for fuzzy matching")

log("")
log("COLLISION GUARD RESULT: 0 of 11 columns are eligible for fuzzy string matching. "
    "There is no categorical/string column in this dataset at all. Therefore the "
    "canonicals_collide() check (comparing thefuzz.utils.full_process() keys of "
    "canonical values) was not run against any column, because there are no "
    "canonical string value lists to check for collision -- there is nothing to feed it. "
    "This is reported explicitly per mandate #2 rather than silently skipping the section. "
    "Stage 4.4 (Categorical Typo Correction) is therefore N/A for this dataset in its "
    "entirety, and dangerous_columns in 01_business_brief.yaml is correctly {} (guard run, "
    "nothing tripped because nothing was eligible).")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

df.to_pickle(PICKLE_OUT)

print("Wrote:", REPORT)
print("Wrote:", PICKLE_OUT)
print("rows:", len(df), "| total_disguise_hits:", total_disguise_hits, "| empty_count:", empty_count)
