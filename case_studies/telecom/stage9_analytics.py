"""
Stage 9 -- ANALYTICS: General EDA (auto-selected, unattended run)
Dataset: viz_ready.csv (3,333 rows, 30 columns) -- telecom subscriber churn control case.

Produces every number cited in insights_report.md. Run with:
    python stage9_analytics.py
"""
import pandas as pd
import numpy as np
from scipy import stats

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

pd.set_option("display.width", 140)

df = pd.read_csv(str(_HERE / "viz_ready.csv"))

print("=" * 80)
print("0. SHAPE / SANITY")
print("=" * 80)
print(df.shape)
print(df["churn"].value_counts(dropna=False))

n = len(df)
n_churn = int(df["churn"].sum())
churn_rate = n_churn / n
# Wilson CI for churn rate
z = 1.959963984540054
phat = churn_rate
denom = 1 + z**2 / n
center = (phat + z**2 / (2 * n)) / denom
half = (z * np.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))) / denom
ci_lo, ci_hi = center - half, center + half

print(f"\nOverall churn rate: {n_churn}/{n} = {churn_rate:.4%}  (Wilson 95% CI: {ci_lo:.4%} - {ci_hi:.4%})")

print("\n" + "=" * 80)
print("1. BINARY CANDIDATE DRIVERS vs CHURN -- chi-square + Cramer's V + odds ratio")
print("=" * 80)


def binary_test(col):
    tab = pd.crosstab(df[col], df["churn"])
    chi2, p, dof, exp = stats.chi2_contingency(tab, correction=False)
    n_ = tab.values.sum()
    cramers_v = np.sqrt(chi2 / (n_ * (min(tab.shape) - 1)))
    # odds ratio: col=1 vs col=0, churn=1 vs churn=0
    a = tab.loc[1, 1] if 1 in tab.index and 1 in tab.columns else 0
    b = tab.loc[1, 0] if 1 in tab.index and 0 in tab.columns else 0
    c = tab.loc[0, 1] if 0 in tab.index and 1 in tab.columns else 0
    d = tab.loc[0, 0] if 0 in tab.index and 0 in tab.columns else 0
    # add 0.5 continuity correction if any cell is 0
    if min(a, b, c, d) == 0:
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    odds_ratio = (a * d) / (b * c)
    se_log_or = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    log_or = np.log(odds_ratio)
    or_ci_lo = np.exp(log_or - z * se_log_or)
    or_ci_hi = np.exp(log_or + z * se_log_or)
    churn_rate_1 = df.loc[df[col] == 1, "churn"].mean()
    churn_rate_0 = df.loc[df[col] == 0, "churn"].mean()
    print(f"\n--- {col} ---")
    print(tab)
    print(f"churn rate when {col}=1: {churn_rate_1:.4%} (n={ (df[col]==1).sum() })")
    print(f"churn rate when {col}=0: {churn_rate_0:.4%} (n={ (df[col]==0).sum() })")
    print(f"chi2={chi2:.3f}, dof={dof}, p={p:.3e}, Cramer's V={cramers_v:.4f}")
    print(f"odds ratio ({col}=1 vs 0) = {odds_ratio:.3f}  (95% CI {or_ci_lo:.3f}-{or_ci_hi:.3f})")
    return dict(col=col, test="chi-square", p=p, effect_name="Cramer's V", effect=cramers_v,
                odds_ratio=odds_ratio, or_lo=or_ci_lo, or_hi=or_ci_hi,
                churn_rate_1=churn_rate_1, churn_rate_0=churn_rate_0)


binary_results = []
for c in ["contract_renewal", "data_plan"]:
    binary_results.append(binary_test(c))

print("\n" + "=" * 80)
print("2. CONTINUOUS CANDIDATE DRIVERS vs CHURN -- Welch t-test + Mann-Whitney U + Cohen's d")
print("=" * 80)


def cohens_d(x, y):
    nx, ny = len(x), len(y)
    pooled_sd = np.sqrt(((nx - 1) * x.var(ddof=1) + (ny - 1) * y.var(ddof=1)) / (nx + ny - 2))
    return (x.mean() - y.mean()) / pooled_sd


def continuous_test(col):
    x = df.loc[df["churn"] == 1, col].dropna()
    y = df.loc[df["churn"] == 0, col].dropna()
    t, p_t = stats.ttest_ind(x, y, equal_var=False)  # Welch
    u, p_u = stats.mannwhitneyu(x, y, alternative="two-sided")
    d = cohens_d(x, y)
    print(f"\n--- {col} ---")
    print(f"churn=1: mean={x.mean():.3f}, median={x.median():.3f}, sd={x.std():.3f}, n={len(x)}")
    print(f"churn=0: mean={y.mean():.3f}, median={y.median():.3f}, sd={y.std():.3f}, n={len(y)}")
    print(f"Welch t={t:.3f}, p={p_t:.3e} | Mann-Whitney U p={p_u:.3e} | Cohen's d={d:.4f}")
    return dict(col=col, test="Welch t-test", p=p_t, mw_p=p_u, effect_name="Cohen's d", effect=d,
                mean_1=x.mean(), mean_0=y.mean())


continuous_results = []
for c in ["cust_serv_calls", "total_charge", "day_mins", "account_weeks", "roam_mins",
          "data_usage", "day_calls", "overage_fee", "monthly_charge"]:
    continuous_results.append(continuous_test(c))

print("\n" + "=" * 80)
print("3. RANKING BY EFFECT SIZE (not just p-value)")
print("=" * 80)
rank_rows = []
for r in binary_results:
    rank_rows.append((r["col"], "Cramer's V", r["effect"], r["p"]))
for r in continuous_results:
    rank_rows.append((r["col"], "Cohen's d", abs(r["effect"]), r["p"]))
rank_df = pd.DataFrame(rank_rows, columns=["col", "effect_metric", "effect_size", "p"])
rank_df = rank_df.sort_values("effect_size", ascending=False)
print(rank_df.to_string(index=False))

print("\n" + "=" * 80)
print("4. data_plan_usage_conflict_flag -- does splitting data_plan=0 change the story?")
print("=" * 80)
sub = df[df["data_plan"] == 0].copy()
print(f"data_plan=0 rows: {len(sub)}")
print(f"  of these, data_plan_usage_conflict_flag=True (data_usage>0 despite no plan): {sub['data_plan_usage_conflict_flag'].sum()} ({sub['data_plan_usage_conflict_flag'].mean():.2%})")

true_zero = sub[~sub["data_plan_usage_conflict_flag"]]
conflict = sub[sub["data_plan_usage_conflict_flag"]]
plan1 = df[df["data_plan"] == 1]

print(f"\nchurn rate, data_plan=1 (n={len(plan1)}): {plan1['churn'].mean():.4%}")
print(f"churn rate, data_plan=0 & true-zero usage (n={len(true_zero)}): {true_zero['churn'].mean():.4%}")
print(f"churn rate, data_plan=0 & conflict (usage>0) (n={len(conflict)}): {conflict['churn'].mean():.4%}")

# 3-group chi-square: plan1 vs true_zero vs conflict
three = df.copy()
three["segment"] = np.where(three["data_plan"] == 1, "plan=1",
                     np.where(three["data_plan_usage_conflict_flag"], "plan=0,usage>0(conflict)", "plan=0,usage=0(true_zero)"))
tab3 = pd.crosstab(three["segment"], three["churn"])
chi2_3, p_3, dof_3, exp_3 = stats.chi2_contingency(tab3, correction=False)
cramers_v_3 = np.sqrt(chi2_3 / (len(three) * (min(tab3.shape) - 1)))
print("\n3-segment crosstab:")
print(tab3)
print(f"chi2={chi2_3:.3f}, dof={dof_3}, p={p_3:.3e}, Cramer's V={cramers_v_3:.4f}")

# is conflict subpop different from true-zero subpop specifically (2-group)?
tab_conflict = pd.crosstab(sub["data_plan_usage_conflict_flag"], sub["churn"])
chi2_c, p_c, dof_c, exp_c = stats.chi2_contingency(tab_conflict, correction=False)
cramers_v_c = np.sqrt(chi2_c / (len(sub) * (min(tab_conflict.shape) - 1)))
print(f"\nWithin data_plan=0 only: conflict vs true-zero churn rate difference")
print(tab_conflict)
print(f"chi2={chi2_c:.3f}, p={p_c:.3e}, Cramer's V={cramers_v_c:.4f}")

print("\n" + "=" * 80)
print("5. Correlation sanity check: data_usage vs total_charge / day_mins (control-case flavor check)")
print("=" * 80)
for a, b in [("data_usage", "total_charge"), ("day_mins", "monthly_charge"), ("account_weeks", "total_charge")]:
    r, p = stats.pearsonr(df[a], df[b])
    print(f"pearson({a}, {b}) = {r:.4f}, p={p:.3e}")

print("\n" + "=" * 80)
print("6. Multivariate sanity: cust_serv_calls churn rate by call-count bucket (monotonic check)")
print("=" * 80)
bucket = pd.cut(df["cust_serv_calls"], bins=[-1, 0, 1, 2, 3, 4, 100], labels=["0", "1", "2", "3", "4", "5+"])
print(df.groupby(bucket, observed=True)["churn"].agg(["mean", "count"]))

print("\nDone.")
