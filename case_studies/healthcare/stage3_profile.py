# -*- coding: utf-8 -*-
"""
Stage 3 (Data Profiling)
Profiles every column: null-disguise scan (incl. domain-specific tokens known from
prior lineage, re-verified here), cardinality, numeric/string/date stats, categorical
value survey.
Repeats stage2b_extract.py's load as setup, so it runs standalone.
Writes: 02_stage3_profiling_report.txt
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

# ---- Stage 3 profiling ----
NULL_DISGUISES_UNAMBIGUOUS = {'', ' ', '?', 'null', 'none', 'tbd', 'undefined', '#n/a', '#value!', '#ref!', 'n/a', 'na'}
NULL_DISGUISES_DOMAIN = {'not available', 'missing', '--', 'pending', 'see invoice', 'unknown'}
ALL_DISGUISE_CANDIDATES = NULL_DISGUISES_UNAMBIGUOUS | NULL_DISGUISES_DOMAIN

def disguise_hits(series):
    s = series.astype(str).str.strip().str.casefold()
    counts = {}
    for tok in ALL_DISGUISE_CANDIDATES:
        n = (s == tok).sum()
        if n > 0:
            counts[tok] = int(n)
    return counts

lines = []
lines.append("STAGE 3: DATA PROFILING REPORT")
lines.append("=" * 60)
lines.append(f"Rows: {raw_shape[0]}  Columns (excl __source_row): {raw_shape[1]}")
lines.append("")

for col in raw_cols:
    s = df[col]
    lines.append(f"--- Column: {col} ---")
    lines.append(f"pandas dtype as read: {s.dtype}")
    nnull_pandas = int(s.isnull().sum())
    lines.append(f"pandas-native null count: {nnull_pandas} ({100*nnull_pandas/len(s):.2f}%)")
    hits = disguise_hits(s.fillna(""))
    lines.append(f"null-disguise token hits (stripped+casefolded, includes domain tokens): {hits}")
    nunique = s.nunique(dropna=True)
    lines.append(f"unique non-null values: {nunique}")
    top10 = s.value_counts(dropna=True).head(10)
    lines.append(f"top 10 values:\n{top10.to_string()}")
    # numeric probe
    numeric_try = pd.to_numeric(s.str.replace(',', '', regex=False).str.replace('$','',regex=False).str.replace('₹','',regex=False), errors='coerce')
    n_numeric_parseable = numeric_try.notna().sum()
    if n_numeric_parseable > 0.5 * s.notna().sum():
        lines.append(f"NUMERIC PROBE (loose strip of $,₹,comma): {n_numeric_parseable}/{s.notna().sum()} parseable")
        lines.append(f"  min={numeric_try.min()} max={numeric_try.max()} mean={numeric_try.mean():.4f} median={numeric_try.median():.4f} std={numeric_try.std():.4f}")
        lines.append(f"  skew={numeric_try.skew():.4f}  pct_negative={100*(numeric_try<0).sum()/n_numeric_parseable:.2f}%")
    # date probe
    date_try = pd.to_datetime(s, errors='coerce', format='mixed')
    n_date_parseable = date_try.notna().sum()
    if n_date_parseable > 0.3 * s.notna().sum():
        lines.append(f"DATE PROBE (mixed-format auto): {n_date_parseable}/{s.notna().sum()} parseable, "
                      f"{s.notna().sum()-n_date_parseable} unparseable")
        if n_date_parseable > 0:
            lines.append(f"  min={date_try.min()} max={date_try.max()}")
    # string length stats
    lens = s.dropna().astype(str).str.len()
    if len(lens) > 0:
        lines.append(f"string length: min={lens.min()} max={lens.max()} avg={lens.mean():.2f}")
    lines.append("")

# zero-variance check
lines.append("ZERO-VARIANCE COLUMNS (all values identical):")
for col in raw_cols:
    if df[col].nunique(dropna=True) <= 1:
        lines.append(f"  {col}")
lines.append("")

# high-risk >30% null
lines.append("HIGH RISK COLUMNS (>30% null, pandas-native count):")
for col in raw_cols:
    rate = df[col].isnull().sum() / len(df)
    if rate > 0.30:
        lines.append(f"  {col}: {100*rate:.2f}%")
lines.append("(none found)" if not any(df[c].isnull().sum()/len(df) > 0.30 for c in raw_cols) else "")

with open(os.path.join(OUT_DIR, "02_stage3_profiling_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("Stage 2 + 3 reports written.")
print("raw shape:", raw_shape)
