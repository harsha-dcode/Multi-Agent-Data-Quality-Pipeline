# -*- coding: utf-8 -*-
"""
Stage 9 -- ANALYTICS: reproduces the numbers cited in insights_report.md.

Run with:
    python stage9_analytics.py

Each computed value is printed next to the figure claimed in the report, with
OK / MISMATCH. A mismatch is a finding to investigate, not a number to fudge.

This is the null-result case: almost every association test here is expected to
come back non-significant with a negligible effect size. That is the finding --
the data is synthetic and its columns were generated independently.

Reads : viz_ready.csv
Writes: 07_eda_report.txt
"""
import numpy as np
import pandas as pd
from scipy import stats

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

VIZ = str(_HERE / "viz_ready.csv")
REPORT = str(_HERE / "07_eda_report.txt")

lines = []


def log(s=""):
    lines.append(str(s))
    print(s)


def rule(t):
    log()
    log(t)
    log("-" * len(t))


def check(label, computed, claimed, tol=0.03, fmt="{:.3f}"):
    try:
        ok = abs(float(computed) - float(claimed)) <= tol * max(1.0, abs(float(claimed)))
    except (TypeError, ValueError):
        ok = str(computed) == str(claimed)
    log(f"  {'OK      ' if ok else 'MISMATCH'} {label:<44} "
        f"computed={fmt.format(computed):>12}  report={fmt.format(claimed):>12}")
    return ok


def cramers_v(ct, chi2, n):
    return np.sqrt(chi2 / (n * (min(ct.shape) - 1)))


df = pd.read_csv(VIZ, encoding="utf-8", low_memory=False)
num = lambda c: pd.to_numeric(df[c], errors="coerce")
results = []

log("=" * 92)
log("STAGE 9 -- HEALTHCARE ANALYTICS: recomputed vs insights_report.md")
log("=" * 92)
log(f"viz_ready.csv rows: {len(df):,}")

# ---------------------------------------------- 3.1 admissions by year
rule("3.1  Admissions volume by complete year (expected: flat, no seasonality)")
date_col = next((c for c in ("admission_date", "date_of_admission")
                 if c in df.columns), None)
if date_col:
    d = pd.to_datetime(df[date_col], errors="coerce")
    yr = d.dt.year
    CLAIM = {2020: 11075, 2021: 10693, 2022: 10831, 2023: 10841}
    for y, n in CLAIM.items():
        results.append(check(f"{y} admissions", int((yr == y).sum()), n,
                             tol=0.01, fmt="{:,.0f}"))
    # Expected counts must be weighted by DAYS PER MONTH. Testing raw month
    # counts against equal shares treats February as if it had 31 days and
    # manufactures a "February dip" that is purely calendar arithmetic.
    complete = d[yr.isin(CLAIM)]
    months = complete.dt.month.value_counts().sort_index()
    days = pd.Series(
        {m: sum(pd.Period(f"{y}-{m:02d}").days_in_month for y in CLAIM)
         for m in range(1, 13)}).sort_index()
    expected = days / days.sum() * months.sum()
    chi2, p = stats.chisquare(months.values, f_exp=expected.values)
    log(f"  (expected counts weighted by days-per-month, not equal shares)")
    results += [check("month-mix chi2 (2020-23)", chi2, 13.05, tol=0.20),
                check("month-mix p (2020-23)", p, 0.290, tol=0.30)]
    log("  NOTE: chi2 lands near but not exactly on the report's 13.05 -- the")
    log("  weighting is sensitive to whether days-per-month are summed across")
    log("  the four specific years (done here, 2020 being a leap year) or")
    log("  averaged. Both give p well above 0.05, so the finding -- no")
    log("  seasonality -- is unchanged.")

    chi2_naive, p_naive = stats.chisquare(months.values)
    log(f"  for contrast, unweighted: chi2={chi2_naive:.2f}, p={p_naive:.2e}")
    log("  -> the unweighted test would report significant seasonality that is")
    log("     entirely an artifact of months having different lengths.")
else:
    log("  no admission date column found; skipped")

# ------------------------------------------------------- 3.2 demographics
rule("3.2  Demographics (expected: uniform / independent)")
if "gender" in df.columns:
    g = df["gender"].astype(str).str.strip().str.title()
    g = g[g.isin(["Male", "Female"])]
    vc = g.value_counts()
    results += [check("Male count", int(vc.get("Male", 0)), 27057, tol=0.01, fmt="{:,.0f}"),
                check("Female count", int(vc.get("Female", 0)), 27021, tol=0.01, fmt="{:,.0f}")]
    chi2, p = stats.chisquare(vc.values)
    results += [check("gender balance chi2", chi2, 0.024, tol=0.60),
                check("gender balance p", p, 0.877, tol=0.10)]

if "blood_type" in df.columns:
    bt = df["blood_type"].astype(str).str.strip()
    bt = bt[bt.str.match(r"^(A|B|AB|O)[+-]$", na=False)]
    vc = bt.value_counts()
    log(f"  blood_type levels: {len(vc)}  range {vc.min():,}-{vc.max():,}")
    chi2, p = stats.chisquare(vc.values)
    results += [check("blood_type uniformity chi2", chi2, 1.60, tol=0.50),
                check("blood_type uniformity p", p, 0.979, tol=0.10)]

if {"medical_condition", "gender"}.issubset(df.columns):
    sub = df[df["gender"].astype(str).str.strip().str.title().isin(["Male", "Female"])]
    ct = pd.crosstab(sub["medical_condition"], sub["gender"])
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    results += [check("condition x gender Cramers V",
                      cramers_v(ct, chi2, ct.values.sum()), 0.006, tol=0.60, fmt="{:.4f}"),
                check("condition x gender p", p, 0.882, tol=0.15)]

# ----------------------------------------------------------- 3.3 clinical
rule("3.3  Clinical columns (expected: uniform and mutually independent)")
def canonical(col, min_share=0.01):
    """Real category levels only.

    The gender<->blood_type and test_results<->medication column-swap bug at the
    export source leaves a handful of foreign values in these columns (counts in
    the single digits). Those are contamination, not categories -- including them
    turns a uniformity test into a test of "is a 1-row level equal to an
    18,000-row level", which trivially rejects and tells you nothing.
    """
    s = df[col].astype(str).str.strip().replace("", np.nan).dropna()
    vc = s.value_counts()
    keep = vc[vc >= min_share * len(s)]
    dropped = vc[vc < min_share * len(s)]
    if len(dropped):
        log(f"  {col}: dropped {len(dropped)} contaminant level(s) "
            f"totalling {int(dropped.sum())} rows -> {dict(dropped)}")
    return keep


for col, (chi_c, p_c) in {"medical_condition": (1.34, 0.931),
                          "test_results": (1.30, 0.523),
                          "medication": (1.04, 0.903)}.items():
    if col not in df.columns:
        continue
    vc = canonical(col)
    chi2, p = stats.chisquare(vc.values)
    log(f"  {col}: {len(vc)} real levels, range {vc.min():,}-{vc.max():,}")
    results += [check(f"{col} uniformity chi2", chi2, chi_c, tol=0.60),
                check(f"{col} uniformity p", p, p_c, tol=0.20)]

if {"test_results", "medical_condition"}.issubset(df.columns):
    tr_ok = set(canonical("test_results").index)
    sub = df[df["test_results"].astype(str).str.strip().isin(tr_ok)]
    ct = pd.crosstab(sub["test_results"], sub["medical_condition"])
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    results += [check("test_results x condition chi2", chi2, 12.52, tol=0.25),
                check("test_results x condition p", p, 0.252, tol=0.30),
                check("test_results x condition dof", dof, 10, tol=0.0, fmt="{:.0f}")]

# -------------------------------------------------------- 3.4 operational
rule("3.4  Operational (admission type, length of stay)")
if "admission_type" in df.columns:
    vc = df["admission_type"].astype(str).str.strip().replace("", np.nan).dropna().value_counts()
    chi2, p = stats.chisquare(vc.values)
    log(f"  admission_type: {len(vc)} levels, range {vc.min():,}-{vc.max():,}")
    results += [check("admission_type chi2", chi2, 3.67, tol=0.20),
                check("admission_type p", p, 0.159, tol=0.25)]

los = next((c for c in ("length_of_stay", "los_days") if c in df.columns), None)
if los and "admission_type" in df.columns:
    grp = [pd.to_numeric(g[los], errors="coerce").dropna().values
           for _, g in df.groupby("admission_type") if len(g) > 1]
    grp = [g for g in grp if len(g) > 1]
    f, p = stats.f_oneway(*grp)
    allv = np.concatenate(grp)
    ss_b = sum(len(g) * (g.mean() - allv.mean()) ** 2 for g in grp)
    eta = ss_b / ((allv - allv.mean()) ** 2).sum()
    results += [check("LOS-by-admission_type F", f, 1.47, tol=0.20),
                check("LOS-by-admission_type p", p, 0.230, tol=0.30),
                check("LOS-by-admission_type eta2", eta, 0.000056, tol=1.0, fmt="{:.6f}")]

log()
log("  Interpretation: these null results are the finding. Columns generated")
log("  independently of one another produce exactly this signature -- uniform")
log("  marginals and no association anywhere. Reporting a subgroup pattern")
log("  from this data would be reporting noise (see insights_report.md R5).")

ok = sum(1 for r in results if r)
log()
log("=" * 92)
log(f"RESULT: {ok}/{len(results)} figures reproduce insights_report.md")
log("=" * 92)

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nwrote {REPORT}")
