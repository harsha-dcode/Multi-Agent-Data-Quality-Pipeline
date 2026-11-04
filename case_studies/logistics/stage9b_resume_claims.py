# -*- coding: utf-8 -*-
"""
Stage 9b -- recompute every figure I cite outside this repo.

stage9_analytics.py verifies the body of insights_report.md. It does not cover
some of the figures I quote on a resume or in an interview: the best-performing
warehouse, the chi-square behind the on-time spread, the two confound checks
that let me call that spread operational, the category side of the margin
result, and the worst category's numbers.

This script closes that gap. Every claim below is recomputed from the run's own
output files and printed next to the claim, with OK / MISMATCH.

A MISMATCH means the claim is wrong and the claim gets changed. It does not
mean the tolerance gets widened.

Reads : input/logistics_supply_chain_dataset_v3.csv, viz_ready.csv
Writes: 09b_resume_claims_report.txt
Run   : python stage9b_resume_claims.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
RAW = HERE / "input" / "logistics_supply_chain_dataset_v3.csv"
VIZ = HERE / "viz_ready.csv"
REPORT = HERE / "09b_resume_claims_report.txt"

lines = []
results = []


def log(s=""):
    lines.append(str(s))
    print(s)


def rule(t):
    log()
    log(t)
    log("-" * len(t))


def check(label, computed, claimed, tol=0.02, fmt="{:.2f}"):
    """Relative tolerance against the claimed value; tol=0 means exact."""
    try:
        c, k = float(computed), float(claimed)
        ok = abs(c - k) <= tol * max(1.0, abs(k))
        shown_c, shown_k = fmt.format(c), fmt.format(k)
    except (TypeError, ValueError):
        ok = str(computed) == str(claimed)
        shown_c, shown_k = str(computed), str(claimed)
    results.append(ok)
    log("  %-8s %-46s computed=%14s  claim=%14s"
        % ("OK" if ok else "MISMATCH", label, shown_c, shown_k))
    return ok


def eta_squared(groups):
    """Between-group sum of squares over total, for a one-way layout."""
    allv = np.concatenate(groups)
    gm = allv.mean()
    ss_b = sum(len(g) * (g.mean() - gm) ** 2 for g in groups)
    ss_t = ((allv - gm) ** 2).sum()
    return ss_b / ss_t


raw = pd.read_csv(RAW, encoding="utf-8", low_memory=False, dtype=str)
df = pd.read_csv(VIZ, encoding="utf-8", low_memory=False)

log("=" * 100)
log("STAGE 9b -- figures quoted outside the repo, recomputed from the run's own output")
log("=" * 100)

# ---------------------------------------------------------------- bullet 1
rule("Bullet 1: 30,102 shipments across 12 warehouses, 4 transport modes, 5 regions")
check("raw shipment rows", len(raw), 30102, tol=0.0, fmt="{:,.0f}")
check("distinct warehouse_id (cleaned)", df["warehouse_id"].nunique(), 12, tol=0.0,
      fmt="{:,.0f}")
check("distinct transport_mode (cleaned)", df["transport_mode"].nunique(), 4, tol=0.0,
      fmt="{:,.0f}")
check("distinct destination_region (cleaned)", df["destination_region"].nunique(), 5,
      tol=0.0, fmt="{:,.0f}")

# ---------------------------------------------------------------- bullet 2
rule("Bullet 2: 21-point on-time gap between warehouses, confounds ruled out")
wh = df.groupby("warehouse_id").agg(
    shipments=("delivery_status", "size"),
    on_time_pct=("delivery_status", lambda s: (s == "On Time").mean() * 100),
    mean_distance=("distance_km", lambda s: pd.to_numeric(s, errors="coerce").mean()),
).sort_values("on_time_pct")

log("  %-12s%11s%12s%14s" % ("warehouse", "shipments", "on-time %", "mean dist km"))
for w, r in wh.iterrows():
    log("  %-12s%11s%12.2f%14.1f"
        % (w, format(int(r["shipments"]), ","), r["on_time_pct"], r["mean_distance"]))
log()

worst_id, best_id = wh.index[0], wh.index[-1]
worst, best = wh["on_time_pct"].iloc[0], wh["on_time_pct"].iloc[-1]
check("worst warehouse is WH011", worst_id, "WH011")
check("worst on-time %", worst, 49.3, tol=0.01)
check("best warehouse is WH001", best_id, "WH001")
check("best on-time %", best, 70.3, tol=0.01)
check("spread in percentage points", best - worst, 21.0, tol=0.05)

# The report's chi-square is over the FULL 4-level delivery_status, not a
# binary on-time/not split. A 12x2 table gives chi2=625.19, V=0.1459 instead.
# Recording which table it is, because the two answer different questions.
ct = pd.crosstab(df["warehouse_id"], df["delivery_status"])
chi2, p, dof, _ = stats.chi2_contingency(ct)
cramers_v = np.sqrt(chi2 / (len(df) * (min(ct.shape) - 1)))
log("  contingency table: warehouse_id x delivery_status (%d x %d), dof=%d"
    % (ct.shape[0], ct.shape[1], dof))
check("status by warehouse chi2", chi2, 929.2, tol=0.01, fmt="{:,.2f}")
check("status by warehouse p < 0.001", float(p < 0.001), 1.0, tol=0.0, fmt="{:.0f}")
check("status by warehouse Cramers V", cramers_v, 0.103, tol=0.01, fmt="{:.4f}")

# confound 1 -- is it just that bad warehouses ship more by Road?
mix = pd.crosstab(df["warehouse_id"], df["transport_mode"], normalize="index") * 100
log()
log("  confound 1: transport-mode mix per warehouse (%), range across warehouses")
for mode in sorted(mix.columns):
    log("    %-18s min %5.1f   max %5.1f   spread %4.1f pts"
        % (mode, mix[mode].min(), mix[mode].max(), mix[mode].max() - mix[mode].min()))
check("Road share spread across warehouses <= 10 pts",
      float((mix["Road"].max() - mix["Road"].min()) <= 10.0), 1.0, tol=0.0, fmt="{:.0f}")

# confound 2 -- is it just that bad warehouses ship further?
r, p_r = stats.pearsonr(wh["mean_distance"], wh["on_time_pct"])
log()
log("  confound 2: mean shipping distance vs on-time rate, across the 12 warehouses")
check("distance vs on-time pearson r", round(r, 2), 0.07, tol=0.0, fmt="{:.2f}")
check("distance vs on-time p (not significant)", float(p_r > 0.05), 1.0, tol=0.0,
      fmt="{:.0f}")

# ---------------------------------------------------------------- bullet 3
rule("Bullet 3: Road 55.2% of volume at 54.4% on-time, against 81.4% for Air")
# Denominator note, worth stating because the report is not consistent about it:
# the by-mode on-time rates exclude In Transit shipments (not yet deliverable),
# while the by-warehouse rates above are over all rows. On the all-rows basis
# Road reads 53.92% and Air 80.77%. Each figure is checked on its own basis.
deliv = df[df["delivery_status"] != "In Transit"]
log("  share is over all %s rows; on-time is over the %s delivered rows"
    % (format(len(df), ","), format(len(deliv), ",")))
road, air = df[df["transport_mode"] == "Road"], df[df["transport_mode"] == "Air"]
road_d = deliv[deliv["transport_mode"] == "Road"]
air_d = deliv[deliv["transport_mode"] == "Air"]
check("Road share of shipments %", len(road) / len(df) * 100, 55.2, tol=0.01)
check("Road on-time % (delivered basis)",
      (road_d["delivery_status"] == "On Time").mean() * 100, 54.4, tol=0.01)
check("Air on-time % (delivered basis)",
      (air_d["delivery_status"] == "On Time").mean() * 100, 81.4, tol=0.01)

# ---------------------------------------------------------------- bullet 4
rule("Bullet 4: margin is a product-category problem, not a transport-mode problem")
by_cat = [pd.to_numeric(g["profit_margin_pct"], errors="coerce").dropna().values
          for _, g in df.groupby("product_category")]
by_cat = [g for g in by_cat if len(g) > 1]
f_cat, p_cat = stats.f_oneway(*by_cat)
check("margin by category ANOVA F", f_cat, 4299.9, tol=0.02, fmt="{:,.1f}")
check("margin by category eta-squared", eta_squared(by_cat), 0.594, tol=0.02,
      fmt="{:.4f}")

by_mode = [pd.to_numeric(g["profit_margin_pct"], errors="coerce").dropna().values
           for _, g in df.groupby("transport_mode")]
by_mode = [g for g in by_mode if len(g) > 1]
f_mode, p_mode = stats.f_oneway(*by_mode)
check("margin by mode ANOVA p (not significant)", p_mode, 0.75, tol=0.05, fmt="{:.3f}")
eta_mode = eta_squared(by_mode)
log("  margin by mode eta-squared, unrounded: %.10f" % eta_mode)
check("margin by mode eta-squared < 0.0001", float(eta_mode < 0.0001), 1.0, tol=0.0,
      fmt="{:.0f}")

# ---------------------------------------------------------------- bullet 5
rule("Bullet 5: worst category at -2.13% margin, 51.7% of its shipments lose money")
pm = pd.to_numeric(df["profit_margin_pct"], errors="coerce")
cat = df.groupby("product_category").apply(
    lambda g: pd.Series({
        "n": len(g),
        "mean_margin": pd.to_numeric(g["profit_margin_pct"], errors="coerce").mean(),
        "pct_losing": (pd.to_numeric(g["profit_margin_pct"],
                                     errors="coerce") < 0).mean() * 100,
    }), include_groups=False).sort_values("mean_margin")

log("  %-26s%9s%14s%14s" % ("category", "n", "mean margin %", "losing %"))
for c, r_ in cat.iterrows():
    log("  %-26s%9s%14.2f%14.2f"
        % (c, format(int(r_["n"]), ","), r_["mean_margin"], r_["pct_losing"]))
log()

worst_cat = cat.index[0]
check("worst category is Books & Stationery", worst_cat, "Books & Stationery")
check("worst category mean margin %", cat["mean_margin"].iloc[0], -2.13, tol=0.02)
check("worst category shipments losing money %", cat["pct_losing"].iloc[0], 51.7,
      tol=0.02)
check("network-wide shipments losing money %", (pm < 0).mean() * 100, 11.83, tol=0.02)
check("only one category has negative mean margin",
      float((cat["mean_margin"] < 0).sum()), 1.0, tol=0.0, fmt="{:.0f}")

# ----------------------------------------------------------------- verdict
ok = sum(results)
log()
log("=" * 100)
log("RESULT: %d/%d claims reproduce" % (ok, len(results)))
if ok != len(results):
    log("A MISMATCH means the claim is wrong. Change the claim, not the tolerance.")
log("=" * 100)

REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\nwrote %s" % REPORT)
