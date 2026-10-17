import pandas as pd
import numpy as np
import os

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

IN = str(_HERE / "input" / "healthcare_dataset_dirty_export.csv")
OUT_DIR = str(_HERE)
OUT = os.path.join(OUT_DIR, "00_peek_report.txt")

lines = []

# encoding: try strict utf-8 decode of whole file; report any failure position
with open(IN, "rb") as f:
    raw = f.read()
try:
    raw.decode("utf-8", errors="strict")
    lines.append("utf-8 strict decode: SUCCESS - file is valid UTF-8")
except UnicodeDecodeError as e:
    lines.append(f"utf-8 strict decode FAILED: {e}")

# BOM check
with open(IN, "rb") as f:
    first_bytes = f.read(4)
lines.append(f"first 4 bytes: {first_bytes}")

# file size
size = os.path.getsize(IN)
lines.append(f"file size bytes: {size}")

df = pd.read_csv(IN, encoding="utf-8", low_memory=False)
lines.append(f"shape: {df.shape}")
lines.append(f"columns (raw, exact): {list(df.columns)}")
lines.append("")
lines.append("dtypes as read:")
lines.append(str(df.dtypes))
lines.append("")
lines.append("first 10 rows:")
lines.append(df.head(10).to_string())
lines.append("")
lines.append("last 10 rows:")
lines.append(df.tail(10).to_string())
lines.append("")
lines.append("null counts (pandas default NA detection only):")
lines.append(str(df.isnull().sum()))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("done, wrote", OUT)
print("shape", df.shape)
print(list(df.columns))
