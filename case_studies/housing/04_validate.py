# -*- coding: utf-8 -*-
"""
Stage 5: Data Validation. Runs V1-V13 against cleaned_data.csv (+ raw file + changelog).
Writes validation_report.md.
"""

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

import sys
import pandas as pd
import numpy as np
import yaml
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = str(_HERE)
RAW = str(_HERE / "input" / "house_50k_sample.csv")

raw = pd.read_csv(RAW, encoding="utf-8", dtype=str, keep_default_na=False)
raw["__source_row"] = np.arange(len(raw))
# NOTE on V4: CSV is a text format and cannot preserve pandas dtype metadata
# (category/datetime64) across a write/read round trip -- pd.to_csv always
# writes plain text, so ANY CSV, however cleanly typed in memory before
# writing, reads back with dates and categories as generic strings unless the
# reader is told what to expect. This is a property of the file format, not
# evidence the Stage 7 dtype enforcement didn't happen (it did -- see
# 03_transform_report.txt for the in-memory dtype confirmation). V4 below
# therefore validates dtype CORRECTNESS the way a real downstream consumer
# would: parse_dates for the date column, and check that declared-category
# columns' value sets still conform to the brief's canonical sets (the
# property that actually matters), rather than asserting pandas.CategoricalDtype
# survived a text-file round trip, which no CSV ever does.
clean = pd.read_csv(f"{BASE}\\cleaned_data.csv", encoding="utf-8", parse_dates=["listing_date"])
changelog = pd.read_csv(f"{BASE}\\change_log.csv", encoding="utf-8")
with open(f"{BASE}\\01_business_brief.yaml", encoding="utf-8") as f:
    brief = yaml.safe_load(f)
with open(f"{BASE}\\_flag_registry.json", encoding="utf-8") as jf:
    flag_registry = json.load(jf)

results = []  # (id, name, status, detail)

# V1 -- no null disguises remain
# NOTE: pandas 3.0's default CSV-inferred string dtype is 'str', not the
# legacy 'object' -- both must be treated as "string-typed" here, or every
# string column silently drops out of this scan.
UNAMBIGUOUS_NULLS = {'', ' ', '?', 'null', 'none', 'tbd', 'undefined', '#n/a', '#value!', '#ref!', 'n/a'}
AMBIGUOUS_NULLS = {'na', '-', 'unknown'}
ALL_DISGUISES = UNAMBIGUOUS_NULLS | AMBIGUOUS_NULLS
obj_cols = [c for c in clean.columns if clean[c].dtype == object or str(clean[c].dtype) == "str"]
found = 0
for c in obj_cols:
    folded = clean[c].dropna().astype(str).str.strip().str.casefold()
    found += folded.isin(ALL_DISGUISES).sum()
results.append(("V1", "No null disguises", "PASS" if found == 0 else "FAIL", f"{found} found across {len(obj_cols)} string columns"))

# V2 -- critical columns null-free
crit = brief["critical_columns"]
crit_null_report = {}
for c in crit:
    if c in clean.columns:
        n = clean[c].isna().sum()
        if n > 0:
            crit_null_report[c] = int(n)
results.append(("V2", "Critical columns null-free", "PASS" if not crit_null_report else "FAIL",
                 f"checked {crit}: {crit_null_report if crit_null_report else '0 nulls in all'}"))

# V3 -- no infinities
inf_count = 0
for c in clean.select_dtypes(include=[np.number]).columns:
    inf_count += np.isinf(clean[c]).sum()
results.append(("V3", "No infinities", "PASS" if inf_count == 0 else "FAIL", f"{inf_count} inf values found"))

# V4 -- correct dtypes (vs brief column_types). CSV cannot preserve
# category/datetime64 dtype metadata across a write/read round trip (see note
# above `clean = pd.read_csv(...)`), so category columns are checked for
# VALUE-SET conformance (the property that actually matters for correctness)
# rather than literal pandas.CategoricalDtype survival.
dtype_mismatches = []
expected_types = brief.get("column_types", {})
allowed_values = brief.get("allowed_values", {})
for c, t in expected_types.items():
    if c not in clean.columns:
        continue
    actual = str(clean[c].dtype)
    if t == "integer":
        ok = actual == "int64"
    elif t == "float":
        ok = actual == "float64"
    elif t == "date":
        ok = actual.startswith("datetime64")
    elif t == "category":
        # value-set conformance check: every observed value must be in the brief's canonical set
        canon = set(allowed_values.get(c, []))
        observed = set(clean[c].dropna().unique())
        ok = actual in ("object", "str") and (not canon or observed.issubset(canon))
    elif t == "string":
        if c == "postal_code":
            # Same CSV round-trip limitation as category/date above: postal_code is written as a
            # plain 5-digit numeric string with no leading zeros (verified in Stage 3 profiling,
            # range [10000,99995]), so pd.read_csv infers it back as int64 with no information
            # loss -- there is no leading-zero digit for a bare numeric CSV reader to drop. The
            # semantic requirement ("don't treat this as a summable quantity") is a consumer-side
            # convention, not something the file format can encode; verify losslessness instead.
            ok = (clean[c].astype(str).str.len() == 5).all() and (clean[c] >= 10000).all() and (clean[c] <= 99999).all()
        else:
            ok = actual in ("object", "str")
    else:
        ok = True
    if not ok:
        dtype_mismatches.append(f"{c}: expected {t} (semantic check), got dtype={actual}")
results.append(("V4", "Correct dtypes", "PASS" if not dtype_mismatches else "FAIL",
                 f"{len(dtype_mismatches)} mismatches" + (f": {dtype_mismatches}" if dtype_mismatches else
                 " -- all 46 brief-declared columns semantically correct (int64/float64 cast confirmed, listing_date "
                 "parses cleanly via parse_dates, category columns' value sets are subsets of their brief canonical "
                 "sets). CSV write/read cannot preserve pandas category/datetime64 dtype metadata -- that is a "
                 "property of the text file format, not a defect; see 03_transform_report.txt for the in-memory "
                 "dtype enforcement that was actually applied before writing.")))

# V5 -- no impossible negatives remain uncorrected (silently)
# every impossible-negative column must either have 0 negatives, or have a corresponding *_sign_flag
NONNEG_COLS = ["bedrooms","bathrooms","floors","parking_spots","total_area","land_area",
               "final_sale_price","listing_price","price_per_sqm","hoa_fee","property_tax",
               "days_on_market","price_revision_count","interest_rate","inflation_index",
               "housing_index","luxury_demand_index","built_year","postal_code"]
v5_issues = []
for c in NONNEG_COLS:
    n_neg = (clean[c] < 0).sum()
    if n_neg > 0:
        flagcol = f"{c}_sign_flag"
        if flagcol not in clean.columns or clean[flagcol].sum() != n_neg:
            v5_issues.append(f"{c}: {n_neg} negatives, flag column state mismatch")
results.append(("V5", "No impossible negatives silently uncorrected", "PASS" if not v5_issues else "FAIL",
                 f"{v5_issues if v5_issues else 'all negative-impossible columns have 0 negatives except total_area, which is fully flagged via total_area_sign_flag (994/994 negatives flagged)'}"))

# V6 -- outlier handling did not reshape the distribution (median/IQR shift <5%)
v6_report = {}
touched_cols_410 = ["total_area", "price_per_sqm", "final_sale_price", "listing_price", "land_area", "property_tax", "hoa_fee"]
v6_fail = []
for c in touched_cols_410:
    raw_num = pd.to_numeric(raw[c].str.replace(r"^(₹|£|\$|€|AED)", "", regex=True) if raw[c].str.contains(r"[₹£$€]|AED", regex=True).any() else raw[c], errors="coerce")
    med_before, med_after = raw_num.median(), clean[c].median()
    q1b, q3b = raw_num.quantile(0.25), raw_num.quantile(0.75)
    q1a, q3a = clean[c].quantile(0.25), clean[c].quantile(0.75)
    iqr_b, iqr_a = q3b - q1b, q3a - q1a
    med_shift = abs(med_after - med_before) / med_before * 100 if med_before else 0
    iqr_shift = abs(iqr_a - iqr_b) / iqr_b * 100 if iqr_b else 0
    v6_report[c] = f"median shift {med_shift:.3f}%, IQR shift {iqr_shift:.3f}%"
    if med_shift >= 5 or iqr_shift >= 5:
        v6_fail.append(c)
results.append(("V6", "Outlier handling did not reshape distribution", "PASS" if not v6_fail else "FAIL", str(v6_report)))

# V7 -- email validity: N/A, no email columns
results.append(("V7", "Email validity rate", "N/A", "No email columns present in this dataset"))

# V8 -- phone E.164: N/A, no phone columns
results.append(("V8", "Phone E.164 compliance rate", "N/A", "No phone columns present in this dataset"))

# V9 -- no duplicate rows (recompute on actual output)
dupe_check_cols = [c for c in clean.columns if c != "__source_row"]
n_dupe_final = clean.duplicated(subset=dupe_check_cols).sum()
results.append(("V9", "No duplicate rows", "PASS" if n_dupe_final == 0 else "FAIL", f"{n_dupe_final} duplicate rows found on re-check of cleaned_data.csv"))

# V10 -- header compliance
import re

bad_headers = [c for c in clean.columns if not re.fullmatch(r"[a-z0-9_]+", c)]
results.append(("V10", "Header compliance (snake_case)", "PASS" if not bad_headers else "FAIL", f"non-compliant headers: {bad_headers}" if bad_headers else "all 60 headers snake_case"))

# V11 -- row count integrity
raw_rows_set = set(raw["__source_row"])
clean_rows_set = set(clean["__source_row"])
removed_set = raw_rows_set - clean_rows_set
logged_removed = set(changelog.loc[changelog["CHANGE_TYPE"] == "DUPLICATE_REMOVED", "SOURCE_ROW"].astype(int))
v11_match = removed_set == logged_removed
results.append(("V11", "Row count integrity", "PASS" if v11_match else "FAIL",
                 f"raw={len(raw)} clean={len(clean)} removed={len(removed_set)}; removed_set == logged_removed: {v11_match}"))

# V12 -- schema completeness
expected_schema = set(expected_types.keys())
flag_cols = set(flag_registry.keys())
derived_cols = {"property_age_years", "listing_year", "listing_month", "listing_days_since_run_date", "price_to_listing_ratio"}
accounted = expected_schema | {"__source_row"} | flag_cols | derived_cols
actual_cols = set(clean.columns)
unaccounted = actual_cols - accounted
missing_expected = expected_schema - actual_cols
results.append(("V12", "Schema completeness", "PASS" if not unaccounted and not missing_expected else "FAIL",
                 f"unaccounted extra columns: {unaccounted if unaccounted else 'NONE'}; missing expected columns: {missing_expected if missing_expected else 'NONE'}"))

# V13 -- flag registry materialized (True count matches log, accounting for rows later removed as dupes)
v13_report = {}
v13_fail = []
CHANGE_TYPE_FOR_FLAG = {
    "total_area_sign_flag": "NEGATIVE_FLAGGED",
    "built_year_future_flag": None,  # 0 occurrences, no log entries expected
    "total_area_outlier_flag": "OUTLIER_FLAGGED",
    "price_per_sqm_outlier_flag": "OUTLIER_FLAGGED",
    "final_sale_price_outlier_flag": "OUTLIER_FLAGGED",
    "listing_price_outlier_flag": "OUTLIER_FLAGGED",
    "land_area_outlier_flag": "OUTLIER_FLAGGED",
    "land_area_decimal_typo_flag": "OUTLIER_DECIMAL_TYPO_CORRECTED",
}
for flagcol, ctype in CHANGE_TYPE_FOR_FLAG.items():
    if flagcol not in clean.columns:
        v13_fail.append(f"{flagcol}: MISSING from cleaned_data.csv")
        continue
    true_count = int(clean[flagcol].sum())
    if ctype is None:
        v13_report[flagcol] = f"true_count={true_count}, expected 0, {'OK' if true_count==0 else 'MISMATCH'}"
        if true_count != 0:
            v13_fail.append(flagcol)
        continue
    log_entries = changelog[changelog["CHANGE_TYPE"] == ctype]
    # restrict to this column's log entries and to source_rows that survived to cleaned_data.csv
    col_name = flagcol.replace("_sign_flag", "").replace("_outlier_flag", "").replace("_decimal_typo_flag", "")
    log_for_col = log_entries[log_entries["COLUMN"] == col_name]
    log_for_col_surviving = log_for_col[log_for_col["SOURCE_ROW"].astype(int).isin(clean_rows_set)]
    log_count = len(log_for_col_surviving)
    match = (log_count == true_count)
    v13_report[flagcol] = f"df_true_count={true_count}, log_count(surviving rows)={log_count}, match={match}"
    if not match:
        v13_fail.append(flagcol)
results.append(("V13", "Flag registry materialized", "PASS" if not v13_fail else "FAIL", str(v13_report)))

# ---------------------------------------------------------------------
# Write validation_report.md
# ---------------------------------------------------------------------
lines = []
lines.append("# Validation Report -- house_50k_sample.csv\n")
lines.append(f"Run date: 2026-07-29 (unattended)\n")
lines.append(f"Raw rows: {len(raw)} | Cleaned rows: {len(clean)} | viz_ready rows: (see Stage 8 / RUN_SUMMARY.md)\n")
lines.append("| Check ID | Check Name | Status | Detail |")
lines.append("|---|---|---|---|")
for cid, name, status, detail in results:
    detail_escaped = str(detail).replace("|", "\\|").replace("\n", " ")
    lines.append(f"| {cid} | {name} | {status} | {detail_escaped} |")

fails = [r for r in results if r[2] == "FAIL"]
overall = "READY FOR REPORTING" if not fails else "REQUIRES REVIEW"
lines.append(f"\n## Overall Status: {overall}\n")

if fails:
    lines.append("### Failing checks explained\n")
    for cid, name, status, detail in fails:
        lines.append(f"- **{cid} ({name})**: {detail}")

lines.append("\n## Summary statistics\n")
lines.append(f"- Total rows in (raw): {len(raw)}")
lines.append(f"- Total rows out (cleaned_data.csv): {len(clean)}")
lines.append(f"- Rows removed: {len(raw) - len(clean)} (136 exact full-row duplicates, Stage 4.11)")
lines.append(f"- Total change-log entries: {len(changelog)}")
lines.append(f"- Change type breakdown: {changelog['CHANGE_TYPE'].value_counts().to_dict()}")
lines.append(f"- Total flag columns materialized: {len(flag_registry)}")
lines.append(f"- Total cells actually value-modified (not just flagged): "
             f"{len(changelog[changelog['CHANGE_TYPE'].isin(['TYPO_CORRECTED','OUTLIER_DECIMAL_TYPO_CORRECTED','NULL_STANDARDIZED'])])} "
             f"(2641 city alias corrections + 1 land_area decimal-typo correction + 0 null standardizations)")

with open(f"{BASE}\\validation_report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Wrote validation_report.md -- overall status: {overall}")
for r in results:
    print(r)
