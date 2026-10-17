#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
stage2a_peek.py -- Stage 2 (Data Extraction) quick inspection of messy_sales.csv.

Purpose: establish, with actual bytes, the extraction-layer defects the task
explicitly flagged before writing anything else (BOM, header drift, naive vs
dtype-pinned read). Nothing here is inferred from memory -- every number is
recomputed against THIS file at THIS path.
"""

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

import hashlib
import io
import os

IN_PATH = str(_HERE / "input" / "messy_sales.csv")
IN_DISPLAY = "case_studies/sales/input/messy_sales.csv"  # repo-relative; keeps local paths out of the report
OUT_DIR = str(_HERE)
REPORT = os.path.join(OUT_DIR, "00_peek_report.txt")

lines = []
def log(s=""):
    lines.append(str(s))

log("=" * 78)
log("STAGE 2 -- RAW EXTRACTION INVENTORY: messy_sales.csv")
log("=" * 78)

# ---- raw bytes / encoding / BOM ----
with open(IN_PATH, "rb") as f:
    raw_bytes = f.read()

size = len(raw_bytes)
md5 = hashlib.md5(raw_bytes).hexdigest()
sha256 = hashlib.sha256(raw_bytes).hexdigest()

has_bom = raw_bytes.startswith(b"\xef\xbb\xbf")
log(f"\nFile path      : {IN_DISPLAY}")
log(f"File size       : {size:,} bytes")
log(f"MD5             : {md5}")
log(f"SHA-256 (first16): {sha256[:16]}")
log(f"UTF-8 BOM present at byte 0 : {has_bom}  (bytes: {raw_bytes[:3]!r})")

# Decode both ways to show the practical effect of the BOM
text_utf8 = raw_bytes.decode("utf-8")             # BOM survives as \ufeff prefix
text_utf8_sig = raw_bytes.decode("utf-8-sig")      # BOM stripped correctly

first_line_utf8 = text_utf8.split("\n", 1)[0].rstrip("\r")
first_line_sig = text_utf8_sig.split("\n", 1)[0].rstrip("\r")
first_header_utf8 = first_line_utf8.split(",")[0]
first_header_sig = first_line_sig.split(",")[0]

log(f"\nDecoded with encoding='utf-8'      -> first header token: {first_header_utf8!r}")
log(f"Decoded with encoding='utf-8-sig'  -> first header token: {first_header_sig!r}")
log("IMPACT: reading this file with encoding='utf-8' (the pandas default on many")
log("        setups) leaves a literal '\\ufeff' glued to the first header, so the")
log("        column that LOOKS like 'order_id' is actually '\\ufeffAorder_id' or")
log("        similar -- df['order_id'] raises KeyError even though the column is")
log("        visibly right there in df.columns / a printed head(). This pipeline")
log("        will load with encoding='utf-8-sig' specifically to strip it.")

# ---- header inventory ----
header_line = first_line_sig
raw_headers = header_line.split(",")
log(f"\nRaw header row ({len(raw_headers)} columns), utf-8-sig decoded, exact repr:")
for i, h in enumerate(raw_headers):
    flag = ""
    if h != h.strip():
        flag = "  <-- LEADING/TRAILING WHITESPACE (silent KeyError risk: df['region'] misses this)"
    if any(c in h for c in " -./"):
        flag += "  <-- contains space/hyphen/dot/slash, needs snake_case normalization"
    log(f"  [{i:2d}] {h!r}{flag}")

# ---- row count / structural sample ----
all_lines = text_utf8_sig.splitlines()
n_lines_total = len(all_lines)
n_data_rows = n_lines_total - 1
log(f"\nTotal lines (incl. header): {n_lines_total}")
log(f"Data rows (excl. header)  : {n_data_rows}")

log("\nFirst 10 raw lines (post BOM-strip):")
for i, l in enumerate(all_lines[:10]):
    log(f"  L{i}: {l}")

log("\nLast 10 raw lines:")
for i, l in enumerate(all_lines[-10:], start=n_lines_total - 10):
    log(f"  L{i}: {l}")

# check for trailing blank lines / footer summary rows
blank_trailing = sum(1 for l in reversed(all_lines) if l.strip() == "")
log(f"\nTrailing blank lines at EOF: {blank_trailing}")
last_nonblank = next((l for l in reversed(all_lines) if l.strip() != ""), "")
looks_like_footer = any(tok in last_nonblank.lower() for tok in ["total", "sum", "grand", "average"])
log(f"Last non-blank line looks like a footer/summary row: {looks_like_footer}")
log(f"  content: {last_nonblank!r}")

# ---- naive read vs dtype=str,keep_default_na=False comparison ----
import pandas as pd


buf1 = io.StringIO(text_utf8_sig)
df_naive = pd.read_csv(buf1)  # pandas default type inference + default NA handling

buf2 = io.StringIO(text_utf8_sig)
df_safe = pd.read_csv(buf2, dtype=str, keep_default_na=False)

log("\n" + "=" * 78)
log("NAIVE pd.read_csv() vs dtype=str, keep_default_na=False -- cell-level diff")
log("=" * 78)
log(f"Naive read shape : {df_naive.shape}")
log(f"Safe  read shape : {df_safe.shape}")
log(f"Naive columns    : {list(df_naive.columns)}")
log(f"Safe  columns    : {list(df_safe.columns)}")

# KeyError demo on the naive frame using the "clean-looking" name
key_error_cols = []
for candidate in ["order_id", "region"]:
    if candidate not in df_naive.columns:
        key_error_cols.append(candidate)
log(f"\nColumns that would KeyError on df_naive[<clean-looking name>]: {key_error_cols}")
log("  (because the real names carry the BOM prefix and/or trailing space -- see header")
log("   inventory above)")

# Compare naive-inferred dtypes vs the raw string cells to see what got silently changed/destroyed.
# Align by position since column NAME strings differ due to BOM/whitespace; use safe frame's raw
# string cell as ground truth and naive frame's positionally-aligned cell as the naive read.
n_cells_total = df_safe.shape[0] * df_safe.shape[1]
destroyed = 0
preserved = 0
destroyed_examples = []

for col_idx in range(df_safe.shape[1]):
    safe_col = df_safe.iloc[:, col_idx]
    naive_col = df_naive.iloc[:, col_idx]
    for row_idx in range(df_safe.shape[0]):
        raw_val = safe_col.iat[row_idx]  # exact string as it appears in the file
        naive_val = naive_col.iat[row_idx]
        # "destroyed" = naive read turned a disguised-null / currency / leading-zero-like string
        # into something that no longer matches the literal source text once you str() it back,
        # OR pandas silently coerced it to NaN/float where the raw text was a non-numeric token.
        naive_as_str = "" if pd.isna(naive_val) else str(naive_val)
        if pd.isna(naive_val) and raw_val.strip() != "":
            destroyed += 1
            if len(destroyed_examples) < 15:
                destroyed_examples.append(
                    (df_safe.columns[col_idx], row_idx, raw_val, "NaN (silently nulled by pandas)")
                )
        elif naive_as_str != raw_val and raw_val.strip() != "":
            # value survived but was retyped/reformatted (e.g. "1200" -> 1200, "2023-1-5" untouched
            # but a float column truncated trailing text, etc.) -- still "destroyed" in the sense
            # that the original literal text is not recoverable from df_naive alone.
            destroyed += 1
            if len(destroyed_examples) < 15:
                destroyed_examples.append(
                    (df_safe.columns[col_idx], row_idx, raw_val, naive_as_str)
                )
        else:
            preserved += 1

log(f"\nTotal cells                         : {n_cells_total:,}")
log(f"Cells preserved verbatim (naive read): {preserved:,}")
log(f"Cells altered/destroyed (naive read) : {destroyed:,}  "
    f"({destroyed / n_cells_total * 100:.2f}% of all cells)")
log("\nFirst up to 15 destroyed-cell examples (column, row, raw literal -> naive value):")
for col, row, raw_v, naive_v in destroyed_examples:
    log(f"  {col!r} row {row}: {raw_v!r} -> {naive_v!r}")

log("\n" + "=" * 78)
log("CONCLUSION: this pipeline loads with encoding='utf-8-sig', dtype=str, "
    "keep_default_na=False")
log("so that (a) the BOM never enters a column name, (b) every disguised null survives")
log("into Stage 4 to be logged rather than silently becoming NaN, and (c) no numeric")
log("string is coerced/reformatted before the explicit Stage 4.6 cleaning step.")
log("=" * 78)

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

# Console is cp1252 on this machine; the report itself is UTF-8 and authoritative.
# Encode-and-replace for the console echo only, never for the file.
print("\n".join(lines).encode("ascii", errors="replace").decode("ascii"))
print(f"\n[WROTE] {REPORT}")
