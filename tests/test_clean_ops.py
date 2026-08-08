"""Tests for the SHIPPED cleaning operations in src/agent/tools/clean.py.

Why this file exists
--------------------
`test_pipeline_tools.py` re-implements eight cleaning operations inline so it
can run without importing `clean.py`. That makes it an end-to-end check of the
*pipeline shape*, but it does not test the code this package actually ships —
if `_apply_op` regressed, those tests would still pass.

This module imports `_apply_op` directly and asserts against its real
behaviour, so a regression in the shipped implementation fails the build.
Every one of the 15 operations `_apply_op` supports is covered.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agent.tools.clean import _apply_op  # noqa: E402


def apply(df: pd.DataFrame, op: dict):
    """Run one op and return (df, log_line)."""
    return _apply_op(df.copy(), op)


# --------------------------------------------------------------------------
# 1-2. row-level operations
# --------------------------------------------------------------------------
def test_drop_duplicates_removes_exact_repeats():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    out, log = apply(df, {"op": "drop_duplicates"})
    assert len(out) == 2
    assert "removed 1 rows" in log


def test_drop_nulls_only_targets_named_columns():
    df = pd.DataFrame({"keep": [1, None, 3], "other": [None, None, None]})
    out, _ = apply(df, {"op": "drop_nulls", "columns": ["keep"]})
    assert len(out) == 2, "a null in an untargeted column must not drop the row"


# --------------------------------------------------------------------------
# 3. fill_nulls — all four strategies
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "strategy,extra,expected",
    [
        ("value", {"value": 0.0}, 0.0),
        ("mean", {}, 2.0),      # mean of [1, 3]
        ("median", {}, 2.0),    # median of [1, 3]
    ],
)
def test_fill_nulls_strategies(strategy, extra, expected):
    df = pd.DataFrame({"x": [1.0, None, 3.0]})
    out, _ = apply(df, {"op": "fill_nulls", "column": "x", "strategy": strategy, **extra})
    assert out["x"].iloc[1] == expected


def test_fill_nulls_mode_picks_most_frequent():
    df = pd.DataFrame({"c": ["a", "a", "b", None]})
    out, _ = apply(df, {"op": "fill_nulls", "column": "c", "strategy": "mode"})
    assert out["c"].iloc[3] == "a"


def test_fill_nulls_unknown_strategy_is_refused_not_guessed():
    df = pd.DataFrame({"x": [1.0, None]})
    out, log = apply(df, {"op": "fill_nulls", "column": "x", "strategy": "telepathy"})
    assert out["x"].isna().sum() == 1, "an unknown strategy must not invent a value"
    assert "unknown strategy" in log


# --------------------------------------------------------------------------
# 4-7. numeric / structural operations
# --------------------------------------------------------------------------
def test_cap_outliers_iqr_clips_both_tails():
    df = pd.DataFrame({"v": [10, 11, 12, 13, 14, 1000]})
    out, log = apply(df, {"op": "cap_outliers_iqr", "column": "v", "k": 1.5})
    assert out["v"].max() < 1000
    assert "clipped" in log


def test_cast_dtype_int_and_float_coerce_bad_values_to_null():
    df = pd.DataFrame({"n": ["1", "2", "not-a-number"]})
    out_i, _ = apply(df, {"op": "cast_dtype", "column": "n", "dtype": "int"})
    assert str(out_i["n"].dtype) == "Int64"
    assert pd.isna(out_i["n"].iloc[2])

    out_f, _ = apply(df, {"op": "cast_dtype", "column": "n", "dtype": "float"})
    assert pd.isna(out_f["n"].iloc[2])


def test_cast_dtype_datetime_reports_newly_created_nulls():
    """A silent NaT is the failure mode this log line exists to expose."""
    df = pd.DataFrame({"d": ["2025-01-05", "definitely not a date"]})
    out, log = apply(df, {"op": "cast_dtype", "column": "d", "dtype": "datetime"})
    assert out["d"].isna().sum() == 1
    assert "failed to parse" in log, "new NaTs must be reported, not swallowed"


def test_cast_dtype_unknown_target_is_rejected():
    df = pd.DataFrame({"x": [1]})
    _, log = apply(df, {"op": "cast_dtype", "column": "x", "dtype": "quaternion"})
    assert "unknown dtype" in log


def test_normalize_string_strips_and_lowercases():
    df = pd.DataFrame({"s": ["  HeLLo  ", "WORLD"]})
    out, _ = apply(df, {"op": "normalize_string", "column": "s"})
    assert list(out["s"]) == ["hello", "world"]


def test_rename_applies_mapping():
    df = pd.DataFrame({"old": [1]})
    out, _ = apply(df, {"op": "rename", "mapping": {"old": "new"}})
    assert list(out.columns) == ["new"]


# --------------------------------------------------------------------------
# 8-9. text normalisation
# --------------------------------------------------------------------------
def test_nfkc_normalize_collapses_runs_of_spaces_and_normalises_unicode():
    df = pd.DataFrame({"t": ["  A    B  ", "ﬁle"]})   # 'ﬁ' is the ligature U+FB01
    out, _ = apply(df, {"op": "nfkc_normalize", "column": "t"})
    assert out["t"].iloc[0] == "A B"
    assert out["t"].iloc[1] == "file"


def test_clean_names_strips_honorifics_and_titlecases():
    df = pd.DataFrame({"n": ["Dr. john smith", "  jane  DOE  ,"]})
    out, _ = apply(df, {"op": "clean_names", "column": "n"})
    assert out["n"].iloc[0] == "John Smith"
    assert out["n"].iloc[1] == "Jane Doe"


def test_clean_names_converts_null_disguises_to_real_nulls():
    df = pd.DataFrame({"n": ["unknown", "N/A", "none", ""]})
    out, _ = apply(df, {"op": "clean_names", "column": "n"})
    assert out["n"].isna().all(), "disguised nulls must become real nulls, not the string 'Unknown'"


# --------------------------------------------------------------------------
# 10-11. contact-field validation
# --------------------------------------------------------------------------
def test_validate_emails_flags_invalid_and_nulls_the_value():
    df = pd.DataFrame({"e": ["  JOHN@Example.COM ", "john at example dot com", None]})
    out, log = apply(df, {"op": "validate_emails", "column": "e"})
    assert out["e"].iloc[0] == "john@example.com"
    assert out["email_valid"].iloc[0] is True or out["email_valid"].iloc[0] == True  # noqa: E712
    assert pd.isna(out["e"].iloc[1]), "an invalid address must not survive as a value"
    assert out["email_valid"].iloc[1] == False  # noqa: E712
    assert "valid=1" in log and "invalid=1" in log and "null=1" in log


def test_normalize_phones_handles_country_code_and_rejects_short_numbers():
    df = pd.DataFrame({"p": ["+91 98765-43210", "(372) 586 2887", "12345", "n/a"]})
    out, log = apply(df, {"op": "normalize_phones", "column": "p"})
    assert out["p"].iloc[0] == "9876543210"
    assert out["p"].iloc[1] == "3725862887"
    assert pd.isna(out["p"].iloc[2]), "a 5-digit number is not a phone number"
    assert pd.isna(out["p"].iloc[3])
    assert "nulled_invalid=" in log


# --------------------------------------------------------------------------
# 12-14. closed code sets — the operations that must never guess
# --------------------------------------------------------------------------
def test_fix_region_maps_known_typos():
    df = pd.DataFrame({"r": ["Esat", "nort", "SOUTH", "north east"]})
    out, _ = apply(df, {"op": "fix_region", "column": "r"})
    assert list(out["r"]) == ["East", "North", "South", "North-East"]


def test_fix_region_nulls_unrecognised_values_rather_than_guessing():
    """The whole point of a closed code set: an unknown value becomes null, not a guess."""
    df = pd.DataFrame({"r": ["Atlantis", "-"]})
    out, _ = apply(df, {"op": "fix_region", "column": "r"})
    assert out["r"].isna().all()


def test_fix_product_and_fix_channel_use_explicit_maps():
    df = pd.DataFrame({"p": ["alpha", "zeta"], "c": ["on line", "carrier pigeon"]})
    out, _ = apply(df, {"op": "fix_product", "column": "p"})
    out, _ = apply(out, {"op": "fix_channel", "column": "c"})
    assert out["p"].iloc[0] == "Alpha"
    assert pd.isna(out["p"].iloc[1])
    assert out["c"].iloc[0] == "Online"
    assert pd.isna(out["c"].iloc[1])


# --------------------------------------------------------------------------
# 15. flagging rather than correcting
# --------------------------------------------------------------------------
def test_flag_negatives_flags_without_altering_the_value():
    df = pd.DataFrame({"amount": [10, -5], "qty": [1, 2]})
    out, log = apply(df, {"op": "flag_negatives", "columns": ["amount", "qty"]})
    assert list(out["negative_flag"]) == [False, True]
    assert out["amount"].iloc[1] == -5, "flag_negatives must not silently abs() the value"
    assert "1 negative values flagged" in log


def test_flag_negatives_skips_missing_columns_without_crashing():
    df = pd.DataFrame({"a": [-1]})
    out, _ = apply(df, {"op": "flag_negatives", "columns": ["a", "does_not_exist"]})
    assert out["negative_flag"].iloc[0] == True  # noqa: E712


# --------------------------------------------------------------------------
# contract: an unrecognised op is refused loudly and changes nothing
# --------------------------------------------------------------------------
def test_unknown_op_is_a_no_op_and_says_so():
    df = pd.DataFrame({"a": [1, 2]})
    out, log = apply(df, {"op": "summon_the_data_fairy"})
    pd.testing.assert_frame_equal(out, df)
    assert log.startswith("WARNING: unknown op")
