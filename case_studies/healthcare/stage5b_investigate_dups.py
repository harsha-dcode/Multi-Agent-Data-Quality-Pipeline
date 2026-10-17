import pandas as pd
import os

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent
OUT_DIR = str(_HERE)
df = pd.read_csv(os.path.join(OUT_DIR, "cleaned_data.csv"), encoding="utf-8", low_memory=False)
dup_check_cols = [c for c in df.columns if c != "__source_row"]
mask = df.duplicated(subset=dup_check_cols, keep=False)
sub = df[mask].sort_values(dup_check_cols)
print("total rows involved in post-transform duplication:", mask.sum())
print(sub[["__source_row","name","date_of_admission","doctor","hospital","billing_amount","admission_year","admission_month"]].head(20).to_string())
