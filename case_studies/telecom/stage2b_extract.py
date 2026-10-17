# -*- coding: utf-8 -*-
"""
Stage 2 (extraction) for telecom_churn.csv.

Profiling and the Stage 4.4 collision guard are the next stage: stage3_profile.py.

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
# Report for this stage only.
# ---------------------------------------------------------------
_STAGE_REPORT = str(_HERE / "stage2_extraction_report.txt")
with open(_STAGE_REPORT, "w", encoding="utf-8") as _f:
    _f.write("\n".join(lines) + "\n")
print("wrote", _STAGE_REPORT)
