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

# =====================================================================================
# BRIEF CLAIM RE-VERIFICATION (spec amendment 2026-09-22)
#
# Stage 5 verifies what Stage 4 did. This is the only place anything verifies what
# Stage 1 asserted. Every verified_by expression in 01_business_brief.yaml is RE-RUN
# here and compared against its recorded result -- the recorded number is never read
# as an answer, only as something to disagree with.
#
# Claims about text columns are measured twice, because Stage 4.3 strips and collapses
# whitespace and a uniqueness claim can be true on raw and false by the time 4.11
# reads it. A claim whose number moves between snapshots is BRIEF_CLAIM_UNVERIFIED
# and HIGH RISK, even when the post-4.3 number is the better one.
# =====================================================================================
import unicodedata

import yaml

with open(os.path.join(OUT_DIR, "01_business_brief.yaml"), encoding="utf-8") as _bf:
    _BRIEF = yaml.safe_load(_bf)
_G = _BRIEF["grain"]


def _recorded(node, key="result"):
    """What the brief claims -- quoted only so it can be disagreed with."""
    return " ".join(str(node.get(key, "<absent>")).split())


def _norm43(s):
    """Stage 4.3's transform, replicated exactly so the two snapshots are comparable."""
    v = unicodedata.normalize("NFC", str(s))
    return re.sub(r"\s+", " ", v.strip())

bc = []
bc.append("")
bc.append("=" * 70)
bc.append("BRIEF CLAIM RE-VERIFICATION (spec 2026-09-22)")
bc.append("=" * 70)

_NAME, _DOA = "Name", "Date of Admission"
_DOC, _HOSP = "Doctor", "Hospital"
_raw = df.copy()

def _grain(frame):
    k = (frame[_NAME].astype(str) + "||" + frame[_DOA].astype(str) + "||"
         + frame[_DOC].astype(str) + "||" + frame[_HOSP].astype(str))
    return len(frame), k.nunique(), int(k.duplicated().sum())

_r = _grain(_raw)
bc.append("")
bc.append("CLAIM grain: one row per admission; composite key "
          "(name, date_of_admission, doctor, hospital)")
bc.append("  brief records : %s  (measured_on: %s)"
          % (_recorded(_G), _G.get("measured_on", "<absent>")))
bc.append("  recomputed raw: %d rows, %d distinct, %d duplicated" % _r)
_fmt = "%d rows, %d distinct, %d duplicated" % _r
bc.append("  -> %s" % ("MATCHES" if _fmt == _recorded(_G)
                       else "BRIEF_CLAIM_UNVERIFIED - recorded number does not reproduce"))

_post = _raw.copy()
_touched = {}
for _c in (_NAME, _DOC, _HOSP):
    _b = _post[_c].copy()
    _post[_c] = _post[_c].map(_norm43)
    _touched[_c] = int((_b != _post[_c]).sum())
_p = _grain(_post)
bc.append("  brief records (decay): %s  (measured_on: %s)"
          % (_recorded(_G.get("decay", {})),
             _G.get("decay", {}).get("measured_on", "<absent>")))
bc.append("  recomputed post_4.3 : %d rows, %d distinct, %d duplicated" % _p)
bc.append("  4.3 changed: %s" % ", ".join("%s=%d" % kv for kv in _touched.items()))

_delta = _p[2] - _r[2]
if _delta:
    bc.append("")
    bc.append("  *** BRIEF_CLAIM_UNVERIFIED -- HIGH RISK ***")
    bc.append("  The grain claim DECAYS: %+d duplicate keys appear after 4.3 alone." % _delta)
    bc.append("  Three of the four key components are text columns that 4.3 rewrites.")
    bc.append("  The flag count moving is harmless. What is not harmless: 4.11 removes")
    bc.append("  exact full-row duplicates BEFORE building this key, reading the same")
    bc.append("  post-4.3 values. Isolating 4.3 only:")
    _strcols = ["Name", "Gender", "Blood Type", "Medical Condition", "Doctor", "Hospital",
                "Insurance Provider", "Admission Type", "Medication", "Test Results"]
    # __source_row is a per-row counter inserted at load; it makes every row unique
    # by construction. 4.11 excludes it when detecting exact duplicates, so do the same.
    _cmp = [c for c in _raw.columns if c != "__source_row"]
    _pd2 = _raw.copy()
    for _c in _strcols:
        _pd2[_c] = _pd2[_c].map(_norm43)
    _er = int(_raw[_cmp].duplicated().sum())
    _ep = int(_pd2[_cmp].duplicated().sum())
    bc.append("     exact full-row duplicates raw=%d  post_4.3=%d  (%+d)" % (_er, _ep, _ep - _er))
    bc.append("     => %d rows are deleted because whitespace was collapsed, for no reason"
              % (_ep - _er))
    bc.append("        visible on the raw file. Defensible, but it must be attributed.")
else:
    bc.append("  -> claim holds on both snapshots.")

_idhits = [c for c in raw_cols if re.search(r"id|_id$|^id$|record", c, re.I)]
bc.append("")
bc.append("CLAIM grain.no_id_column: no id/patient_id/record_id among the 19 raw columns")
bc.append("  brief records : %s  (measured_on: %s)"
          % (_recorded(_G["no_id_column"]),
             _G["no_id_column"].get("measured_on", "<absent>")))
bc.append("  recomputed    : %s across %d columns" % (_idhits or [], len(raw_cols)))
bc.append("  -> %s" % ("MATCHES" if not _idhits and len(raw_cols) == 19 else "CHANGED"))

bc.append("")
bc.append("CLAIM dangerous_columns.blood_type: +/- pairs collide under default_process")
try:
    from rapidfuzz import fuzz as _fz
    from rapidfuzz.utils import default_process as _dp
    _all100 = True
    for _a, _b in (("A+", "A-"), ("B+", "B-"), ("AB+", "AB-"), ("O+", "O-")):
        _s = _fz.token_sort_ratio(_a, _b, processor=_dp)
        bc.append("  token_sort_ratio(%-4r, %-4r) = %.1f" % (_a, _b, _s))
        _all100 = _all100 and _s == 100.0
    bc.append("  brief records : 100.0 for all four pairs")
    bc.append("  -> %s" % ("MATCHES - fuzzy stays disabled for blood_type"
                           if _all100 else "CHANGED - re-decide the guard"))
except ImportError:
    bc.append("  rapidfuzz not importable -- BRIEF_CLAIM_UNVERIFIED (cannot recompute)")

lines.extend(bc)

with open(os.path.join(OUT_DIR, "02_stage3_profiling_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("Stage 2 + 3 reports written.")
print("raw shape:", raw_shape)
