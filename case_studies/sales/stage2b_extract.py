#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
stage2b_extract.py -- Stage 2 (full extraction).

Loads the raw CSV the "safe" way established in stage2a_peek.py (encoding='utf-8-sig',
dtype=str, keep_default_na=False) and adds the __source_row identity column (spec 4.0)
immediately, before any row is dropped or reordered.

Profiling and the collision guard are the next stage: stage3_profile.py.
Writes: stage2_extraction_report.txt
"""
import os
import re
import pandas as pd
from thefuzz import utils as fuzz_utils

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

IN_PATH = str(_HERE / "input" / "messy_sales.csv")
OUT_DIR = str(_HERE)
REPORT = os.path.join(OUT_DIR, "02_profile_report.txt")
PICKLE_RAW = os.path.join(OUT_DIR, "_raw_with_source_row.pkl")

lines = []
def log(s=""):
    lines.append(str(s))

# ---- Stage 2: extraction ----
df = pd.read_csv(IN_PATH, encoding="utf-8-sig", dtype=str, keep_default_na=False)
df.insert(0, "__source_row", range(len(df)))  # 0-based row number in the raw file (spec 4.0)

log("=" * 78)
log("STAGE 2 -- FULL EXTRACTION")
log("=" * 78)
log(f"Loaded with encoding='utf-8-sig', dtype=str, keep_default_na=False")
log(f"Shape (rows, cols, excl. __source_row): ({df.shape[0]}, {df.shape[1]-1})")
log(f"Columns (raw, as-is): {[c for c in df.columns if c != '__source_row']}")

df.to_pickle(PICKLE_RAW)  # hand off to stage4_clean.py so it doesn't re-parse and can trust __source_row


# ---------------------------------------------------------------
# Report for this stage only.
# ---------------------------------------------------------------
_STAGE_REPORT = str(_HERE / "stage2_extraction_report.txt")
with open(_STAGE_REPORT, "w", encoding="utf-8") as _f:
    _f.write("\n".join(lines) + "\n")
print("wrote", _STAGE_REPORT)
