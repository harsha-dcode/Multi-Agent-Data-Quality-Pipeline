# -*- coding: utf-8 -*-
"""Run the mandatory fuzzy-matching collision guard on every categorical column BEFORE any
fuzzy matching is attempted anywhere in the pipeline. Prints + writes measured evidence."""
import pandas as pd
from rapidfuzz import fuzz, utils
import os

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

OUT_DIR = str(_HERE)

CANON = {
    "gender": ["Male", "Female"],
    "blood_type": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
    "medical_condition": ["Diabetes", "Arthritis", "Cancer", "Asthma", "Hypertension", "Obesity"],
    "admission_type": ["Elective", "Emergency", "Urgent"],
    "insurance_provider": ["Cigna", "UnitedHealthcare", "Medicare", "Blue Cross", "Aetna"],
    "test_results": ["Normal", "Abnormal", "Inconclusive"],
    "medication": ["Ibuprofen", "Lipitor", "Penicillin", "Paracetamol", "Aspirin"],
}

lines = []
lines.append("COLLISION GUARD RESULTS (rapidfuzz.utils.default_process, alnum-strip+lowercase)")
lines.append("=" * 70)

def canonicals_collide(canonical_list):
    keys = [utils.default_process(str(c)) for c in canonical_list]
    collided = len(set(keys)) < len(keys)
    return collided, dict(zip(canonical_list, keys))

results = {}
for col, canon in CANON.items():
    collided, keymap = canonicals_collide(canon)
    results[col] = collided
    lines.append(f"\nColumn: {col}")
    lines.append(f"  canonical values: {canon}")
    lines.append(f"  processed keys:   {keymap}")
    lines.append(f"  COLLISION DETECTED: {collided}")
    if collided:
        # show which pairs collide
        seen = {}
        for c, k in keymap.items():
            seen.setdefault(k, []).append(c)
        for k, members in seen.items():
            if len(members) > 1:
                lines.append(f"    -> key '{k}' shared by: {members}  (pairwise scores under this processor:)")
                for i in range(len(members)):
                    for j in range(i+1, len(members)):
                        score = fuzz.token_sort_ratio(members[i], members[j], processor=utils.default_process)
                        lines.append(f"       token_sort_ratio('{members[i]}','{members[j]}') = {score}")

lines.append("\n" + "=" * 70)
lines.append("VERDICT per column:")
for col, collided in results.items():
    verdict = "DANGEROUS - fuzzy matching DISABLED, exact-match only" if collided else "SAFE - fuzzy matching permitted (with additional tiered exact-match pass first)"
    lines.append(f"  {col}: {verdict}")

with open(os.path.join(OUT_DIR, "02c_collision_guard_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("\n".join(lines))
