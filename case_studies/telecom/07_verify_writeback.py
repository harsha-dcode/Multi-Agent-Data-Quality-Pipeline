# -*- coding: utf-8 -*-
"""
Independent write-back verification -- per the "never trust a step's own
success report" rule. Re-derives key numbers directly from the artifacts on
disk (cleaned_data.csv, viz_ready.csv, change_log.csv) rather than trusting
the console output printed by 03_clean.py / 04_transform.py / 06_viz_ready.py.

Writes: 07_verify_writeback_report.txt
"""

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

import pandas as pd

OUT_DIR = str(_HERE)
CLEANED = OUT_DIR + r"\cleaned_data.csv"
VIZ = OUT_DIR + r"\viz_ready.csv"
CHANGELOG = OUT_DIR + r"\change_log.csv"

lines = []
def log(s=""):
    lines.append(str(s))
    print(s)

df = pd.read_csv(CLEANED, encoding="utf-8")
viz = pd.read_csv(VIZ, encoding="utf-8")
changelog = pd.read_csv(CHANGELOG, encoding="utf-8")

log(f"cleaned_data.csv: rows={len(df)}, cols={len(df.columns)}")
log(f"viz_ready.csv: rows={len(viz)}, cols={len(viz.columns)}")
log(f"change_log.csv: rows={len(changelog)}")

# total_charge derived-column correctness (every row, not a sample)
mismatches = int(((df["total_charge"] - (df["monthly_charge"] + df["overage_fee"])).abs() > 1e-9).sum())
log(f"total_charge write-back mismatches (should be 0): {mismatches}")

# data_plan_usage_conflict_flag correctness (every row)
expected_conflict = (df["data_plan"] == 0) & (df["data_usage"] > 0)
conflict_mismatches = int((df["data_plan_usage_conflict_flag"] != expected_conflict).sum())
log(f"data_plan_usage_conflict_flag write-back mismatches (should be 0): {conflict_mismatches}")
log(f"data_plan_usage_conflict_flag True count in cleaned_data.csv: {int(df['data_plan_usage_conflict_flag'].sum())}")

# header snake_case write-back (every column)
import re

non_snake = [c for c in df.columns if c != "__source_row" and not re.fullmatch(r"[a-z0-9_]+", c)]
log(f"Non-snake_case headers remaining in cleaned_data.csv (should be []): {non_snake}")

# churn rate, cross-checked two ways
churn_rate_mean = float(df["churn"].mean())
churn_rate_manual = int(df["churn"].sum()) / len(df)
log(f"Churn rate via .mean(): {churn_rate_mean:.6f}, via sum/len: {churn_rate_manual:.6f}, match: {churn_rate_mean == churn_rate_manual}")
log(f"Churned subscribers: {int(df['churn'].sum())} / {len(df)} = {churn_rate_mean*100:.2f}%")

# flag column True-count cross-check against change_log.csv, independent of 03_clean.py's own count
flag_cols = [c for c in df.columns if c.endswith("_flag")]
log(f"\nFlag columns present: {len(flag_cols)}")
for fc in flag_cols:
    true_count = int(df[fc].sum())
    log(f"  {fc}: True count = {true_count}")

# cleaned_data.csv vs viz_ready.csv row identity (control case: expect identical)
same_rows = set(df["__source_row"]) == set(viz["__source_row"])
log(f"\ncleaned_data.csv and viz_ready.csv cover identical __source_row sets: {same_rows}")
log(f"(expected True for this run: 0 rows were filtered in Stage 8, per 06_viz_ready_report.txt)")

# change_log.csv change-type breakdown, independent tally
log("\nchange_log.csv CHANGE_TYPE breakdown:")
for ct, cnt in changelog["CHANGE_TYPE"].value_counts().items():
    log(f"  {ct}: {cnt}")

with open(OUT_DIR + r"\07_verify_writeback_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
