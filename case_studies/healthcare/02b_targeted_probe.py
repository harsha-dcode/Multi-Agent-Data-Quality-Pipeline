# -*- coding: utf-8 -*-
"""Targeted probes to pin down exact regex/logic needed before writing the cleaning script."""
import pandas as pd
import re
import os

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

IN = str(_HERE / "input" / "healthcare_dataset_dirty_export.csv")
OUT_DIR = str(_HERE)
df = pd.read_csv(IN, encoding="utf-8", low_memory=False, dtype=str)

out = []

# Room number patterns
rn = df["Room Number"].dropna().astype(str)
out.append("Room Number samples with non-digit chars:")
out.append(str(rn[~rn.str.fullmatch(r"\d+")].value_counts().head(20)))
out.append(f"count with 'Room' prefix: {rn.str.contains('Room', case=False, na=False).sum()}")
out.append(f"count with leading quote: {rn.str.startswith(chr(39)).sum()}")
out.append("")

# Age word-numbers / non-numeric non-disguise tokens
age = df["Age"].dropna().astype(str)
non_numeric_age = age[~age.str.strip().str.fullmatch(r"-?\d+")]
out.append(f"Age non-numeric non-null tokens (excluding pure ints): {non_numeric_age.value_counts().head(30).to_dict()}")
out.append(f"Age with unit suffix e.g. 'yrs': {age.str.contains('yr', case=False, na=False).sum()}")
out.append("")

# Insurance provider - space variant of UnitedHealthcare, BlueCross
ins = df["Insurance Provider"].dropna().astype(str)
out.append("Insurance Provider full value_counts (all unique <=40):")
out.append(str(ins.value_counts()))
out.append("")

# Blood type non-canonical values full list
bt = df["Blood Type"].dropna().astype(str)
out.append("Blood Type full value_counts:")
out.append(str(bt.value_counts()))
out.append("")

# Gender full value counts
gd = df["Gender"].dropna().astype(str)
out.append("Gender full value_counts:")
out.append(str(gd.value_counts()))
out.append("")

# check blood_type <-> gender swap: rows where Blood Type contains Male/Female (case-insens, stripped)
bt_is_gender = df["Blood Type"].astype(str).str.strip().str.casefold().isin(["male","female"])
gd_is_bloodtype = df["Gender"].astype(str).str.strip().str.upper().isin(["A+","A-","B+","B-","AB+","AB-","O+","O-"])
out.append(f"rows where Blood Type holds a gender word: {bt_is_gender.sum()}")
out.append(f"rows where Gender holds a blood-type code: {gd_is_bloodtype.sum()}")
both = (bt_is_gender & gd_is_bloodtype)
out.append(f"rows where BOTH true (symmetric swap confirmed): {both.sum()}")
out.append("")

# test_results <-> medication swap
tr_is_med = df["Test Results"].astype(str).str.strip().str.casefold().isin(
    ["ibuprofen","lipitor","penicillin","paracetamol","aspirin"])
med_is_tr = df["Medication"].astype(str).str.strip().str.casefold().isin(
    ["normal","abnormal","inconclusive"])
out.append(f"rows where Test Results holds a medication name: {tr_is_med.sum()}")
out.append(f"rows where Medication holds a test-result word: {med_is_tr.sum()}")
both2 = (tr_is_med & med_is_tr)
out.append(f"rows where BOTH true (symmetric swap confirmed): {both2.sum()}")
out.append("")

# Medical condition typo list
mc = df["Medical Condition"].dropna().astype(str)
out.append("Medical Condition value_counts (all, to see typo tail):")
out.append(str(mc.value_counts().to_string()))
out.append("")

# Admission Type full
at = df["Admission Type"].dropna().astype(str)
out.append("Admission Type value_counts (all):")
out.append(str(at.value_counts().to_string()))
out.append("")

# Billing amount format survey - separator patterns
ba = df["Billing Amount"].dropna().astype(str)
has_comma = ba.str.contains(",", na=False)
has_dot = ba.str.contains(r"\.", na=False, regex=True)
out.append(f"Billing Amount: has comma {has_comma.sum()}, has dot {has_dot.sum()}, has both {(has_comma&has_dot).sum()}")
out.append("Sample values with comma:")
out.append(str(ba[has_comma].head(10).tolist()))
out.append("Sample values with currency symbols:")
out.append(str(ba[ba.str.contains(r'[\$₹]', na=False, regex=True)].head(10).tolist()))
out.append("Sample of .00 duplicate-suffix artifact pattern (NNNNN.NN.00):")
out.append(str(ba[ba.str.contains(r'^\d+\.\d+\.00$', na=False, regex=True)].head(10).tolist()))
out.append(f"count matching NNNNN.NN.00 pattern: {ba.str.contains(r'^\d+\.\d+\.00$', na=False, regex=True).sum()}")
out.append(f"count exactly '999999' or '999999.0': {(ba.isin(['999999','999999.0','999999.00'])).sum()}")
out.append("")

# Date garbage patterns
doa = df["Date of Admission"].dropna().astype(str)
out.append(f"Date of Admission '0000-00-00' count: {(doa=='0000-00-00').sum()}")
out.append(f"Date of Admission day/month>31 or invalid pattern samples:")
bad_pattern = doa[~doa.str.match(r"^\d{4}-\d{2}-\d{2}$")]
out.append(str(bad_pattern.value_counts().head(15)))

with open(os.path.join(OUT_DIR, "02b_targeted_probe_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
