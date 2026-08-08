# -*- coding: utf-8 -*-
"""
Final artifact presence/size check -- run once at the end of the pipeline.
Confirms all six required deliverables (plus RUN_SUMMARY.md) exist on disk.
"""
import os

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

OUT_DIR = str(_HERE)
REQUIRED = [
    "01_business_brief.yaml",
    "cleaned_data.csv",
    "viz_ready.csv",
    "change_log.csv",
    "validation_report.md",
    "insights_report.md",
    "RUN_SUMMARY.md",
]

print(f"Output directory: {OUT_DIR}\n")
all_present = True
for fname in REQUIRED:
    path = os.path.join(OUT_DIR, fname)
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"  [OK]      {fname:28s} {size:>10,} bytes")
    else:
        print(f"  [MISSING] {fname:28s} NOT FOUND")
        all_present = False

print()
print("ALL REQUIRED ARTIFACTS PRESENT:", all_present)
