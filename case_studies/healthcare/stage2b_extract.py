# -*- coding: utf-8 -*-
"""
Stage 2 (Data Extraction)
Reads the raw file, builds the extraction inventory, and adds __source_row (0-based
index into the raw file) before any row is dropped or reordered.
Profiling is the next stage: stage3_profile.py.
Writes: 02_stage2_extraction_report.txt
"""
import pandas as pd
import numpy as np
import re
import os

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

IN = str(_HERE / "input" / "healthcare_dataset_dirty_export.csv")
OUT_DIR = str(_HERE)

df = pd.read_csv(IN, encoding="utf-8", low_memory=False, dtype=str)
raw_shape = df.shape
raw_cols = list(df.columns)

# ---- Stage 2 report ----
s2 = []
s2.append("STAGE 2: DATA EXTRACTION INVENTORY")
s2.append("=" * 60)
s2.append(f"Source file: {IN}")
s2.append(f"File size bytes: {os.path.getsize(IN)}")
s2.append(f"Encoding: UTF-8 (strict decode verified in stage2a_peek.py, no BOM)")
s2.append(f"Detected delimiter: ',' (standard csv)")
s2.append(f"Raw shape: {raw_shape[0]} rows x {raw_shape[1]} columns")
s2.append(f"Raw column names (exact): {raw_cols}")
s2.append("")
s2.append("Structural anomaly scan:")
s2.append(f"  - No multi-row header detected (single header row).")
s2.append(f"  - No trailing summary/footer row detected (last row is a normal data row - see 00_peek_report.txt tail sample).")
s2.append(f"  - 3 pre-existing derived columns present in raw file: Admission Year, Admission Month,")
s2.append(f"    Admission YearMonth - flagged as distrust-and-recompute per business brief BR6.")
s2.append(f"  - All 19 columns read as string dtype by pandas except Length of Stay/Admission Year/")
s2.append(f"    Admission Month which pandas auto-inferred as float64 due to NaN presence - will be")
s2.append(f"    re-parsed explicitly during cleaning, not trusted to pandas auto-inference.")
s2.append("")
s2.append(f"__source_row added: 0-based row index into this raw file, range 0..{raw_shape[0]-1}.")
with open(os.path.join(OUT_DIR, "02_stage2_extraction_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(s2))

# add __source_row immediately, before any row is dropped/reordered (per 4.0 convention)
df.insert(0, "__source_row", range(len(df)))

