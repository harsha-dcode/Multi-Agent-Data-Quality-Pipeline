"""20-step pipeline test — no API keys, no claude_agent_sdk dependency.

Imports _correct_dates_logic and _impute_logic directly from the tool modules
(they have no I/O side effects).  All new ops from Task 1 are inlined here so
the file has zero dependency on clean.py (which imports claude_agent_sdk at
module top level).

Run:
    python tests/test_pipeline_tools.py
or:
    python -m pytest tests/test_pipeline_tools.py -v -s
"""
from __future__ import annotations

import datetime
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# stdout UTF-8 (Windows console fix)
# ---------------------------------------------------------------------------
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

MESSY_CSV = PROJECT_ROOT / "tests" / "sample_data" / "messy_sales.csv"
# NB: the directory is created in main(), not here. Creating it at import time
# is a side effect of merely *loading* this module — under pytest, main() never
# runs, so it left an empty `tests/cleaned_output/` behind that looked like a
# failed run.
OUT_DIR = PROJECT_ROOT / "tests" / "cleaned_output"
OUT_CSV    = OUT_DIR / "messy_sales_cleaned_v5.csv"
OUT_REPORT = OUT_DIR / "validation_report_v5.txt"

# ---------------------------------------------------------------------------
# Import pure-logic functions from tool modules (no SDK at module level)
# ---------------------------------------------------------------------------
from agent.tools.correct_dates import _correct_dates_logic  # noqa: E402
from agent.tools.impute import _impute_logic  # noqa: E402

# ---------------------------------------------------------------------------
# Inline implementations of the 8 new clean.py ops (Task 1)
# These mirror _apply_op exactly so we can test without importing clean.py.
# ---------------------------------------------------------------------------

NULL_DISGUISES_GENERIC = {"", "-", "?", "n/a", "null", "unknown", "tbd", "not provided", "none", "nan"}

_HONORIFICS_RE = re.compile(r"^\s*(mr\.?|mrs\.?|ms\.?|dr\.?|prof\.?)\s+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[\w.+\-]+@[\w\-]+\.[\w.\-]+$")
_NULL_PHONE = {"?", "-", "n/a", "na", "not provided", "nan", "none", ""}

REGION_MAP = {
    "east": "East", "esat": "East", "eaast": "East", "est": "East",
    "north": "North", "nort": "North", "norh": "North",
    "south": "South", "sourh": "South", "sout": "South", "souht": "South",
    "west": "West", "wst": "West", "wesst": "West",
    "north-east": "North-East", "northeast": "North-East",
    "north east": "North-East", "north_east": "North-East",
    "norht-east": "North-East", "norh-east": "North-East",
}
REGION_NULL = {"-", "n/a", "na", "null", "none", "nan", ""}

PRODUCT_MAP = {v.lower(): v for v in ["Alpha", "Beta", "Delta", "Gamma"]}
PRODUCT_NULL = {"n/a", "na", "null", "none", "nan", "unknown", ""}

CHANNEL_MAP = {
    "online": "Online", "on line": "Online", "on-line": "Online",
    "wholesale": "Wholesale",
    "retail": "Retail", "brick & mortar": "Retail",
    "b2b": "B2B",
    "b2c": "B2C",
}
CHANNEL_NULL = {"n/a", "na", "null", "none", "nan", "-", ""}


def op_nfkc_normalize(df: pd.DataFrame, col: str) -> pd.DataFrame:
    def _nfkc(v):
        if pd.isna(v):
            return v
        s = unicodedata.normalize("NFKC", str(v))
        s = s.strip()
        s = re.sub(r" {2,}", " ", s)
        return s
    df = df.copy()
    df[col] = df[col].map(_nfkc)
    return df


def op_clean_names(df: pd.DataFrame, col: str) -> tuple[pd.DataFrame, int]:
    NULL_D = {"null", "n/a", "na", "unknown", "none", "nan", ""}

    def _clean_name(v):
        if pd.isna(v):
            return v
        s = str(v).strip().rstrip(",").strip()
        if s.lower() in NULL_D:
            return np.nan
        s = re.sub(r"(?<=[a-zA-Z])\.(?=[A-Z])", " ", s)
        s = _HONORIFICS_RE.sub("", s).strip()
        s = s.title()
        s = re.sub(r" {2,}", " ", s).strip()
        return s if s else np.nan

    df = df.copy()
    before = df[col].copy()
    df[col] = df[col].map(_clean_name)
    modified = int((df[col] != before).sum())
    return df, modified


def op_validate_emails(df: pd.DataFrame, col: str, flag_col: str = "email_valid") -> tuple[pd.DataFrame, int, int, int]:
    valid_count = invalid_count = null_count = 0
    new_vals, new_flags = [], []
    for v in df[col]:
        if pd.isna(v) or str(v).strip() == "":
            new_vals.append(np.nan)
            new_flags.append(np.nan)
            null_count += 1
        else:
            cleaned = str(v).lower().replace(" ", "")
            if _EMAIL_RE.match(cleaned):
                new_vals.append(cleaned)
                new_flags.append(True)
                valid_count += 1
            else:
                new_vals.append(np.nan)
                new_flags.append(False)
                invalid_count += 1
    df = df.copy()
    df[col] = new_vals
    df[flag_col] = new_flags
    return df, valid_count, invalid_count, null_count


def op_normalize_phones(df: pd.DataFrame, col: str) -> tuple[pd.DataFrame, int, int]:
    def _norm_phone(v):
        if pd.isna(v):
            return np.nan
        s = str(v).strip()
        # Strip trailing .0 artifact from float→string conversion
        if s.endswith('.0') and s[:-2].isdigit():
            s = s[:-2]
        if s.lower() in _NULL_PHONE:
            return np.nan
        # Strip country code
        s = re.sub(r"^\+91[-\s]?", "", s)
        s = re.sub(r"^91(?=\d{10})", "", s)   # drop "91" when followed by 10 digits
        # Keep only digits
        digits = re.sub(r"\D", "", s)
        if len(digits) > 10:
            digits = digits[-10:]
        return digits if len(digits) == 10 else np.nan

    df = df.copy()
    normalized = df[col].map(_norm_phone)
    n_valid = int(normalized.notna().sum())
    n_nulled = int((normalized.isna() & df[col].notna()).sum())
    df[col] = normalized
    return df, n_valid, n_nulled


def op_fix_region(df: pd.DataFrame, col: str) -> pd.DataFrame:
    def _fix(v):
        if pd.isna(v):
            return np.nan
        s = str(v).strip().lower()
        if s in REGION_NULL:
            return np.nan
        return REGION_MAP.get(s, np.nan)
    df = df.copy()
    df[col] = df[col].map(_fix)
    return df


def op_fix_product(df: pd.DataFrame, col: str) -> pd.DataFrame:
    def _fix(v):
        if pd.isna(v):
            return np.nan
        s = str(v).strip().lower()
        if s in PRODUCT_NULL:
            return np.nan
        return PRODUCT_MAP.get(s, np.nan)
    df = df.copy()
    df[col] = df[col].map(_fix)
    return df


def op_fix_channel(df: pd.DataFrame, col: str) -> pd.DataFrame:
    def _fix(v):
        if pd.isna(v):
            return np.nan
        s = str(v).strip().lower()
        if s in CHANNEL_NULL:
            return np.nan
        return CHANNEL_MAP.get(s, np.nan)
    df = df.copy()
    df[col] = df[col].map(_fix)
    return df


def op_flag_negatives(df: pd.DataFrame, cols: list, flag_col: str = "negative_flag") -> tuple[pd.DataFrame, int]:
    df = df.copy()
    if flag_col not in df.columns:
        df[flag_col] = False
    count = 0
    for c in cols:
        if c not in df.columns:
            continue
        mask = pd.to_numeric(df[c], errors="coerce") < 0
        df.loc[mask, flag_col] = True
        count += int(mask.sum())
    return df, count


# ---------------------------------------------------------------------------
# Inline decimal outlier correction (Step 0 of _impute_logic, Task 2)
# Used to get the count BEFORE calling the real _impute_logic
# (which runs the same logic internally).
# ---------------------------------------------------------------------------

def _decimal_outlier_count(df: pd.DataFrame, numeric_columns: list,
                           revenue_col: str = "total_revenue",
                           units_col: str = "units_sold",
                           price_col: str = "unit_price") -> int:
    """Estimate how many decimal corrections _impute_logic Step 0 will make.

    Mirrors the cross-validated logic in impute._impute_logic Step 0.
    Uses divisors 10, 100, 1000 (smallest first), Case 0 (formula-mismatch),
    Cases 1-3 (outlier-flagged), all with 20× median post-correction threshold.
    """
    # Pre-compute medians on valid (positive) values only
    _medians: dict = {}
    for col in numeric_columns:
        if col not in df.columns:
            continue
        ser = df[col] if pd.api.types.is_numeric_dtype(df[col]) else pd.to_numeric(df[col], errors="coerce")
        pos = ser[ser > 0]
        _medians[col] = float(pos.median()) if not pos.empty else float("nan")

    _rev = revenue_col if revenue_col in df.columns else None
    _u   = units_col   if units_col   in df.columns else None
    _p   = price_col   if price_col   in df.columns else None

    # Ensure numeric for iteration
    df_num = df.copy()
    for col in numeric_columns:
        if col in df_num.columns and not pd.api.types.is_numeric_dtype(df_num[col]):
            df_num[col] = pd.to_numeric(df_num[col], errors="coerce")

    def _is_outlier(val, col):
        med = _medians.get(col, float("nan"))
        return (
            val is not None
            and pd.notna(val) and val > 0
            and not (isinstance(med, float) and med != med)
            and med > 0
            and val > 100 * med
        )

    def _is_corrected(val, col):
        """True when a corrected value is within 20× median — genuinely fixed."""
        med = _medians.get(col, float("nan"))
        return (
            pd.notna(val)
            and not (isinstance(med, float) and med != med)
            and med > 0
            and val <= 20 * med
        )

    count = 0
    for idx in df_num.index:
        rev   = df_num.at[idx, _rev] if _rev else float("nan")
        units = df_num.at[idx, _u]   if _u   else float("nan")
        price = df_num.at[idx, _p]   if _p   else float("nan")

        rev_null   = _rev   is None or pd.isna(rev)
        units_null = _u     is None or pd.isna(units)
        price_null = _p     is None or pd.isna(price)

        rev_out   = (not rev_null)   and bool(_is_outlier(rev,   _rev   or ""))
        units_out = (not units_null) and bool(_is_outlier(units, _u     or ""))
        price_out = (not price_null) and bool(_is_outlier(price, _p     or ""))

        # Case 0: formula-mismatch — all three present, none are outliers by
        # median test, but revenue >> units×price (ratio >= 9).
        # Tries divisors first; if none match within 5%, counts a formula-replace.
        if (not rev_null) and (not units_null) and (not price_null) and not (rev_out or units_out or price_out):
            r_f = float(rev); u_f = float(units); p_f = float(price)
            if u_f > 0 and p_f > 0 and r_f > 0:
                expected = u_f * p_f
                ratio = r_f / expected if expected != 0 else float("nan")
                if pd.notna(ratio) and ratio >= 9:
                    corrected = False
                    for divisor in [10, 100, 1000]:
                        c_rev = r_f / divisor
                        if abs(c_rev - expected) / max(abs(expected), 1e-9) <= 0.05:
                            if _is_corrected(c_rev, _rev or "") and _rev:
                                count += 1
                            corrected = True
                            break
                    if not corrected and _rev and _is_corrected(expected, _rev or ""):
                        count += 1  # formula-replace fallback
            continue  # All three present and non-outlier — skip Cases 1-3

        if not (rev_out or units_out or price_out):
            continue

        applied = False
        # Try divisors smallest-first so we prefer the least-aggressive correction
        for divisor in [10, 100, 1000]:
            c_rev   = float(rev)   / divisor if rev_out   else (float(rev)   if not rev_null   else float("nan"))
            c_units = float(units) / divisor if units_out else (float(units) if not units_null else float("nan"))
            c_price = float(price) / divisor if price_out else (float(price) if not price_null else float("nan"))

            all_three = pd.notna(c_rev) and pd.notna(c_units) and pd.notna(c_price)

            # Case 1: all three present — check formula balance AND corrected
            # outlier values land within 20× median (genuinely fixed).
            if all_three and c_units != 0 and c_price != 0:
                computed_rev = c_units * c_price
                formula_ok = abs(c_rev - computed_rev) / max(abs(c_rev), 1e-9) <= 0.05
                rev_fixed   = (not rev_out)   or _is_corrected(c_rev,   _rev or "")
                units_fixed = (not units_out) or _is_corrected(c_units, _u   or "")
                price_fixed = (not price_out) or _is_corrected(c_price, _p   or "")
                if formula_ok and rev_fixed and units_fixed and price_fixed:
                    n_changes = sum([rev_out and bool(_rev), units_out and bool(_u), price_out and bool(_p)])
                    count += n_changes
                    applied = True
                    break

            # Case 2: revenue missing — validate corrected value against revenue median
            if not all_three and rev_null and pd.notna(c_units) and pd.notna(c_price):
                rev_med = _medians.get(_rev or "", float("nan"))
                units_fixed = (not units_out) or _is_corrected(c_units, _u or "")
                price_fixed = (not price_out) or _is_corrected(c_price, _p or "")
                if pd.notna(rev_med) and rev_med > 0 and c_units != 0 and c_price != 0:
                    derived_rev = c_units * c_price
                    if derived_rev <= 20 * rev_med and units_fixed and price_fixed:
                        n_changes = sum([units_out and bool(_u), price_out and bool(_p)])
                        if n_changes > 0:
                            count += n_changes
                            applied = True
                            break

            # Case 3: one value missing (not revenue) — validate corrected outlier via formula
            if not applied and not all_three:
                if price_null and pd.notna(c_rev) and pd.notna(c_units) and c_units != 0:
                    expected_price = c_rev / c_units
                    p_med = _medians.get(_p or "", float("nan"))
                    rev_fixed = (not rev_out) or _is_corrected(c_rev, _rev or "")
                    if pd.notna(p_med) and 0 < expected_price <= 20 * p_med and rev_fixed:
                        if rev_out and _rev:
                            count += 1
                            applied = True
                            break
                if not applied and rev_out and pd.notna(c_units) and pd.notna(c_price) and c_units != 0 and c_price != 0:
                    expected_rev = c_units * c_price
                    rev_fixed = _is_corrected(c_rev, _rev or "")
                    if abs(c_rev - expected_rev) / max(abs(expected_rev), 1e-9) <= 0.05 and rev_fixed:
                        count += 1
                        applied = True
                        break
    return count


# ===========================================================================
# Main pipeline — 20 steps
# ===========================================================================

def run_pipeline(csv_path: Path):
    """Execute all 20 steps; return tracking dict."""
    tracking = {}

    # ---- Load raw data ------------------------------------------------------
    df = pd.read_csv(csv_path)
    tracking["input_rows"] = len(df)

    # Capture null rates BEFORE any cleaning, aligned to original columns
    null_rates_before_raw = {col: round(float(df[col].isna().mean() * 100), 2) for col in df.columns}

    # =========================================================================
    # STEP 1: Headers -> snake_case
    # =========================================================================
    df.columns = [
        re.sub(r"[\s_]+", "_", col.strip()).lower().strip("_")
        for col in df.columns
    ]
    tracking["step1_cols"] = list(df.columns)
    # Build null_rates_before keyed on NEW column names (after rename)
    old_cols = list(null_rates_before_raw.keys())
    new_cols = tracking["step1_cols"]
    null_rates_before = {}
    for old, new in zip(old_cols, new_cols):
        null_rates_before[new] = null_rates_before_raw[old]

    # =========================================================================
    # STEP 2: Null disguises -> NaN on all string/object columns
    # =========================================================================
    NULL_DISGUISES_STEP2 = {"", "-", "?", "n/a", "null", "unknown", "tbd", "not provided", "none", "nan"}
    null_disguise_count = 0
    # include both "object" and "str" to work with pandas 2 and 3
    _str_dtypes = ["object", "str"] if "str" in pd.api.types.pandas_dtype.__module__ or True else ["object"]
    for col in df.select_dtypes(include=["object", "string"]).columns:
        mask = df[col].astype(str).str.strip().str.lower().isin(NULL_DISGUISES_STEP2)
        null_disguise_count += int(mask.sum())
        df.loc[mask, col] = np.nan
    tracking["step2_null_disguises"] = null_disguise_count

    # =========================================================================
    # STEP 3: NFKC unicode normalize on all string/object columns
    # =========================================================================
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df = op_nfkc_normalize(df, col)
    tracking["step3_done"] = True

    # =========================================================================
    # STEP 4: clean_names on customer_name
    # =========================================================================
    if "customer_name" in df.columns:
        df, names_modified = op_clean_names(df, "customer_name")
        tracking["step4_names_modified"] = names_modified
    else:
        tracking["step4_names_modified"] = 0

    # =========================================================================
    # STEP 5: validate_emails on customer_email -> email_valid flag
    # =========================================================================
    if "customer_email" in df.columns:
        df, valid_emails, invalid_emails, null_emails = op_validate_emails(df, "customer_email", "email_valid")
        tracking["step5_valid_emails"] = valid_emails
        tracking["step5_invalid_emails"] = invalid_emails
        tracking["step5_null_emails"] = null_emails
        tracking["step5_total"] = len(df)
    else:
        tracking["step5_valid_emails"] = 0
        tracking["step5_invalid_emails"] = 0
        tracking["step5_null_emails"] = 0
        tracking["step5_total"] = len(df)

    # =========================================================================
    # STEP 6: normalize_phones on phone_number
    # =========================================================================
    phone_col = "phone_number" if "phone_number" in df.columns else None
    if phone_col:
        df, n_valid_phones, n_nulled_phones = op_normalize_phones(df, phone_col)
        tracking["step6_valid_phones"] = n_valid_phones
        tracking["step6_nulled_phones"] = n_nulled_phones
        # Bug 1 fix: force phone column to string dtype to prevent float/int upcast
        df[phone_col] = df[phone_col].apply(
            lambda v: f"{int(float(v)):010d}" if pd.notna(v) else np.nan
        )
        # Store as pandas object dtype (strings + NaN)
        df[phone_col] = df[phone_col].astype(object)
    else:
        tracking["step6_valid_phones"] = 0
        tracking["step6_nulled_phones"] = 0

    # =========================================================================
    # STEP 7a/b/c: fix_region, fix_product, fix_channel
    # =========================================================================
    if "region" in df.columns:
        df = op_fix_region(df, "region")
    if "product" in df.columns:
        df = op_fix_product(df, "product")
    if "channel" in df.columns:
        df = op_fix_channel(df, "channel")

    region_unique = sorted(df["region"].dropna().unique().tolist()) if "region" in df.columns else []
    product_unique = sorted(df["product"].dropna().unique().tolist()) if "product" in df.columns else []
    channel_unique = sorted(df["channel"].dropna().unique().tolist()) if "channel" in df.columns else []
    tracking["step7_region_unique"] = region_unique
    tracking["step7_product_unique"] = product_unique
    tracking["step7_channel_unique"] = channel_unique

    # =========================================================================
    # STEP 8: Strip currency (INR, $, Rs) and unit suffixes; cast numeric cols
    # =========================================================================
    for col in ["unit_price", "units_sold", "total_revenue"]:
        if col not in df.columns:
            continue
        df[col] = (
            df[col].astype(str)
            .str.replace(r"[₹$,]", "", regex=True)
            .str.replace(r"(?i)\s*INR\s*", "", regex=True)
            .str.replace(r"(?i)\s*units?\s*$", "", regex=True)
            .str.replace(r"[/\-]+$", "", regex=True)
            .str.strip()
            .replace({"nan": np.nan, "none": np.nan, "": np.nan, "?": np.nan, "-": np.nan})
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")
    tracking["step8_done"] = True

    # =========================================================================
    # STEP 9-11: Date parse via _correct_dates_logic (snaps + casts + flags)
    # =========================================================================
    date_col = "order_date" if "order_date" in df.columns else None
    if date_col is None:
        for c in df.columns:
            if "date" in c.lower():
                date_col = c
                break

    date_summary = {"snapped": 0, "flagged_future": 0, "flagged_far_past": 0, "flagged_far_future": 0,
                    "rows_processed": 0, "median_year_used": 2024}
    if date_col and not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        # Convert Excel serial date integers before calling _correct_dates_logic.
        # Excel epoch is 1899-12-30; serial 45000 = 2023-03-15.
        _EXCEL_EPOCH = pd.Timestamp("1899-12-30")
        _EXCEL_RE = re.compile(r"^\s*\d{5}\s*$")
        def _convert_excel_serial(v):
            if pd.isna(v):
                return v
            s = str(v).strip()
            if _EXCEL_RE.match(s):
                try:
                    serial = int(s)
                    # Excel erroneously treats 1900 as leap year; adjust for serials > 59
                    if serial > 59:
                        serial -= 1
                    return (_EXCEL_EPOCH + pd.Timedelta(days=serial)).strftime("%Y-%m-%d")
                except Exception:
                    return v
            return v
        df[date_col] = df[date_col].map(_convert_excel_serial)

        df, date_summary, _date_log = _correct_dates_logic(df, date_col)
        if "error" in date_summary:
            date_summary = {"snapped": 0, "flagged_future": 0, "flagged_far_past": 0,
                            "flagged_far_future": 0, "rows_processed": 0, "median_year_used": 2024}
    tracking["step9_date_summary"] = date_summary

    # =========================================================================
    # STEP 12: Outlier decimal correction (Step 0 inside _impute_logic)
    # We measure count here; the actual correction happens inside _impute_logic.
    # =========================================================================
    numeric_cols_for_impute = [c for c in ["units_sold", "unit_price", "total_revenue"] if c in df.columns]
    decimal_correction_preview = _decimal_outlier_count(df, numeric_cols_for_impute)
    tracking["step12_decimal_corrections_preview"] = decimal_correction_preview

    # =========================================================================
    # STEP 13: flag_negatives on [units_sold, unit_price, total_revenue]
    # =========================================================================
    neg_cols = [c for c in ["units_sold", "unit_price", "total_revenue"] if c in df.columns]
    df, neg_count = op_flag_negatives(df, neg_cols, "negative_flag")
    tracking["step13_negative_count"] = neg_count

    # =========================================================================
    # STEPS 14-17: imputation via _impute_logic (includes Step 0 decimal fix)
    # =========================================================================
    critical_columns = [
        "order_id",
        date_col if date_col else "order_date",
        "units_sold", "unit_price", "total_revenue", "region", "product",
    ]
    categorical_columns = [c for c in ["region", "product", "channel"] if c in df.columns]

    rows_before_impute = len(df)
    df, impute_summary, _impute_log = _impute_logic(
        df,
        critical_columns=critical_columns,
        email_col="customer_email",
        name_col="customer_name",
        revenue_col="total_revenue",
        units_col="units_sold",
        price_col="unit_price",
        categorical_columns=categorical_columns,
        numeric_columns=numeric_cols_for_impute,
    )
    tracking["step14_formula_fills"] = impute_summary["formula_fills"]
    tracking["step15_pattern_name_fills"] = impute_summary["pattern_name_fills"]
    tracking["step15_pattern_email_fills"] = impute_summary["pattern_email_fills"]
    tracking["step16_mode_fills"] = impute_summary["statistical_mode_fills"]
    tracking["step16_median_fills"] = impute_summary["statistical_median_fills"]
    tracking["step17_rows_dropped"] = impute_summary["rows_dropped"]
    tracking["step12_outlier_corrections"] = impute_summary.get("outlier_corrections", 0)

    # Bug 3 fix: re-run flag_negatives after imputation to catch newly derived negatives
    neg_cols_post = [c for c in ["units_sold", "unit_price", "total_revenue"] if c in df.columns]
    df, neg_count_post = op_flag_negatives(df, neg_cols_post, "negative_flag")
    tracking["step13_negative_count"] += neg_count_post  # accumulate total

    rows_after_impute = len(df)
    tracking["rows_after_impute"] = rows_after_impute

    # =========================================================================
    # STEP 18: Deduplication — exact first, then near-dedup on order_id
    # =========================================================================
    before_exact = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    exact_removed = before_exact - len(df)

    if "order_id" in df.columns:
        df["_order_id_norm"] = df["order_id"].astype(str).str.strip().str.upper()
        before_near = len(df)
        df = df.drop_duplicates(subset=["_order_id_norm"], keep="first").reset_index(drop=True)
        near_removed = before_near - len(df)
        df = df.drop(columns=["_order_id_norm"])
    else:
        near_removed = 0

    tracking["step18_exact_removed"] = exact_removed
    tracking["step18_near_removed"] = near_removed
    tracking["rows_final"] = len(df)

    # =========================================================================
    # STEP 19: Final dtype cast
    # =========================================================================
    for col in ["units_sold", "unit_price", "total_revenue"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    if date_col and date_col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce", format="mixed", dayfirst=True)
    for col in ["region", "product", "channel"]:
        if col in df.columns:
            df[col] = df[col].astype("category")
    # Bug 1 fix: ensure phone_number stays as string dtype (not int/float upcast)
    if phone_col and phone_col in df.columns:
        df[phone_col] = df[phone_col].apply(
            lambda v: str(v).zfill(10) if pd.notna(v) and str(v) != 'nan' else np.nan
        )
    tracking["step19_done"] = True

    # =========================================================================
    # STEP 20: Validate and compute null rates
    # =========================================================================
    null_rates_after = {col: round(float(df[col].isna().mean() * 100), 2) for col in df.columns}
    tracking["null_rates_before"] = null_rates_before
    tracking["null_rates_after"] = null_rates_after
    tracking["df_final"] = df
    tracking["date_col"] = date_col
    tracking["phone_col"] = phone_col

    return tracking


# ===========================================================================
# Validation report builder
# ===========================================================================

def build_report(tracking: dict) -> str:
    df = tracking["df_final"]
    ds = tracking["step9_date_summary"]
    nr_before = tracking["null_rates_before"]
    nr_after = tracking["null_rates_after"]
    date_col = tracking["date_col"] or "order_date"
    phone_col = tracking.get("phone_col")

    input_rows = tracking["input_rows"]
    rows_after_impute = tracking["rows_after_impute"]
    rows_final = tracking["rows_final"]
    total_removed = input_rows - rows_final

    lines = []
    SEP = "=" * 70

    lines.append(SEP)
    lines.append("VALIDATION REPORT --- messy_sales.csv")
    lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(SEP)
    lines.append("")

    # ---- Step execution summary -------------------------------------------
    lines.append("STEP EXECUTION SUMMARY")

    def chk(condition: bool, label: str, extra: str = "") -> str:
        mark = "✓" if condition else "✗"
        tail = f"  ({extra})" if extra else ""
        return f"  {label:<42} {mark}{tail}"

    lines.append(chk(True, "Step  1: Headers normalized",
                      f"{len(tracking['step1_cols'])} columns"))
    lines.append(chk(tracking["step2_null_disguises"] >= 0, "Step  2: Null disguises replaced",
                      f"{tracking['step2_null_disguises']} cells set to NaN"))
    lines.append(chk(True, "Step  3: NFKC unicode normalize"))
    lines.append(chk(True, "Step  4: Names cleaned",
                      f"{tracking['step4_names_modified']} cells modified"))
    total_email = tracking["step5_total"]
    valid_email = tracking["step5_valid_emails"]
    lines.append(chk(True, "Step  5: Emails validated",
                      f"{valid_email}/{total_email} valid"))
    lines.append(chk(True, "Step  6: Phones normalized",
                      f"{tracking['step6_valid_phones']} valid 10-digit"))

    region_ok = len(tracking["step7_region_unique"]) == 5 and df["region"].isna().sum() == 0 if "region" in df.columns else False
    product_ok = len(tracking["step7_product_unique"]) == 4 and df["product"].isna().sum() == 0 if "product" in df.columns else False
    channel_ok = len(tracking["step7_channel_unique"]) <= 6 and df["channel"].isna().sum() == 0 if "channel" in df.columns else False
    lines.append(chk(region_ok and product_ok and channel_ok,
                      "Step  7: Categories fixed",
                      f"region: {len(tracking['step7_region_unique'])} unique, "
                      f"product: {len(tracking['step7_product_unique'])}, "
                      f"channel: <={len(tracking['step7_channel_unique'])}"))
    lines.append(chk(True, "Step  8: Numeric cleaning"))

    snapped = ds.get("snapped", 0)
    flagged = ds.get("flagged_future", 0) + ds.get("flagged_far_past", 0) + ds.get("flagged_far_future", 0)
    date_col_ok = date_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[date_col])
    lines.append(chk(date_col_ok, "Step  9-11: Dates parsed/corrected",
                      f"{snapped} snapped, {flagged} flagged"))

    lines.append(chk(True, "Step 12: Outlier decimal correction",
                      f"{tracking['step12_outlier_corrections']} corrections"))
    lines.append(chk(True, "Step 13: Negative values flagged",
                      f"{tracking['step13_negative_count']} flagged"))

    formula = tracking["step14_formula_fills"]
    pattern = tracking["step15_pattern_name_fills"] + tracking["step15_pattern_email_fills"]
    stat = tracking["step16_mode_fills"] + tracking["step16_median_fills"]
    lines.append(chk(True, "Step 14-16: Imputation",
                      f"{formula}F + {pattern}P + {stat}S fills"))
    lines.append(chk(True, "Step 17: Damaged rows dropped",
                      f"{tracking['step17_rows_dropped']} dropped"))
    lines.append(chk(True, "Step 18: Deduplication",
                      f"{tracking['step18_exact_removed']} exact + "
                      f"{tracking['step18_near_removed']} near-dups removed"))
    lines.append(chk(True, "Step 19: Final dtype cast"))
    lines.append(chk(True, "Step 20: Validation                    "))
    lines.append("")

    # ---- Row counts --------------------------------------------------------
    lines.append("ROW COUNTS")
    lines.append(f"  Input                 : {input_rows}")
    lines.append(f"  After dedup           : {rows_final + tracking['step18_exact_removed'] + tracking['step18_near_removed']}")
    lines.append(f"  After imputation/drop : {rows_after_impute}")
    lines.append(f"  Final                 : {rows_final}")
    lines.append(f"  Total removed         : {total_removed}")
    lines.append("")

    # ---- Null rates table --------------------------------------------------
    TARGET_ZERO = ["region", "product", "channel", "units_sold", "unit_price", "total_revenue"]
    TARGET_LT5 = [date_col]
    DISPLAY_COLS = [
        "order_id", date_col, "customer_name", "customer_email", "phone_number",
        "region", "product", "channel", "units_sold", "unit_price", "total_revenue",
        "email_valid", "date_flag", "negative_flag", "revenue_mismatch",
    ]
    lines.append("NULL RATES --- BEFORE vs AFTER")
    lines.append(f"  {'Column':<28}  {'Before%':>8}  {'After%':>7}  {'Target':<8}  {'Pass/Fail'}")
    lines.append(f"  {'-'*28}  {'-'*8}  {'-'*7}  {'-'*8}  {'-'*9}")
    for col in DISPLAY_COLS:
        if col not in df.columns:
            continue
        b = nr_before.get(col, float("nan"))
        a = nr_after.get(col, float("nan"))
        b_str = f"{b:.1f}%" if not np.isnan(b) else "n/a"
        a_str = f"{a:.1f}%" if not np.isnan(a) else "n/a"
        if col in TARGET_ZERO:
            target = "0%"
            pf = "PASS" if (not np.isnan(a) and a == 0.0) else "FAIL"
        elif col in TARGET_LT5:
            target = "<5%"
            pf = "PASS" if (not np.isnan(a) and a < 5.0) else "FAIL"
        else:
            target = "-"
            pf = "-"
        lines.append(f"  {col:<28}  {b_str:>8}  {a_str:>7}  {target:<8}  {pf}")
    lines.append("")

    # ---- Categorical cardinality -------------------------------------------
    lines.append("CATEGORICAL CARDINALITY")
    for col in ["region", "product", "channel"]:
        if col in df.columns:
            unique_vals = sorted(df[col].dropna().astype(str).unique().tolist())
            lines.append(f"  {col:<9} unique values : {unique_vals}")
    lines.append("")

    # ---- Anomaly flags -----------------------------------------------------
    lines.append("ANOMALY FLAGS")
    n_invalid_email = int((df["email_valid"] == False).sum()) if "email_valid" in df.columns else 0  # noqa: E712
    n_negative = int((df["negative_flag"] == True).sum()) if "negative_flag" in df.columns else 0  # noqa: E712
    n_mismatch = int((df["revenue_mismatch"] == True).sum()) if "revenue_mismatch" in df.columns else 0  # noqa: E712

    date_flag_nonempty = 0
    ff = fn_fp = fn_ff = 0
    if "date_flag" in df.columns:
        nonempty_flags = df["date_flag"].astype(str).str.strip()
        nonempty_flags = nonempty_flags[nonempty_flags != ""]
        date_flag_nonempty = len(nonempty_flags)
        ff = int(nonempty_flags.str.contains("future_date", na=False).sum())
        fn_fp = int(nonempty_flags.str.contains("year_far_past", na=False).sum())
        fn_ff = int(nonempty_flags.str.contains("year_far_future", na=False).sum())

    lines.append(f"  email_valid=False      : {n_invalid_email} rows")
    lines.append(f"  negative_flag=True     : {n_negative} rows")
    lines.append(f"  revenue_mismatch=True  : {n_mismatch} rows")
    lines.append(f"  date_flag non-empty    : {date_flag_nonempty} rows "
                 f"(breakdown: future={ff}, far_past={fn_fp}, far_future={fn_ff})")
    lines.append("")

    # ---- Imputation summary ------------------------------------------------
    lines.append("IMPUTATION SUMMARY")
    lines.append(f"  Outlier decimal corrections : {tracking['step12_outlier_corrections']}")
    lines.append(f"  Formula fills               : {tracking['step14_formula_fills']}")
    lines.append(f"  Pattern name fills          : {tracking['step15_pattern_name_fills']}")
    lines.append(f"  Pattern email fills         : {tracking['step15_pattern_email_fills']}")
    lines.append(f"  Statistical mode fills      : {tracking['step16_mode_fills']}")
    lines.append(f"  Statistical median fills    : {tracking['step16_median_fills']}")
    lines.append(f"  Rows dropped (3+ nulls)     : {tracking['step17_rows_dropped']}")
    lines.append("")

    # ---- Date corrections --------------------------------------------------
    lines.append("DATE CORRECTIONS")
    lines.append(f"  Dates snapped (impossible)  : {ds.get('snapped', 0)}")
    lines.append(f"  Flagged future              : {ds.get('flagged_future', 0)}")
    lines.append(f"  Flagged far past            : {ds.get('flagged_far_past', 0)}")
    lines.append(f"  Flagged far future          : {ds.get('flagged_far_future', 0)}")
    lines.append("")

    # ---- Pass/Fail summary -------------------------------------------------
    lines.append("PASS/FAIL SUMMARY")
    checks_pass = 0
    checks_total = 0

    def pf_check(condition: bool, msg_pass: str, msg_fail: str = "") -> str:
        nonlocal checks_pass, checks_total
        checks_total += 1
        if condition:
            checks_pass += 1
            return f"  PASS: {msg_pass}"
        else:
            return f"  FAIL: {msg_fail or msg_pass}"

    region_n = len(df["region"].cat.categories) if "region" in df.columns and hasattr(df["region"], "cat") else len(df["region"].dropna().unique()) if "region" in df.columns else 0
    region_null_rate = nr_after.get("region", 0)
    product_n = len(df["product"].cat.categories) if "product" in df.columns and hasattr(df["product"], "cat") else len(df["product"].dropna().unique()) if "product" in df.columns else 0
    product_null_rate = nr_after.get("product", 0)
    channel_n = len(df["channel"].cat.categories) if "channel" in df.columns and hasattr(df["channel"], "cat") else len(df["channel"].dropna().unique()) if "channel" in df.columns else 0
    channel_null_rate = nr_after.get("channel", 0)

    lines.append(pf_check(region_n == 5 and region_null_rate == 0,
                           "region has exactly 5 unique values (no nulls)",
                           f"region has {region_n} unique values, null_rate={region_null_rate}%"))
    lines.append(pf_check(product_n == 4 and product_null_rate == 0,
                           "product has exactly 4 unique values (no nulls)",
                           f"product has {product_n} unique values, null_rate={product_null_rate}%"))
    lines.append(pf_check(channel_n <= 6 and channel_null_rate == 0,
                           "channel has <=6 unique values (no nulls)",
                           f"channel has {channel_n} unique values, null_rate={channel_null_rate}%"))

    for col in ["units_sold", "unit_price", "total_revenue"]:
        rate = nr_after.get(col, 100.0)
        lines.append(pf_check(rate == 0.0, f"{col} null rate = 0%",
                               f"{col} null rate = {rate}%"))

    date_rate = nr_after.get(date_col, 100.0)
    lines.append(pf_check(date_rate < 5.0, f"order_date null rate < 5%",
                           f"order_date null rate = {date_rate}%"))

    final_row_ok = 270 <= rows_final <= 285
    lines.append(pf_check(final_row_ok,
                           f"final row count between 270-285 (actual={rows_final})",
                           f"final row count = {rows_final}, expected 270-285"))

    date_flag_exists = "date_flag" in df.columns
    lines.append(pf_check(date_flag_exists,
                           "date_flag column exists",
                           "date_flag column missing"))

    email_valid_exists = "email_valid" in df.columns
    lines.append(pf_check(email_valid_exists,
                           "email_valid column exists",
                           "email_valid column missing"))

    phone_ok = False
    _pc = tracking.get("phone_col")
    if _pc and _pc in df.columns:
        non_null = df[_pc].replace("", np.nan).dropna()
        dtype_str = str(df[_pc].dtype)
        phone_ok = (
            dtype_str in ("object", "str", "string")
            and all(re.match(r'^\d{10}$', str(v)) for v in non_null)
        )
    lines.append(pf_check(phone_ok,
        f"phone_number dtype=object, all non-null values are 10-digit strings",
        f"phone dtype={df[_pc].dtype if _pc and _pc in df.columns else 'N/A'}"))

    max_units = float(df["units_sold"].max()) if "units_sold" in df.columns else float("inf")
    max_rev   = float(df["total_revenue"].max()) if "total_revenue" in df.columns else float("inf")
    lines.append(pf_check(max_units < 500,   f"max(units_sold) = {max_units:.0f} < 500",   f"max(units_sold) = {max_units:.0f} — outliers remain"))
    lines.append(pf_check(max_rev   < 50000, f"max(total_revenue) = {max_rev:.0f} < 50000", f"max(total_revenue) = {max_rev:.0f} — outliers remain"))

    lines.append("")
    overall = "PASS" if checks_pass == checks_total else "FAIL"
    lines.append(f"OVERALL: {overall} ({checks_pass}/{checks_total} checks passed)")
    lines.append(SEP)

    return "\n".join(lines)


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nRunning 20-step pipeline on: {MESSY_CSV}\n")
    tracking = run_pipeline(MESSY_CSV)
    report = build_report(tracking)

    # Write CSV
    import csv as _csv_module

    # Ensure phone_number writes as a quoted string in CSV so readers
    # (pandas, Excel) don't re-infer it as float64.
    df_out = tracking["df_final"].copy()
    _pc = tracking.get("phone_col")
    if _pc and _pc in df_out.columns:
        # Re-format: strip any .0 artifact and zero-pad to 10 digits
        def _fmt_phone(v):
            if pd.isna(v):
                return ""
            s = str(v).strip()
            if s.endswith('.0') and s[:-2].isdigit():
                s = s[:-2]
            return s.zfill(10)
        df_out[_pc] = df_out[_pc].apply(_fmt_phone)

    df_out.to_csv(OUT_CSV, index=False, quoting=_csv_module.QUOTE_NONNUMERIC)
    print(f"Cleaned CSV written to: {OUT_CSV}")

    # Write and print report
    with open(OUT_REPORT, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"Validation report written to: {OUT_REPORT}\n")
    print(report)

    # Return exit code based on OVERALL
    if "OVERALL: FAIL" in report:
        return 1
    return 0


# ===========================================================================
# Pytest test functions (each runs the full pipeline once via module-level cache)
# ===========================================================================

_PIPELINE_RESULT: dict | None = None


def _get_result() -> dict:
    global _PIPELINE_RESULT
    if _PIPELINE_RESULT is None:
        _PIPELINE_RESULT = run_pipeline(MESSY_CSV)
    return _PIPELINE_RESULT


def test_step1_headers_snake_case():
    t = _get_result()
    for col in t["step1_cols"]:
        assert col == col.lower(), f"Column '{col}' is not lowercase"
        assert " " not in col, f"Column '{col}' has spaces"


def test_step2_null_disguises_replaced():
    t = _get_result()
    assert t["step2_null_disguises"] > 0, "Expected at least some null disguises replaced"


def test_step4_names_cleaned():
    t = _get_result()
    assert t["step4_names_modified"] >= 0


def test_step5_email_valid_column_exists():
    t = _get_result()
    assert "email_valid" in t["df_final"].columns


def test_step7_region_has_five_values():
    t = _get_result()
    assert len(t["step7_region_unique"]) == 5, f"Got: {t['step7_region_unique']}"


def test_step7_product_has_four_values():
    t = _get_result()
    assert len(t["step7_product_unique"]) == 4, f"Got: {t['step7_product_unique']}"


def test_step9_dates_parsed():
    t = _get_result()
    date_col = t["date_col"]
    assert date_col in t["df_final"].columns
    assert pd.api.types.is_datetime64_any_dtype(t["df_final"][date_col])


def test_step9_dates_snapped():
    t = _get_result()
    assert t["step9_date_summary"]["snapped"] > 0, "Expected at least one date snapped"


def test_step13_negative_flag_exists():
    t = _get_result()
    assert "negative_flag" in t["df_final"].columns


def test_step17_damaged_rows_dropped():
    t = _get_result()
    assert t["step17_rows_dropped"] >= 0


def test_step18_dedup():
    t = _get_result()
    assert t["rows_final"] < t["input_rows"], "Expected row count to decrease after dedup+drop"


def test_final_row_count_in_range():
    t = _get_result()
    rows = t["rows_final"]
    assert 270 <= rows <= 285, f"Final row count {rows} outside expected range 270-285"


if __name__ == "__main__":
    sys.exit(main())
