"""Stage 4: Fix impossible calendar dates and flag suspicious ones.

Can be called in two modes:
  - Before cast_dtype: column is still a string — snaps impossible dates in the
    string representation, then casts to datetime.
  - After cast_dtype: column is already datetime — NaT values from impossible
    dates cannot be recovered here, but valid Timestamps are flagged as
    suspicious (future, far-past, far-future).

The pipeline spec calls for this tool AFTER cast_dtype. Because pandas already
converts impossible dates (Feb 29 in non-leap years, day 31 in 30-day months)
to NaT before this tool runs, this tool also performs a pre-parse phase: if the
column is object/string dtype it snaps and casts in one step. If the column is
already datetime, it only flags (NaTs from impossible dates are irretrievably
lost by that point — the agent should call correct_dates on the raw string
column if snap recovery is needed).
"""
from __future__ import annotations

import calendar
import datetime
import re
from pathlib import Path
from typing import Any

import pandas as pd
from claude_agent_sdk import tool


_THIRTY_DAY_MONTHS = {4, 6, 9, 11}  # Apr, Jun, Sep, Nov

_DATE_SLASH_RE = re.compile(
    r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})"
)


def _is_leap_year(year: int) -> bool:
    return calendar.isleap(year)


def _snap_date_string(date_str: str) -> tuple[str, str | None]:
    """
    Attempt to snap an impossible date string to the nearest valid date.
    Returns (possibly_corrected_string, snap_log_or_None).
    Only handles DD/MM/YYYY-style strings where dayfirst is assumed.
    """
    s = date_str.strip()
    m = _DATE_SLASH_RE.match(s)
    if not m:
        return s, None

    sep = s[len(m.group(1))]
    d_str, mo_str, yr_str = m.group(1), m.group(2), m.group(3)
    try:
        day = int(d_str)
        month = int(mo_str)
        year = int(yr_str) if len(yr_str) == 4 else 2000 + int(yr_str)
    except ValueError:
        return s, None

    if month < 1 or month > 12:
        return s, None

    snap_log = None
    new_day = day

    if month == 2 and day == 29 and not _is_leap_year(year):
        new_day = 28
        snap_log = f"date_snap: Feb29→Feb28 (non-leap year {year})"

    elif day == 31 and month in _THIRTY_DAY_MONTHS:
        month_name = calendar.month_name[month]
        new_day = 30
        snap_log = f"date_snap: day31→day30 in {month_name} {year}"

    elif month > 12 and day <= 12:
        swapped_day, swapped_month = month, day
        if 1 <= swapped_month <= 12 and 1 <= swapped_day <= 31:
            try:
                import datetime as _dt
                _dt.date(year, swapped_month, swapped_day)
                corrected = f"{swapped_day:02d}{sep}{swapped_month:02d}{sep}{yr_str}"
                rest = s[m.end():]
                return corrected + rest, f"date_snap: swapped month/day ({month}/{day}→{swapped_month}/{swapped_day})"
            except ValueError:
                pass

    if new_day != day:
        corrected = f"{new_day:02d}{sep}{month:02d}{sep}{yr_str}"
        rest = s[m.end():]
        return corrected + rest, snap_log

    return s, None


def _correct_dates_logic(
    df: pd.DataFrame,
    date_col: str,
) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    """Core correction logic, separated so it can be tested without the SDK."""
    log_lines: list[str] = []

    if date_col not in df.columns:
        return df, {
            "error": f"Column '{date_col}' not found. Available: {list(df.columns)}"
        }, log_lines

    series = df[date_col]
    is_string_col = not pd.api.types.is_datetime64_any_dtype(series)

    df = df.copy()
    if "date_flag" not in df.columns:
        df["date_flag"] = ""
    else:
        df["date_flag"] = df["date_flag"].fillna("").astype(str)

    today = pd.Timestamp(datetime.date.today())

    snapped = 0
    flagged_future = 0
    flagged_far_past = 0
    flagged_far_future = 0
    rows_processed = 0

    if is_string_col:
        str_series = series.astype(str).str.strip()
        sentinels = {"nan", "none", "null", "n/a", "na", "?", "-", "tbd", ""}
        str_series = str_series.where(
            ~str_series.str.lower().isin(sentinels), other=pd.NA
        )

        new_strings = str_series.copy()
        for idx, val in str_series.items():
            if pd.isna(val):
                continue
            snapped_str, snap_log = _snap_date_string(str(val))
            if snap_log:
                new_strings.at[idx] = snapped_str
                log_lines.append(f"{snap_log} at row {idx} (original='{val}')")
                snapped += 1
                existing = df.at[idx, "date_flag"] if "date_flag" in df.columns else ""
                existing_str = str(existing) if pd.notna(existing) else ""
                df.at[idx, "date_flag"] = (existing_str + "|date_snapped").lstrip("|") if existing_str else "date_snapped"

        df[date_col] = pd.to_datetime(
            new_strings, errors="coerce", format="mixed", dayfirst=True
        )

    dt_series = df[date_col]

    if not pd.api.types.is_datetime64_any_dtype(dt_series):
        return df, {
            "error": (
                f"Column '{date_col}' could not be converted to datetime. "
                "Check the column values."
            )
        }, log_lines

    non_null = dt_series.dropna()
    if non_null.empty:
        median_year = today.year
    else:
        median_year = int(non_null.dt.year.median())

    new_dates = dt_series.copy()
    new_flags = df["date_flag"].copy()

    for idx, ts in dt_series.items():
        if pd.isna(ts):
            continue

        rows_processed += 1
        corrected = ts
        snap_log = None

        if ts.month == 2 and ts.day == 29 and not _is_leap_year(ts.year):
            corrected = ts.replace(day=28)
            snap_log = (
                f"date_snap: Feb29→Feb28 (non-leap year) at row {idx} "
                f"(original={ts.date()})"
            )
        elif ts.day == 31 and ts.month in _THIRTY_DAY_MONTHS:
            month_name = calendar.month_name[ts.month]
            corrected = ts.replace(day=30)
            snap_log = (
                f"date_snap: day31→day30 in {month_name} at row {idx} "
                f"(original={ts.date()})"
            )

        if snap_log:
            new_dates.at[idx] = corrected
            log_lines.append(snap_log)
            snapped += 1

        eval_ts = corrected
        flags: list[str] = []

        if eval_ts > today + pd.Timedelta(days=1):
            flags.append("future_date")
            flagged_future += 1

        if eval_ts.year < (median_year - 10):
            flags.append("year_far_past")
            flagged_far_past += 1

        if eval_ts.year > (median_year + 5):
            flags.append("year_far_future")
            flagged_far_future += 1

        if flags:
            existing = new_flags.at[idx]
            if existing:
                combined = existing + "|" + "|".join(flags)
            else:
                combined = "|".join(flags)
            new_flags.at[idx] = combined
            log_lines.append(
                f"date_flag: row {idx} ({eval_ts.date()}) → {combined}"
            )

    df[date_col] = new_dates
    df["date_flag"] = new_flags

    summary = {
        "snapped": snapped,
        "flagged_future": flagged_future,
        "flagged_far_past": flagged_far_past,
        "flagged_far_future": flagged_far_future,
        "rows_processed": rows_processed,
        "median_year_used": median_year,
        "log_lines": log_lines,
    }
    return df, summary, log_lines


def make_correct_dates_tool(cleaned_dir: Path):

    @tool(
        "correct_dates",
        (
            "Fix impossible calendar dates in the order_date column and flag suspicious ones. "
            "Run AFTER cast_dtype(datetime) and BEFORE impute_data.\n\n"
            "SAFE SNAPS (auto-corrected, original logged):\n"
            "  - Feb 29 in a non-leap year → Feb 28 same year\n"
            "  - Day 31 in a 30-day month (Apr/Jun/Sep/Nov) → day 30\n"
            "  If the column is still a string (not yet cast), snaps the string "
            "representation and then casts to datetime in one step.\n\n"
            "FLAGS ONLY (written to 'date_flag' column, date not modified):\n"
            "  - future_date: date is more than 1 day in the future\n"
            "  - year_far_past: year < (column median year − 10)\n"
            "  - year_far_future: year > (column median year + 5)\n"
            "Multiple flags on the same row are joined with '|'."
        ),
        {
            "type": "object",
            "properties": {
                "date_column": {
                    "type": "string",
                    "description": "Name of the date column to correct (default: 'order_date').",
                }
            },
            "required": [],
        },
    )
    async def correct_dates(args: dict[str, Any]) -> dict[str, Any]:
        src = cleaned_dir / "cleaned.parquet"
        if not src.exists():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "ERROR: cleaned.parquet not found. "
                            "Run clean_data (pass 1) first."
                        ),
                    }
                ],
                "is_error": True,
            }

        date_col = args.get("date_column", "order_date")
        df = pd.read_parquet(src)

        df, summary, log_lines = _correct_dates_logic(df, date_col)

        if "error" in summary:
            return {
                "content": [{"type": "text", "text": f"ERROR: {summary['error']}"}],
                "is_error": True,
            }

        df.to_parquet(src, index=False)

        log_header = [
            f"=== correct_dates on '{date_col}' ===",
            f"rows_processed: {summary['rows_processed']}",
            f"snapped: {summary['snapped']}",
            f"flagged_future: {summary['flagged_future']}",
            f"flagged_far_past: {summary['flagged_far_past']}",
            f"flagged_far_future: {summary['flagged_far_future']}",
            f"median_year_used: {summary['median_year_used']}",
        ]
        full_log = log_header + log_lines

        log_path = cleaned_dir / "cleaning_log.txt"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(full_log) + "\n")

        result_text = (
            f"correct_dates complete:\n"
            f"  rows processed : {summary['rows_processed']}\n"
            f"  snapped        : {summary['snapped']}\n"
            f"  flagged future : {summary['flagged_future']}\n"
            f"  flagged far past: {summary['flagged_far_past']}\n"
            f"  flagged far future: {summary['flagged_far_future']}\n"
            f"  median year used: {summary['median_year_used']}\n"
        )
        if log_lines:
            result_text += "Details:\n" + "\n".join(log_lines)

        return {"content": [{"type": "text", "text": result_text}]}

    return correct_dates
