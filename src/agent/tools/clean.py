"""Stage 3: Apply cleaning operations chosen by the agent.

The AGENT decides which ops to run based on the profile; this tool just
executes them deterministically. This is the hybrid intelligence pattern
in action: Claude handles judgment, Python handles execution.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from claude_agent_sdk import tool


def _apply_op(df: pd.DataFrame, op: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    """Apply one operation; return (new_df, log_line)."""
    name = op.get("op")

    if name == "drop_duplicates":
        before = len(df)
        df = df.drop_duplicates().reset_index(drop=True)
        return df, f"drop_duplicates: removed {before - len(df)} rows"

    if name == "drop_nulls":
        cols = op.get("columns")  # None = drop rows with any null
        before = len(df)
        df = df.dropna(subset=cols).reset_index(drop=True)
        return df, f"drop_nulls(columns={cols or 'any'}): removed {before - len(df)} rows"

    if name == "fill_nulls":
        col = op["column"]
        strategy = op.get("strategy", "value")
        if strategy == "value":
            v = op["value"]
            df[col] = df[col].fillna(v)
            detail = f"value={v}"
        elif strategy == "mean":
            v = df[col].mean()
            df[col] = df[col].fillna(v)
            detail = f"mean={v:.4f}"
        elif strategy == "median":
            v = df[col].median()
            df[col] = df[col].fillna(v)
            detail = f"median={v:.4f}"
        elif strategy == "mode":
            mode = df[col].mode()
            v = mode.iloc[0] if not mode.empty else None
            df[col] = df[col].fillna(v)
            detail = f"mode={v}"
        else:
            return df, f"fill_nulls: unknown strategy '{strategy}'"
        return df, f"fill_nulls(col={col}, {detail})"

    if name == "cap_outliers_iqr":
        col = op["column"]
        k = float(op.get("k", 1.5))
        q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - k * iqr, q3 + k * iqr
        below = int((df[col] < lo).sum())
        above = int((df[col] > hi).sum())
        df[col] = df[col].clip(lower=lo, upper=hi)
        return df, f"cap_outliers_iqr(col={col}, k={k}): clipped {below} below {lo:.2f}, {above} above {hi:.2f}"

    if name == "cast_dtype":
        col = op["column"]
        target = op["dtype"]
        if target == "datetime":
            fmt = op.get("format", "mixed")
            dayfirst = bool(op.get("dayfirst", True))
            before_nulls = int(df[col].isna().sum())
            df[col] = pd.to_datetime(df[col], errors="coerce", format=fmt, dayfirst=dayfirst)
            after_nulls = int(df[col].isna().sum())
            new_nulls = after_nulls - before_nulls
            detail = f"format={fmt}, dayfirst={dayfirst}"
            if new_nulls > 0:
                detail += f", {new_nulls} values failed to parse (became NaT)"
            return df, f"cast_dtype(col={col}, dtype=datetime, {detail})"
        elif target == "int":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        elif target == "float":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif target == "string":
            df[col] = df[col].astype("string")
        else:
            return df, f"cast_dtype: unknown dtype '{target}'"
        return df, f"cast_dtype(col={col}, dtype={target})"

    if name == "normalize_string":
        col = op["column"]
        df[col] = df[col].astype("string").str.strip().str.lower()
        return df, f"normalize_string(col={col})"

    if name == "rename":
        mapping = op["mapping"]
        df = df.rename(columns=mapping)
        return df, f"rename({mapping})"

    if name == "nfkc_normalize":
        col = op["column"]

        def _nfkc(v):
            if pd.isna(v):
                return v
            s = unicodedata.normalize("NFKC", str(v))
            s = s.strip()
            s = re.sub(r" {2,}", " ", s)
            return s

        df[col] = df[col].map(_nfkc)
        return df, f"nfkc_normalize(col={col})"

    if name == "clean_names":
        col = op["column"]
        NULL_DISGUISES = {"null", "n/a", "na", "unknown", "none", "nan", ""}
        HONORIFICS = re.compile(r"^\s*(mr\.?|mrs\.?|ms\.?|dr\.?|prof\.?)\s+", re.IGNORECASE)

        def _clean_name(v):
            if pd.isna(v):
                return v
            s = str(v).strip().rstrip(",").strip()
            if s.lower() in NULL_DISGUISES:
                return np.nan
            s = re.sub(r"(?<=[a-zA-Z])\.(?=[A-Z])", " ", s)
            s = HONORIFICS.sub("", s).strip()
            s = s.title()
            s = re.sub(r" {2,}", " ", s).strip()
            return s if s else np.nan

        df[col] = df[col].map(_clean_name)
        return df, f"clean_names(col={col})"

    if name == "validate_emails":
        col = op["column"]
        flag_col = op.get("flag_column", "email_valid")
        EMAIL_RE = re.compile(r"^[\w.+\-]+@[\w\-]+\.[\w.\-]+$")
        valid_count = invalid_count = null_count = 0
        new_vals = []
        new_flags = []
        for v in df[col]:
            if pd.isna(v) or str(v).strip() == "":
                new_vals.append(np.nan)
                new_flags.append(np.nan)
                null_count += 1
            else:
                cleaned = str(v).lower().replace(" ", "")
                if EMAIL_RE.match(cleaned):
                    new_vals.append(cleaned)
                    new_flags.append(True)
                    valid_count += 1
                else:
                    new_vals.append(np.nan)
                    new_flags.append(False)
                    invalid_count += 1
        df[col] = new_vals
        df[flag_col] = new_flags
        return df, f"validate_emails(col={col}): valid={valid_count}, invalid={invalid_count}, null={null_count}"

    if name == "normalize_phones":
        col = op["column"]
        NULL_PHONE = {"?", "-", "n/a", "na", "not provided", "nan", "none", ""}

        def _norm_phone(v):
            if pd.isna(v):
                return np.nan
            s = str(v).strip()
            if s.lower() in NULL_PHONE:
                return np.nan
            s = re.sub(r"^\+91[-\s]?", "", s)
            s = re.sub(r"^91(?=\d{10}$)", "", s)
            digits = re.sub(r"\D", "", s)
            if len(digits) > 10:
                digits = digits[-10:]
            return digits if len(digits) == 10 else np.nan

        normalized = df[col].map(_norm_phone)
        n_nulled = int((normalized.isna() & df[col].notna()).sum())
        df[col] = normalized
        return df, f"normalize_phones(col={col}): nulled_invalid={n_nulled}"

    if name == "fix_region":
        col = op["column"]
        REGION_MAP = {
            "east": "East", "esat": "East", "eaast": "East", "est": "East",
            "north": "North", "nort": "North", "norh": "North",
            "south": "South", "sourh": "South", "sout": "South", "souht": "South",
            "west": "West", "wst": "West", "wesst": "West",
            "north-east": "North-East", "northeast": "North-East",
            "north east": "North-East", "north_east": "North-East",
            "norht-east": "North-East", "norh-east": "North-East",
        }
        NULL_DISGUISES = {"-", "n/a", "na", "null", "none", "nan", ""}

        def _fix_region(v):
            if pd.isna(v):
                return np.nan
            s = str(v).strip().lower()
            if s in NULL_DISGUISES:
                return np.nan
            return REGION_MAP.get(s, np.nan)

        before_nulls = int(df[col].isna().sum())
        df[col] = df[col].map(_fix_region)
        after_nulls = int(df[col].isna().sum())
        return df, f"fix_region(col={col}): mapped {len(df) - after_nulls} rows, {after_nulls} null after"

    if name == "fix_product":
        col = op["column"]
        PRODUCT_MAP = {v.lower(): v for v in ["Alpha", "Beta", "Delta", "Gamma"]}
        NULL_DISGUISES = {"n/a", "na", "null", "none", "nan", "unknown", ""}

        def _fix_product(v):
            if pd.isna(v):
                return np.nan
            s = str(v).strip().lower()
            if s in NULL_DISGUISES:
                return np.nan
            return PRODUCT_MAP.get(s, np.nan)

        df[col] = df[col].map(_fix_product)
        return df, f"fix_product(col={col})"

    if name == "fix_channel":
        col = op["column"]
        CHANNEL_MAP = {
            "online": "Online", "on line": "Online", "on-line": "Online",
            "wholesale": "Wholesale",
            "retail": "Retail", "brick & mortar": "Retail",
            "b2b": "B2B",
            "b2c": "B2C",
        }
        NULL_DISGUISES = {"n/a", "na", "null", "none", "nan", "-", ""}

        def _fix_channel(v):
            if pd.isna(v):
                return np.nan
            s = str(v).strip().lower()
            if s in NULL_DISGUISES:
                return np.nan
            return CHANNEL_MAP.get(s, np.nan)

        df[col] = df[col].map(_fix_channel)
        return df, f"fix_channel(col={col})"

    if name == "flag_negatives":
        cols_to_check = op.get("columns", [])
        flag_col = op.get("flag_column", "negative_flag")
        if flag_col not in df.columns:
            df[flag_col] = False
        count = 0
        for c in cols_to_check:
            if c not in df.columns:
                continue
            mask = pd.to_numeric(df[c], errors="coerce") < 0
            df.loc[mask, flag_col] = True
            count += int(mask.sum())
        return df, f"flag_negatives(cols={cols_to_check}): {count} negative values flagged"

    return df, f"WARNING: unknown op '{name}', skipped"


def make_clean_tool(landing_dir: Path, cleaned_dir: Path):

    @tool(
        "clean_data",
        (
            "Apply a list of cleaning operations to the extracted dataset and write the "
            "cleaned Parquet. Operations run in order. Supported ops:\n"
            "  - drop_duplicates\n"
            "  - drop_nulls (columns?: list[str])\n"
            "  - fill_nulls (column, strategy: value|mean|median|mode, value? for 'value')\n"
            "  - cap_outliers_iqr (column, k=1.5)\n"
            "  - cast_dtype (column, dtype: datetime|int|float|string; for datetime, "
            "    optional format=\"mixed\"|<strftime> and dayfirst=True|False — defaults "
            "    are format='mixed' and dayfirst=True, which handles ISO + DD/MM/YYYY "
            "    + MM/DD/YYYY correctly)\n"
            "  - normalize_string (column)\n"
            "  - rename (mapping: dict[str,str])\n"
            "  - nfkc_normalize (column) — NFKC unicode normalize, strip whitespace, "
            "    collapse internal spaces; run on ALL text columns before other ops\n"
            "  - clean_names (column) — strip honorifics (Mr/Mrs/Ms/Dr/Prof), fix "
            "    dot-separators (Sneha.Gupta->Sneha Gupta), replace null disguises, "
            "    title-case; run on customer_name\n"
            "  - validate_emails (column, flag_column='email_valid') — lowercase, strip "
            "    spaces, regex-validate; invalid emails -> NaN; adds flag_column boolean\n"
            "  - normalize_phones (column) — strip +91/91 country prefix, keep last 10 "
            "    digits; non-10-digit results -> NaN\n"
            "  - fix_region (column) — map all typos/variants to exactly 5 canonical "
            "    values: East, North, South, West, North-East\n"
            "  - fix_product (column) — map all case variants to: Alpha, Beta, Delta, "
            "    Gamma; null disguises -> NaN\n"
            "  - fix_channel (column) — map to: Online, Wholesale, Retail, B2B, B2C; "
            "    'Brick & Mortar' -> Retail; null disguises -> NaN\n"
            "  - flag_negatives (columns: list[str], flag_column='negative_flag') — add "
            "    boolean flag column for rows with any negative value; does NOT remove rows\n"
            "Decide ops based on the profile and the brief."
        ),
        {
            "type": "object",
            "properties": {
                "operations": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of cleaning op dicts to apply in order.",
                },
            },
            "required": ["operations"],
        },
    )
    async def clean_data(args: dict[str, Any]) -> dict[str, Any]:
        cleaned_src = cleaned_dir / "cleaned.parquet"
        raw_src = landing_dir / "extracted.parquet"
        src = cleaned_src if cleaned_src.exists() else raw_src
        if not src.exists():
            return {
                "content": [{"type": "text", "text": "ERROR: no input parquet found. Run extract_csv first."}],
                "is_error": True,
            }
        df = pd.read_parquet(src)
        ops = args.get("operations", [])
        log = [f"start: {len(df)} rows x {len(df.columns)} cols"]
        for op in ops:
            try:
                df, line = _apply_op(df, op)
                log.append(line)
            except Exception as e:  # noqa: BLE001
                log.append(f"ERROR on op {op}: {e}")
        log.append(f"end:   {len(df)} rows x {len(df.columns)} cols")

        out = cleaned_dir / "cleaned.parquet"
        df.to_parquet(out, index=False)
        log_path = cleaned_dir / "cleaning_log.txt"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(log) + "\n")
        return {"content": [{"type": "text", "text": "Cleaning log:\n" + "\n".join(log)}]}

    return clean_data
