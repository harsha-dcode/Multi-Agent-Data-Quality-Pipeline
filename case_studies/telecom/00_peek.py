"""
Stage 2 (partial): raw structural inspection of telecom_churn.csv.
Read-only against the input file. Writes 00_peek_report.txt in this folder.
"""
import hashlib
import os

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

INPUT = str(_HERE / "input" / "telecom_churn.csv")
INPUT_DISPLAY = "case_studies/telecom/input/telecom_churn.csv"  # repo-relative; keeps local paths out of the report
OUT_DIR = str(_HERE)
REPORT = os.path.join(OUT_DIR, "00_peek_report.txt")

lines = []
def log(s=""):
    lines.append(str(s))

# --- raw bytes: BOM / encoding sniff ---
with open(INPUT, "rb") as f:
    raw_bytes = f.read()

log("=== FILE ===")
log(f"path: {INPUT_DISPLAY}")
log(f"size_bytes: {len(raw_bytes):,}")

bom_map = {
    b"\xef\xbb\xbf": "UTF-8 with BOM",
    b"\xff\xfe": "UTF-16 LE BOM",
    b"\xfe\xff": "UTF-16 BE BOM",
}
detected_bom = "none"
for sig, name in bom_map.items():
    if raw_bytes.startswith(sig):
        detected_bom = name
        break
log(f"bom: {detected_bom}")
log(f"first_4_bytes_hex: {raw_bytes[:4].hex()}")

# try strict utf-8 decode
try:
    text = raw_bytes.decode("utf-8")
    encoding_used = "utf-8 (strict decode succeeded)"
except UnicodeDecodeError as e:
    text = raw_bytes.decode("latin-1")
    encoding_used = f"utf-8 FAILED ({e}); fell back to latin-1"
log(f"encoding: {encoding_used}")

sha256 = hashlib.sha256(raw_bytes).hexdigest()
log(f"sha256: {sha256}")
log(f"sha256_first16: {sha256[:16]}")

# --- structural scan ---
all_lines = text.splitlines()
log(f"\n=== STRUCTURE ===")
log(f"total_lines_incl_header: {len(all_lines)}")
log(f"data_rows_expected: {len(all_lines) - 1}")

header = all_lines[0]
log(f"\nheader_raw: {header!r}")
delim_candidates = {",": header.count(","), ";": header.count(";"), "\t": header.count("\t"), "|": header.count("|")}
log(f"delimiter_candidate_counts: {delim_candidates}")
detected_delim = max(delim_candidates, key=delim_candidates.get)
log(f"detected_delimiter: {detected_delim!r}")

cols = header.split(detected_delim)
log(f"column_count: {len(cols)}")
log(f"columns_exact: {cols}")

# check for whitespace / special chars in headers
for c in cols:
    if c != c.strip():
        log(f"  WARNING header has leading/trailing whitespace: {c!r}")
    if not c.replace("_", "").isalnum():
        log(f"  NOTE header has non-alnum/non-underscore chars: {c!r}")

# consistent column count across all data rows?
bad_row_count_lines = []
for i, ln in enumerate(all_lines[1:], start=0):  # start=0 -> __source_row for data rows
    if ln.strip() == "":
        continue
    n = len(ln.split(detected_delim))
    if n != len(cols):
        bad_row_count_lines.append((i, n, ln[:120]))
log(f"\nrows_with_wrong_field_count: {len(bad_row_count_lines)}")
for i, n, ln in bad_row_count_lines[:20]:
    log(f"  source_row={i} field_count={n} sample={ln!r}")

blank_lines = [i for i, ln in enumerate(all_lines[1:], start=0) if ln.strip() == ""]
log(f"blank_lines_in_body: {len(blank_lines)} -> {blank_lines[:20]}")

log(f"\n=== FIRST 10 DATA ROWS (raw) ===")
for i, ln in enumerate(all_lines[1:11], start=0):
    log(f"[{i}] {ln}")

log(f"\n=== LAST 10 DATA ROWS (raw) ===")
tail = all_lines[1:]
for i, ln in enumerate(tail[-10:], start=len(tail) - 10):
    log(f"[{i}] {ln}")

log(f"\n=== FOOTER / TRAILER CHECK ===")
log(f"last raw line: {all_lines[-1]!r}")
log(f"file ends with newline: {raw_bytes.endswith(b'\\n') or raw_bytes.endswith(b'\\r\\n')}")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("Wrote:", REPORT)
print("data_rows_expected:", len(all_lines) - 1)
print("columns:", cols)
print("bom:", detected_bom)
print("encoding:", encoding_used)
print("sha256_first16:", sha256[:16])
