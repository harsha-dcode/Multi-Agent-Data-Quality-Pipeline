# -*- coding: utf-8 -*-
"""
Stage 9 -- ANALYTICS: reproduces every number cited in insights_report.md.

Run with:
    python 06_eda.py

Each computed value is printed next to the figure claimed in the report, with
OK / MISMATCH. A mismatch is a finding to investigate, not a number to fudge.

Reads : viz_ready.csv (29,354 rows)
Writes: 06_eda_report.txt
"""
import numpy as np
import pandas as pd
from scipy import stats

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

VIZ = str(_HERE / "viz_ready.csv")
REPORT = str(_HERE / "06_eda_report.txt")

lines = []


def log(s=""):
    lines.append(str(s))
    print(s)


def rule(t):
    log()
    log(t)
    log("-" * len(t))


def check(label, computed, claimed, tol=0.02, fmt="{:.2f}"):
    try:
        ok = abs(float(computed) - float(claimed)) <= tol * max(1.0, abs(float(claimed)))
    except (TypeError, ValueError):
        ok = str(computed) == str(claimed)
    log(f"  {'OK      ' if ok else 'MISMATCH'} {label:<42} "
        f"computed={fmt.format(computed):>12}  report={fmt.format(claimed):>12}")
    return ok


df = pd.read_csv(VIZ, encoding="utf-8", low_memory=False)
num = lambda c: pd.to_numeric(df[c], errors="coerce")
results = []

log("=" * 92)
log("STAGE 9 -- LOGISTICS ANALYTICS: recomputed vs insights_report.md")
log("=" * 92)
results.append(check("viz_ready.csv rows", len(df), 29354, tol=0.0, fmt="{:,.0f}"))

# ------------------------------------------------------ 3.1 status mix
rule("3.1  Delivery status mix")
vc = df["delivery_status"].value_counts()
CLAIM = {"On Time": (18220, 62.07), "Delayed": (8488, 28.92),
         "Early": (2417, 8.23), "In Transit": (229, 0.78)}
for k, (n, pct) in CLAIM.items():
    got = int(vc.get(k, 0))
    results.append(check(f"{k} count", got, n, tol=0.005, fmt="{:,.0f}"))
    results.append(check(f"{k} share %", got / len(df) * 100, pct, tol=0.02))

# --------------------------------------------- 3.2 transit time by mode
rule("3.2  Transit time and on-time rate by transport mode")
delivered = df[df["delivery_status"] != "In Transit"]
log(f"  delivered subset n = {len(delivered):,}   (report: 29,125)")

MODE = {"Air": (1.84, 81.36, 6343), "Sea": (15.95, 70.19, 475),
        "Rail": (7.57, 64.07, 6344), "Road": (5.61, 54.37, 16192)}
for mode, (transit, ontime, n) in MODE.items():
    sub = df[df["transport_mode"] == mode]
    if not len(sub):
        log(f"  {mode}: absent")
        continue
    t = pd.to_numeric(sub["actual_transit_days"], errors="coerce").mean()
    o = (sub["delivery_status"] == "On Time").mean() * 100
    results += [check(f"{mode} mean transit days", t, transit, tol=0.03),
                check(f"{mode} on-time %", o, ontime, tol=0.02),
                check(f"{mode} shipments", len(sub), n, tol=0.005, fmt="{:,.0f}")]

grp = [pd.to_numeric(g["delay_days"], errors="coerce").dropna().values
       for _, g in delivered.groupby("transport_mode")]
grp = [g for g in grp if len(g) > 1]
f, p = stats.f_oneway(*grp)
ss_b = sum(len(g) * (g.mean() - np.concatenate(grp).mean()) ** 2 for g in grp)
ss_t = ((np.concatenate(grp) - np.concatenate(grp).mean()) ** 2).sum()
results += [check("delay_days ANOVA F", f, 123.0, tol=0.05),
            check("delay_days eta-squared", ss_b / ss_t, 0.0125, tol=0.15, fmt="{:.4f}")]

# --------------------------------------------------- 3.3 profitability
rule("3.3  Profitability structure")
pm = num("profit_margin_pct")
results += [check("profit margin mean %", pm.mean(), 28.27),
            check("profit margin median %", pm.median(), 29.29),
            check("negative-margin share %", (pm < 0).mean() * 100, 11.83, tol=0.03)]

grp = [pd.to_numeric(g["profit_margin_pct"], errors="coerce").dropna().values
       for _, g in df.groupby("transport_mode")]
grp = [g for g in grp if len(g) > 1]
f, p = stats.f_oneway(*grp)
results += [check("margin-by-mode ANOVA F", f, 0.407, tol=0.15),
            check("margin-by-mode p", p, 0.748, tol=0.15)]

# --------------------------------------------------------- 3.4 returns
rule("3.4  Returns")
ret = df["return_status"].astype(str).str.strip().str.lower()
is_ret = ret.isin(["returned", "yes", "true", "1"])
results += [check("return count", int(is_ret.sum()), 2517, tol=0.01, fmt="{:,.0f}"),
            check("return rate %", is_ret.mean() * 100, 8.57, tol=0.02)]

ct = pd.crosstab(df["transport_mode"], is_ret)
chi2, p, dof, _ = stats.chi2_contingency(ct)
v = np.sqrt(chi2 / (len(df) * (min(ct.shape) - 1)))
results += [check("returns-by-mode chi2", chi2, 0.865, tol=0.20),
            check("returns-by-mode p", p, 0.834, tol=0.10),
            check("returns-by-mode Cramers V", v, 0.005, tol=0.50, fmt="{:.4f}")]

# ------------------------------------------------- 3.5 warehouse table
rule("3.5  Worst-performing warehouses (report flags WH011, WH010, WH004)")
wh = df.groupby("warehouse_id").agg(
    shipments=("delivery_status", "size"),
    on_time_pct=("delivery_status", lambda s: (s == "On Time").mean() * 100),
).sort_values("on_time_pct")
log(f"  {'warehouse':<12}{'shipments':>11}{'on-time %':>12}")
for w, r in wh.head(5).iterrows():
    log(f"  {str(w):<12}{int(r['shipments']):>11,}{r['on_time_pct']:>12.2f}")
for w, (n, ot) in {"WH011": (1145, 49.35), "WH010": (1478, 50.54),
                   "WH004": (2845, 52.30)}.items():
    if w in wh.index:
        results += [check(f"{w} shipments", wh.loc[w, "shipments"], n, tol=0.01, fmt="{:,.0f}"),
                    check(f"{w} on-time %", wh.loc[w, "on_time_pct"], ot, tol=0.02)]

ok = sum(1 for r in results if r)
log()
log("=" * 92)
log(f"RESULT: {ok}/{len(results)} figures reproduce insights_report.md")
log("=" * 92)

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nwrote {REPORT}")
