# -*- coding: utf-8 -*-
"""
Stage 9 -- ANALYTICS: reproduces every number cited in insights_report.md.

Run with:
    python stage9_analytics.py

Each computed value is printed next to the figure claimed in the report, with
OK / MISMATCH. A mismatch is a real finding, not a script bug to paper over --
the whole point of this project is that a report's own claims are not evidence.

Reads : viz_ready.csv (266 rows)
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


def check(label, computed, claimed, tol=0.02, fmt="{:.3f}"):
    """Compare a computed statistic against the figure in insights_report.md."""
    try:
        ok = abs(float(computed) - float(claimed)) <= tol * max(1.0, abs(float(claimed)))
    except (TypeError, ValueError):
        ok = str(computed) == str(claimed)
    log(f"  {'OK      ' if ok else 'MISMATCH'} {label:<46} "
        f"computed={fmt.format(computed):>14}  report={fmt.format(claimed):>14}")
    return ok


def truthy(s):
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


df = pd.read_csv(VIZ, dtype=str, keep_default_na=False)
for c in ("units_sold", "unit_price", "total_revenue"):
    df[c] = pd.to_numeric(df[c].replace("", np.nan), errors="coerce")

log("=" * 92)
log("STAGE 9 -- SALES ANALYTICS: recomputed vs insights_report.md")
log("=" * 92)
log(f"viz_ready.csv rows: {len(df)}   (report claims 266)")
log()

# ---- clean subset: excludes revenue_mismatch and units_sold_outlier rows ----
mism = truthy(df["revenue_mismatch_flag"])
bulk = truthy(df["units_sold_outlier_flag"])
clean = df[~mism & ~bulk]
log(f"revenue_mismatch_flag rows : {int(mism.sum())}   (report: 13)")
log(f"units_sold_outlier_flag rows: {int(bulk.sum())}   (report: 6)")
log(f"clean subset n             : {len(clean)}   (report: 247)")
log()

results = []

# ---- 3.1 revenue does not differ by group -----------------------------------
log("### 3.1  Revenue group comparisons (expected: all null)")
sub = clean[clean["total_revenue"].notna()]

def groups(frame, col):
    """Real categories only -- a blank is an absent value, not a group.
    Including it adds a spurious level and inflates the test's df."""
    f = frame[frame[col].str.strip() != ""]
    return [g["total_revenue"].values for _, g in f.groupby(col) if len(g) > 1], len(f)


grp, n = groups(sub, "region")
log(f"  region groups={len(grp)} n={n}   (report: 5 groups, n=220)")
h, p = stats.kruskal(*grp)
results += [check("region Kruskal-Wallis H", h, 4.84, tol=0.05),
            check("region Kruskal-Wallis p", p, 0.304, tol=0.15)]
f, pf = stats.f_oneway(*grp)
results += [check("region ANOVA F", f, 1.03, tol=0.10),
            check("region ANOVA p", pf, 0.394, tol=0.15)]

grp, n = groups(sub, "product")
log(f"  product groups={len(grp)} n={n}   (report: 4 groups, n=226)")
h, p = stats.kruskal(*grp)
results += [check("product Kruskal-Wallis H", h, 1.24, tol=0.30),
            check("product Kruskal-Wallis p", p, 0.743, tol=0.15)]
log()

# ---- 3.2 volume mix ---------------------------------------------------------
log("### 3.2  Volume-mix chi-square tests")
prod = df.loc[df["product"].str.strip() != "", "product"].value_counts()
chi2, p = stats.chisquare(prod.values)
v = np.sqrt(chi2 / (prod.sum() * (len(prod) - 1)))
results += [check("product chi2", chi2, 27.63),
            check("product Cramers V", v, 0.20)]

reg = df.loc[df["region"].str.strip() != "", "region"].value_counts()
chi2, p = stats.chisquare(reg.values)
results += [check("region mix chi2", chi2, 6.23), check("region mix p", p, 0.183)]
log()

# ---- 3.3 concentration ------------------------------------------------------
log("### 3.3  Revenue / unit concentration in 6 bulk rows")
tot_rev = df["total_revenue"].sum()
bulk_rev = df.loc[bulk, "total_revenue"].sum()
tot_u = df["units_sold"].sum()
bulk_u = df.loc[bulk, "units_sold"].sum()
results += [
    check("total revenue", tot_rev, 14729126, tol=0.001, fmt="{:,.0f}"),
    check("bulk-row revenue", bulk_rev, 11857570, tol=0.001, fmt="{:,.0f}"),
    check("bulk revenue share %", bulk_rev / tot_rev * 100, 80.5, fmt="{:.1f}"),
    check("total units", tot_u, 144466, tol=0.001, fmt="{:,.0f}"),
    check("bulk units", bulk_u, 138000, tol=0.001, fmt="{:,.0f}"),
    check("bulk unit share %", bulk_u / tot_u * 100, 95.5, fmt="{:.1f}"),
]
log()

# ---- 3.4 AOV instability ----------------------------------------------------
log("### 3.4  AOV is unstable; median is robust")
allrev = df["total_revenue"].dropna()
results += [
    check("mean revenue (all)", allrev.mean(), 63215, tol=0.01, fmt="{:,.0f}"),
    check("n comparable", len(allrev), 233, tol=0.0, fmt="{:.0f}"),
    check("median revenue (all)", allrev.median(), 2493, tol=0.01, fmt="{:,.0f}"),
]
log()

# ---- 3.5 unit_price vs units_sold -------------------------------------------
log("### 3.5  unit_price vs units_sold correlation (expected: null)")
cc = clean[["unit_price", "units_sold"]].dropna()
r, pr = stats.pearsonr(cc["unit_price"], cc["units_sold"])
rho, prho = stats.spearmanr(cc["unit_price"], cc["units_sold"])
results += [check("Pearson r", r, -0.007, tol=0.5),
            check("Pearson p", pr, 0.920, tol=0.15),
            check("Spearman rho", rho, -0.005, tol=0.5),
            check("clean n", len(cc), 208, tol=0.02, fmt="{:.0f}")]
log()

# ---- 3.7 unit_price skew ----------------------------------------------------
log("### 3.7  unit_price skew, with and without the flagged outlier")
up_all = df["unit_price"].dropna()
out = truthy(df["unit_price_outlier_flag"])
up_ex = df.loc[~out, "unit_price"].dropna()
results += [
    check("skew incl. outlier", stats.skew(up_all), 13.95, tol=0.10, fmt="{:.2f}"),
    check("skew excl. outlier", stats.skew(up_ex), 0.055, tol=1.0, fmt="{:.3f}"),
    check("mean excl. outlier", up_ex.mean(), 107.89, tol=0.02, fmt="{:.2f}"),
    check("median excl. outlier", up_ex.median(), 104.97, tol=0.02, fmt="{:.2f}"),
]
log()

# ---- 3.9 customer identity --------------------------------------------------
log("### 3.9  customer_name is not a usable key")
names = df.loc[df["customer_name"].str.strip() != "", "customer_name"].nunique()
emails = df.loc[df["customer_email"].str.strip() != "", "customer_email"].nunique()
results += [check("unique customer_name", names, 83, tol=0.0, fmt="{:.0f}"),
            check("unique customer_email", emails, 15, tol=0.0, fmt="{:.0f}")]
log()

ok = sum(1 for r in results if r)
log("=" * 92)
log(f"RESULT: {ok}/{len(results)} figures reproduce insights_report.md")
log("=" * 92)

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nwrote {REPORT}")
