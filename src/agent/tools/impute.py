"""Stage 5: Multi-pass imputation — formula derivation, pattern matching, statistical fallback.

Pass order:
  A. Formula: derive total_revenue / unit_price / units_sold from the other two when
     exactly one is missing.
  B. Pattern: derive customer_name from email and vice-versa.
  C. Statistical: mode for categoricals, median for numerics.
  D. Drop: rows with >= 3 critical nulls after all passes.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from claude_agent_sdk import tool


_DEFAULT_CRITICAL_COLUMNS = [
    "order_id", "order_date", "units_sold", "unit_price",
    "total_revenue", "region", "product",
]
_DEFAULT_CATEGORICAL_COLUMNS = ["region", "product", "channel"]
_DEFAULT_NUMERIC_COLUMNS = ["units_sold", "unit_price", "total_revenue"]
_DEFAULT_EMAIL_COLUMN = "customer_email"
_DEFAULT_NAME_COLUMN = "customer_name"
_DEFAULT_REVENUE_COLUMN = "total_revenue"
_DEFAULT_UNITS_COLUMN = "units_sold"
_DEFAULT_PRICE_COLUMN = "unit_price"

_NAME_EMAIL_RE = re.compile(r"^[\w.]+\.[\w.]+$")


def _is_null_or_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and np.isnan(val):
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def _impute_logic(
    df: pd.DataFrame,
    critical_columns: list[str],
    email_col: str,
    name_col: str,
    revenue_col: str,
    units_col: str,
    price_col: str,
    categorical_columns: list[str],
    numeric_columns: list[str],
) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    """All imputation logic with no I/O side-effects. Returns (df, summary, log_lines)."""

    log_lines: list[str] = []
    formula_fills = 0
    pattern_name_fills = 0
    pattern_email_fills = 0
    statistical_mode_fills = 0
    statistical_median_fills = 0

    df = df.copy()

    # ------------------------------------------------------------------ #
    # STEP 0 — Decimal-typo outlier correction (cross-validated)         #
    # ------------------------------------------------------------------ #
    outlier_corrections = 0

    _medians: dict[str, float] = {}
    for col in numeric_columns:
        if col not in df.columns:
            continue
        ser = df[col] if pd.api.types.is_numeric_dtype(df[col]) else pd.to_numeric(df[col], errors="coerce")
        pos = ser[ser > 0]
        _medians[col] = float(pos.median()) if not pos.empty else float("nan")

    for col in numeric_columns:
        if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    _rev = revenue_col if revenue_col in df.columns else None
    _u   = units_col   if units_col   in df.columns else None
    _p   = price_col   if price_col   in df.columns else None

    def _is_outlier(val: float, col: str) -> bool:
        med = _medians.get(col, float("nan"))
        return (
            val is not None
            and not (isinstance(val, float) and (val != val))
            and val > 0
            and not (isinstance(med, float) and (med != med))
            and med > 0
            and val > 100 * med
        )

    def _is_corrected(val: float, col: str) -> bool:
        med = _medians.get(col, float("nan"))
        return (
            not (isinstance(val, float) and (val != val))
            and not (isinstance(med, float) and (med != med))
            and med > 0
            and val <= 20 * med
        )

    for idx in df.index:
        rev   = df.at[idx, _rev] if _rev else float("nan")
        units = df.at[idx, _u]   if _u   else float("nan")
        price = df.at[idx, _p]   if _p   else float("nan")

        rev_null   = _rev   is None or (isinstance(rev,   float) and rev   != rev)
        units_null = _u     is None or (isinstance(units, float) and units != units)
        price_null = _p     is None or (isinstance(price, float) and price != price)

        rev_out   = (not rev_null)   and _is_outlier(float(rev)   if not rev_null   else 0, _rev   or "")
        units_out = (not units_null) and _is_outlier(float(units) if not units_null else 0, _u     or "")
        price_out = (not price_null) and _is_outlier(float(price) if not price_null else 0, _p     or "")

        if (not rev_null) and (not units_null) and (not price_null) and not (rev_out or units_out or price_out):
            r_f = float(rev); u_f = float(units); p_f = float(price)
            if u_f > 0 and p_f > 0 and r_f > 0:
                expected = u_f * p_f
                ratio = r_f / expected if expected != 0 else float("nan")
                if not (ratio != ratio) and ratio >= 9:
                    corrected = False
                    for divisor in [10, 100, 1000]:
                        c_rev = r_f / divisor
                        if abs(c_rev - expected) / max(abs(expected), 1e-9) <= 0.05:
                            if _is_corrected(c_rev, _rev or "") and _rev:
                                df.at[idx, _rev] = c_rev
                                log_lines.append(f"outlier_decimal: row {idx} ÷{divisor} (formula-mismatch): {_rev}: {r_f:.2f}→{c_rev:.2f}")
                                outlier_corrections += 1
                            corrected = True
                            break
                    if not corrected and _rev and _is_corrected(expected, _rev or ""):
                        df.at[idx, _rev] = expected
                        log_lines.append(f"outlier_decimal: row {idx} formula-replace (formula-mismatch, ratio={ratio:.1f}): {_rev}: {r_f:.2f}→{expected:.2f}")
                        outlier_corrections += 1
            continue

        if not (rev_out or units_out or price_out):
            continue

        applied = False
        for divisor in [10, 100, 1000]:
            c_rev   = float(rev)   / divisor if rev_out   else (float(rev)   if not rev_null   else float("nan"))
            c_units = float(units) / divisor if units_out else (float(units) if not units_null else float("nan"))
            c_price = float(price) / divisor if price_out else (float(price) if not price_null else float("nan"))

            all_three = not (c_rev != c_rev) and not (c_units != c_units) and not (c_price != c_price)

            if all_three and c_units != 0 and c_price != 0:
                computed = c_units * c_price
                formula_ok = abs(c_rev - computed) / max(abs(c_rev), 1e-9) <= 0.05
                rev_fixed   = (not rev_out)   or _is_corrected(c_rev,   _rev or "")
                units_fixed = (not units_out) or _is_corrected(c_units, _u   or "")
                price_fixed = (not price_out) or _is_corrected(c_price, _p   or "")
                if formula_ok and rev_fixed and units_fixed and price_fixed:
                    changes = []
                    if rev_out   and _rev: df.at[idx, _rev] = c_rev;   changes.append(f"{_rev}: {float(rev):.2f}→{c_rev:.2f}")
                    if units_out and _u:   df.at[idx, _u]   = c_units; changes.append(f"{_u}: {float(units):.2f}→{c_units:.2f}")
                    if price_out and _p:   df.at[idx, _p]   = c_price; changes.append(f"{_p}: {float(price):.2f}→{c_price:.2f}")
                    log_lines.append(f"outlier_decimal: row {idx} ÷{divisor} (all-3): {'; '.join(changes)}")
                    outlier_corrections += len(changes)
                    applied = True
                    break

            if not all_three and rev_null and not (c_units != c_units) and not (c_price != c_price):
                rev_med = _medians.get(_rev or "", float("nan"))
                if not (rev_med != rev_med) and rev_med > 0 and c_units != 0 and c_price != 0:
                    derived_rev = c_units * c_price
                    units_fixed = (not units_out) or _is_corrected(c_units, _u or "")
                    price_fixed = (not price_out) or _is_corrected(c_price, _p or "")
                    if derived_rev <= 20 * rev_med and units_fixed and price_fixed:
                        changes = []
                        if units_out and _u: df.at[idx, _u] = c_units; changes.append(f"{_u}: {float(units):.2f}→{c_units:.2f}")
                        if price_out and _p: df.at[idx, _p] = c_price; changes.append(f"{_p}: {float(price):.2f}→{c_price:.2f}")
                        if changes:
                            log_lines.append(f"outlier_decimal: row {idx} ÷{divisor} (rev-null, derived={derived_rev:.2f}): {'; '.join(changes)}")
                            outlier_corrections += len(changes)
                            applied = True
                            break

            if not applied and not all_three:
                if rev_out and not (c_units != c_units) and not (c_price != c_price) and c_units != 0 and c_price != 0:
                    expected_rev = c_units * c_price
                    rev_fixed = _is_corrected(c_rev, _rev or "")
                    if abs(c_rev - expected_rev) / max(abs(expected_rev), 1e-9) <= 0.05 and rev_fixed:
                        df.at[idx, _rev] = c_rev
                        log_lines.append(f"outlier_decimal: row {idx} ÷{divisor} (rev-out): {_rev}: {float(rev):.2f}→{c_rev:.2f}")
                        outlier_corrections += 1
                        applied = True
                        break

    # ------------------------------------------------------------------ #
    # STEP A — Formula-based imputation (revenue = units × price)         #
    # ------------------------------------------------------------------ #
    rev_col_exists = revenue_col in df.columns
    units_col_exists = units_col in df.columns
    price_col_exists = price_col in df.columns

    for col in [revenue_col, units_col, price_col]:
        if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if rev_col_exists and units_col_exists and price_col_exists:
        for idx in df.index:
            rev = df.at[idx, revenue_col]
            units = df.at[idx, units_col]
            price = df.at[idx, price_col]

            rev_null = pd.isna(rev)
            units_null = pd.isna(units)
            price_null = pd.isna(price)

            mismatch_flag = df.at[idx, "revenue_mismatch"] if "revenue_mismatch" in df.columns else None
            if mismatch_flag is True or mismatch_flag == 1:
                continue

            if not units_null and not price_null and rev_null:
                result = units * price
                df.at[idx, revenue_col] = result
                log_lines.append(f"formula: {revenue_col} = {units:.2f} × {price:.2f} = {result:.2f} (row {idx})")
                formula_fills += 1

            elif not units_null and not rev_null and price_null and units != 0:
                result = rev / units
                df.at[idx, price_col] = result
                log_lines.append(f"formula: {price_col} = {rev:.2f} / {units:.2f} = {result:.2f} (row {idx})")
                formula_fills += 1

            elif not price_null and not rev_null and units_null and price != 0:
                result = rev / price
                df.at[idx, units_col] = result
                log_lines.append(f"formula: {units_col} = {rev:.2f} / {price:.2f} = {result:.2f} (row {idx})")
                formula_fills += 1

        rev = df[revenue_col]
        units = df[units_col]
        price = df[price_col]
        all_present = rev.notna() & units.notna() & price.notna()
        computed = units * price
        with np.errstate(divide="ignore", invalid="ignore"):
            pct_diff = np.where(
                computed != 0,
                np.abs(rev - computed) / np.abs(computed),
                0.0,
            )
        if "revenue_mismatch" not in df.columns:
            df["revenue_mismatch"] = False
        df.loc[all_present & (pd.Series(pct_diff, index=df.index) > 0.05), "revenue_mismatch"] = True

    # ------------------------------------------------------------------ #
    # STEP B — Pattern-based imputation                                   #
    # ------------------------------------------------------------------ #
    name_col_exists = name_col in df.columns
    email_col_exists = email_col in df.columns

    if name_col_exists and email_col_exists:
        for idx in df.index:
            name_val = df.at[idx, name_col]
            email_val = df.at[idx, email_col]
            if _is_null_or_empty(name_val) and not _is_null_or_empty(email_val):
                email_str = str(email_val).strip()
                local = email_str.split("@")[0]
                if _NAME_EMAIL_RE.match(local):
                    derived = " ".join(part.title() for part in local.split("."))
                    df.at[idx, name_col] = derived
                    log_lines.append(f"pattern: {name_col} derived from email '{email_str}' → '{derived}' (row {idx})")
                    pattern_name_fills += 1

    if email_col_exists and name_col_exists:
        non_null_emails = df[email_col].dropna().astype(str)
        non_null_emails = non_null_emails[non_null_emails.str.contains("@", na=False)]
        if len(non_null_emails) > 0:
            domains = non_null_emails.str.split("@").str[-1].str.strip()
            domain_mode = domains.mode()
            if not domain_mode.empty:
                dominant_domain = domain_mode.iloc[0]
                dominant_count = (domains == dominant_domain).sum()
                domain_dominance = dominant_count / len(non_null_emails)
            else:
                dominant_domain = None
                domain_dominance = 0.0
        else:
            dominant_domain = None
            domain_dominance = 0.0

        if dominant_domain and domain_dominance > 0.80:
            for idx in df.index:
                email_val = df.at[idx, email_col]
                name_val = df.at[idx, name_col]
                if _is_null_or_empty(email_val) and not _is_null_or_empty(name_val):
                    name_str = str(name_val).strip()
                    parts = name_str.split()
                    if len(parts) == 2:
                        firstname, lastname = parts[0].lower(), parts[1].lower()
                        derived = f"{firstname}.{lastname}@{dominant_domain}"
                        df.at[idx, email_col] = derived
                        log_lines.append(f"pattern: {email_col} derived from name '{name_str}' → '{derived}' (row {idx})")
                        pattern_email_fills += 1

    # ------------------------------------------------------------------ #
    # STEP C — Statistical fallback (mode / median)                       #
    # ------------------------------------------------------------------ #
    for col in categorical_columns:
        if col not in df.columns:
            continue
        null_mask = df[col].isna()
        null_count = null_mask.sum()
        if null_count == 0:
            continue
        if df[col].notna().sum() == 0:
            log_lines.append(f"stat_mode: {col} skipped (entirely null)")
            continue
        mode_val = df[col].mode().iloc[0]
        df.loc[null_mask, col] = mode_val
        log_lines.append(f"stat_mode: {col} filled {null_count} nulls with mode='{mode_val}'")
        statistical_mode_fills += null_count

    for col in numeric_columns:
        if col not in df.columns:
            continue
        null_mask = df[col].isna()
        null_count = null_mask.sum()
        if null_count == 0:
            continue
        if df[col].notna().sum() == 0:
            log_lines.append(f"stat_median: {col} skipped (entirely null)")
            continue
        skip_mask = pd.Series(False, index=df.index)
        if "negative_flag" in df.columns:
            skip_mask |= df["negative_flag"].fillna(False).astype(bool)
        if "revenue_mismatch" in df.columns:
            skip_mask |= df["revenue_mismatch"].fillna(False).astype(bool)
        fill_mask = null_mask & ~skip_mask
        fill_count = fill_mask.sum()
        if fill_count == 0:
            continue
        median_val = df[col].median()
        df.loc[fill_mask, col] = median_val
        log_lines.append(f"stat_median: {col} filled {fill_count} nulls with median={median_val:.4f}")
        statistical_median_fills += fill_count

    # ------------------------------------------------------------------ #
    # STEP D — Drop damaged rows (>= 3 critical nulls)                   #
    # ------------------------------------------------------------------ #
    actual_critical = [c for c in critical_columns if c in df.columns]
    rows_to_drop: list[int] = []
    for idx in df.index:
        null_cols = [c for c in actual_critical if pd.isna(df.at[idx, c])]
        n = len(null_cols)
        if n >= 3:
            order_id_val = df.at[idx, "order_id"] if "order_id" in df.columns else "unknown"
            log_lines.append(f"drop: row {idx} (order_id={order_id_val}) — {n} critical nulls: {null_cols}")
            rows_to_drop.append(idx)

    df = df.drop(index=rows_to_drop).reset_index(drop=True)
    rows_dropped = len(rows_to_drop)

    null_rates_after = {
        col: round(float(df[col].isna().mean() * 100), 2)
        for col in df.columns
    }

    summary = {
        "outlier_corrections": outlier_corrections,
        "formula_fills": formula_fills,
        "pattern_name_fills": pattern_name_fills,
        "pattern_email_fills": pattern_email_fills,
        "statistical_mode_fills": statistical_mode_fills,
        "statistical_median_fills": statistical_median_fills,
        "rows_dropped": rows_dropped,
        "rows_remaining": len(df),
        "null_rates_after": null_rates_after,
    }
    return df, summary, log_lines


def make_impute_tool(cleaned_dir: Path):

    @tool(
        "impute_data",
        (
            "Fill missing values using formula derivation, pattern matching, and statistical "
            "fallback — in that order. Run AFTER correct_dates and BEFORE finalize.\n\n"
            "Pass A — Formula: derive total_revenue / unit_price / units_sold from the other two "
            "when exactly one is missing. Also flags revenue_mismatch where stored vs computed "
            "differs by more than 5%.\n\n"
            "Pass B — Pattern: derive customer_name from 'first.last@domain' email (title-case), "
            "and derive customer_email from 'Firstname Lastname' when a dominant domain (>80% of "
            "non-null emails) can be identified.\n\n"
            "Pass C — Statistical: fill categorical nulls with column mode, numeric nulls with "
            "column median (skips anomaly-flagged rows).\n\n"
            "Pass D — Drop: remove rows where 3 or more critical columns are still null after "
            "all passes."
        ),
        {
            "type": "object",
            "properties": {
                "critical_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columns checked for the 3-null drop threshold.",
                },
                "email_column": {"type": "string", "description": "Default: 'customer_email'"},
                "name_column": {"type": "string", "description": "Default: 'customer_name'"},
                "revenue_column": {"type": "string", "description": "Default: 'total_revenue'"},
                "units_column": {"type": "string", "description": "Default: 'units_sold'"},
                "price_column": {"type": "string", "description": "Default: 'unit_price'"},
                "categorical_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columns to fill with mode. Default: ['region','product','channel']",
                },
                "numeric_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columns to fill with median. Default: ['units_sold','unit_price','total_revenue']",
                },
            },
            "required": [],
        },
    )
    async def impute_data(args: dict[str, Any]) -> dict[str, Any]:
        src = cleaned_dir / "cleaned.parquet"
        if not src.exists():
            return {
                "content": [{"type": "text", "text": "ERROR: cleaned.parquet not found. Run clean_data and correct_dates first."}],
                "is_error": True,
            }

        df = pd.read_parquet(src)

        critical_columns = args.get("critical_columns", _DEFAULT_CRITICAL_COLUMNS)
        email_col = args.get("email_column", _DEFAULT_EMAIL_COLUMN)
        name_col = args.get("name_column", _DEFAULT_NAME_COLUMN)
        revenue_col = args.get("revenue_column", _DEFAULT_REVENUE_COLUMN)
        units_col = args.get("units_column", _DEFAULT_UNITS_COLUMN)
        price_col = args.get("price_column", _DEFAULT_PRICE_COLUMN)
        categorical_columns = args.get("categorical_columns", _DEFAULT_CATEGORICAL_COLUMNS)
        numeric_columns = args.get("numeric_columns", _DEFAULT_NUMERIC_COLUMNS)

        df, summary, log_lines = _impute_logic(
            df,
            critical_columns=critical_columns,
            email_col=email_col,
            name_col=name_col,
            revenue_col=revenue_col,
            units_col=units_col,
            price_col=price_col,
            categorical_columns=categorical_columns,
            numeric_columns=numeric_columns,
        )

        df.to_parquet(src, index=False)

        log_header = [
            "=== impute_data ===",
            f"outlier_corrections     : {summary['outlier_corrections']}",
            f"formula_fills           : {summary['formula_fills']}",
            f"pattern_name_fills      : {summary['pattern_name_fills']}",
            f"pattern_email_fills     : {summary['pattern_email_fills']}",
            f"statistical_mode_fills  : {summary['statistical_mode_fills']}",
            f"statistical_median_fills: {summary['statistical_median_fills']}",
            f"rows_dropped            : {summary['rows_dropped']}",
            f"rows_remaining          : {summary['rows_remaining']}",
        ]
        full_log = log_header + log_lines

        log_path = cleaned_dir / "cleaning_log.txt"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(full_log) + "\n")

        null_rates_str = "\n".join(f"  {col}: {pct}%" for col, pct in summary["null_rates_after"].items())
        result_text = (
            f"impute_data complete:\n"
            f"  formula fills          : {summary['formula_fills']}\n"
            f"  pattern name fills     : {summary['pattern_name_fills']}\n"
            f"  pattern email fills    : {summary['pattern_email_fills']}\n"
            f"  statistical mode fills : {summary['statistical_mode_fills']}\n"
            f"  statistical median fills: {summary['statistical_median_fills']}\n"
            f"  rows dropped           : {summary['rows_dropped']}\n"
            f"  rows remaining         : {summary['rows_remaining']}\n"
            f"\nNull rates after imputation:\n{null_rates_str}"
        )

        return {"content": [{"type": "text", "text": result_text}]}

    return impute_data
