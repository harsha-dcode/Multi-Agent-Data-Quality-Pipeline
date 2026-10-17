# Telecom Subscriber Churn — Insights Report

**Scope:** General EDA (auto-selected, unattended run) — no user was available to choose a
narrower focus (a/b/c/d/e), so this report covers churn rate, churn correlates, and pipeline
findings broadly.

**Source:** `viz_ready.csv` (3,333 rows, 30 columns), the filtered chart-ready view. 0 rows were
removed between raw input and this file (see §4). All numbers below are reproducible via
`stage9_analytics.py` in this folder.

---

## 1. The headline

14.5% of the 3,333 subscribers in this snapshot churned (483/3,333, 95% CI 13.3%–15.7%). Two
signals stand out clearly above sampling noise and are worth acting on: **customer-service-call
volume** and **contract non-renewal**. Subscribers who called support 4+ times churn at 51.7% vs
11.3% for 0–3 calls (chi-square p=1.9e-72, Cramer's V=0.31, odds ratio 8.4x) — this is a sharp
threshold, not a gentle slope, and it is the single most actionable pattern in the data. Contract
non-renewal is the second-largest lever: 42.4% churn vs 11.5% among renewers (p=7.1e-51,
odds ratio 0.176 for renewal, i.e. renewing cuts churn odds by ~82%). A cluster of billing/usage
variables (day_mins, total_charge, overage_fee, monthly_charge, data_usage, roam_mins) are all
statistically significant but individually weak (Cohen's d 0.19–0.26) and are mutually correlated
(they are arithmetic/behavioral siblings of each other), so they should be read as one blurry
"heavy, high-billing user" signal, not five independent drivers. Tenure (account_weeks) and daytime
call count (day_calls) show **no relationship to churn** (p=0.34 and p=0.32) — a genuine null worth
stating plainly, since "long-tenured customers don't churn" is a common but here-unsupported
assumption. Recommendations below name the intervention, the owner, and the number that would
prove each one wrong.

---

## 2. Recommendations

### R1 — Route accounts with 4+ customer-service calls into a retention/save-desk workflow, not a normal support queue
- **Do what:** Flag any account that reaches its 4th customer-service call in a rolling window
  (or lifetime, given this is a snapshot) for proactive retention outreach — not just call
  resolution. Treat "4th call" as a churn-risk trigger event, analogous to a fraud-score threshold.
- **Why:** Churn rate jumps from 11.3% (0–3 calls, n=3,066) to 51.7% (4+ calls, n=267) —
  chi-square p=1.9e-72, Cramer's V=0.31 (medium-large), odds ratio 8.4x. This is the strongest
  and cleanest signal in the dataset — a sharp threshold rather than a gradual trend (see §3,
  bucketed churn-rate table: 13.2%, 10.3%, 11.5%, 10.3%, 45.8%, 61.4% for 0/1/2/3/4/5+ calls).
- **Who:** Customer retention / call-center operations owner. This is an operational routing rule,
  not a modeling change — it can be implemented as a simple counter-based trigger in the CRM/call
  system today.
- **Cost / risk:** Low cost (a routing rule + retention-team capacity for ~267/3,333 = ~8% of the
  base). Risk if wrong: retention outreach is offered to accounts who were never going to churn,
  wasting agent time — bounded and recoverable, not dangerous.
- **Falsified if:** On a fresh cohort, the 4+ calls vs 0–3 calls churn-rate gap closes to a small,
  non-significant difference (e.g. chi-square p>0.05 or odds ratio near 1), or if outreach to the
  4+ group fails to move their churn rate in a controlled trial.

### R2 — Investigate and address root causes of contract non-renewal before it happens, not after
- **Do what:** Build an early-warning trigger on contract come-up-for-renewal date (not present in
  this schema, so this also doubles as a data-collection ask — see §5) and prioritize renewal
  outreach for accounts approaching that date, since failing to renew is strongly associated with
  churn.
- **Why:** Churn rate is 42.4% among the 323 accounts with `contract_renewal=0` vs 11.5% among the
  3,010 with `contract_renewal=1` (chi-square p=7.1e-51, Cramer's V=0.26, odds ratio 0.176 for
  renewal — i.e. non-renewal roughly quadruples churn odds). This is correlational: renewal could
  be a cause of retention (contractual lock-in) or a symptom of an already-satisfied customer: the
  data cannot distinguish these (see §5).
- **Who:** Retention / contracts team, working with whoever owns the renewal-offer process
  upstream.
- **Cost / risk:** Moderate — building a renewal-date-triggered workflow requires a renewal-date
  field this dataset does not have. Risk if wrong: over-invests in renewal incentives for accounts
  that would have stayed anyway (reverse causality is plausible here — see §5).
- **Falsified if:** A controlled renewal-incentive trial shows no reduction in churn among
  treated accounts relative to a matched control, or if a time-ordered dataset shows renewal status
  is set *after* the churn decision is already effectively made (which would flip the causal story).

### R3 — Treat the day_mins / total_charge / overage_fee / monthly_charge / data_usage / roam_mins cluster as one "heavy-usage/high-bill" signal in any churn model, not six independent features
- **Do what:** If this dataset feeds a churn-prediction model, do not include all six billing/usage
  variables as independent linear-model predictors without checking collinearity (e.g. VIF) —
  `total_charge` is arithmetically `monthly_charge + overage_fee`, and `data_usage` correlates with
  `total_charge` at r=0.74 (p≈0). Consider a single composite feature or a tree-based model that
  handles collinearity natively.
- **Why:** All six are statistically significant vs churn (p from 9e-5 to 1e-20) but each has a
  small individual effect size (Cohen's d 0.19–0.26 — day_mins is the exception at d=0.60, see §3
  table). Because they are correlated with each other, their apparent statistical "significance"
  in a naive multi-variable model would overstate how many independent signals are actually
  present.
- **Who:** Whoever builds the downstream churn-prediction model (data science team).
- **Cost / risk:** Low — this is a modeling-hygiene note, not an operational change. Risk if
  ignored: an unregularized logistic regression could produce unstable, hard-to-interpret
  coefficients on these six correlated features.
- **Falsified if:** A VIF check on these six columns comes back low (e.g. all <5), showing the
  collinearity concern is smaller than the derivation formula suggests.

### R4 — Do not build a tenure-based (account_weeks) retention program off this data
- **Do what:** If a retention program is currently being scoped around "long-tenure customers are
  safe" or "short-tenure customers are risky," stop and do not fund it on the strength of this
  dataset.
- **Why:** account_weeks shows no relationship to churn — Welch t-test p=0.34, Mann-Whitney
  p=0.37, Cohen's d=0.047 (essentially zero). Mean tenure is 102.7 weeks for churners vs 100.8
  weeks for non-churners — a trivial, non-significant gap. This is a genuine null, not a failure
  to find a test.
- **Who:** Whoever is prioritizing retention-program budget by customer segment.
- **Cost / risk:** None — this recommendation is "don't spend money here," which only saves cost.
- **Falsified if:** A larger sample, or a differently-sliced tenure variable (e.g. tenure buckets
  rather than a linear read), shows a significant and non-trivial effect (e.g. p<0.05 with
  |Cohen's d|>0.2).

---

## 3. Business findings

### 3.1 Overall churn rate
483 of 3,333 subscribers churned = **14.49%** (Wilson 95% CI: 13.34%–15.73%).

### 3.2 Churn correlates, ranked by effect size (not raw p-value)

All tests run on the full 3,333-row viz_ready.csv. Binary predictors tested with chi-square
(reporting Cramer's V and odds ratio); continuous predictors tested with Welch's t-test and
Mann-Whitney U as a robustness check (reporting Cohen's d). At n=3,333, p-values below 1e-4 are
common even for small effects — effect size is the primary ranking criterion here, per the
large-n-trivial-effect caveat.

| Rank | Variable | Test | p-value | Effect size | Interpretation |
|---|---|---|---|---|---|
| 1 | **cust_serv_calls ≥ 4 (threshold)** | chi-square | 1.91e-72 | Cramer's V = 0.31, OR = 8.44 | Strongest signal in the dataset — a sharp threshold, not a slope |
| 2 | cust_serv_calls (continuous) | Welch t / Mann-Whitney | 5.27e-18 / 3.06e-15 | Cohen's d = 0.61 (medium) | Confirms #1; linear version understates the threshold's sharpness |
| 3 | day_mins | Welch t / Mann-Whitney | 1.22e-20 / 6.72e-23 | Cohen's d = 0.60 (medium) | Churners use more daytime minutes (207 vs 175 mean) |
| 4 | contract_renewal | chi-square | 7.15e-51 | Cramer's V = 0.26, OR = 0.176 | Small marginal (only 323/3,333 non-renewers) compresses V, but the absolute churn-rate gap (42.4% vs 11.5%) is the second-largest practical effect in the data |
| 5 | overage_fee | Welch t / Mann-Whitney | 1.83e-07 / 3.17e-07 | Cohen's d = 0.26 (small) | Part of the billing cluster, see R3 |
| 6 | data_usage | Welch t / Mann-Whitney | 6.96e-08 / 3.81e-09 | Cohen's d = -0.25 (small) | Direction is counterintuitive: churners use *less* data (0.55 GB vs 0.86 GB mean) |
| 7 | total_charge | Welch t / Mann-Whitney | 2.35e-06 / 3.03e-09 | Cohen's d = 0.23 (small) | Billing cluster, see R3 |
| 8 | monthly_charge | Welch t / Mann-Whitney | 2.41e-05 / 4.66e-08 | Cohen's d = 0.21 (small) | Billing cluster, see R3 |
| 9 | roam_mins | Welch t / Mann-Whitney | 9.07e-05 / 4.44e-04 | Cohen's d = 0.19 (small, borderline) | Weakest of the significant billing/usage variables |
| 10 | data_plan | chi-square | 3.70e-09 | Cramer's V = 0.10 (small), OR = 0.473 | See §3.3 — this headline number masks a more nuanced split |
| 11 | day_calls | Welch t | 0.317 | Cohen's d = 0.052 | **Null** — no relationship to churn |
| 12 | account_weeks (tenure) | Welch t | 0.337 | Cohen's d = 0.047 | **Null** — no relationship to churn (see R4) |

`cust_serv_calls` bucketed churn rate (the basis for the threshold finding in rank #1):

| calls | 0 | 1 | 2 | 3 | 4 | 5+ |
|---|---|---|---|---|---|---|
| churn rate | 13.2% | 10.3% | 11.5% | 10.3% | 45.8% | 61.4% |
| n | 697 | 1,181 | 759 | 429 | 166 | 101 |

The rate is flat (~10–13%) through 0–3 calls and then jumps sharply at 4+ — this is why the
threshold framing (R1) is more useful operationally than treating call count as a smooth linear
driver.

### 3.3 data_plan as a churn driver, disaggregated by the conflict flag (required caveat, see §4)

The headline `data_plan` chi-square (rank #10 above, V=0.10) treats `data_plan=0` as one
homogeneous group. Splitting it using `data_plan_usage_conflict_flag` changes the picture:

| Segment | n | churn rate |
|---|---|---|
| data_plan=1 | 922 | 8.68% |
| data_plan=0, true-zero usage (no conflict) | 1,809 | 17.80% |
| data_plan=0, usage>0 despite no plan (conflict, 602 rows) | 602 | 13.46% |

A 3-way chi-square across these segments is significant (chi2=41.7, p=9.0e-10, Cramer's V=0.11).
Restricted to just the two `data_plan=0` sub-segments, the conflict group churns significantly
less than the true-zero group (chi-square p=0.013, Cramer's V=0.050 — significant but very small).
**Read:** the "conflict" population (residual/unbilled data usage without a formal plan) behaves
more like an intermediate-risk group than like the rest of the no-plan population — consistent
with the Stage-1 judgment that this is plausible legitimate behavior, not a data error. This
doesn't overturn `data_plan` as a weak-to-moderate churn correlate, but a churn model that uses
raw `data_plan` as a single binary feature is throwing away a small, real distinction between
these two `data_plan=0` sub-populations.

### 3.4 Genuine null results

- **account_weeks (tenure):** p=0.337, Cohen's d=0.047 — no evidence tenure predicts churn in this
  snapshot. Common industry intuition ("loyal long-tenure customers don't leave") is **not
  supported** by this data.
- **day_calls:** p=0.317, Cohen's d=0.052 — call volume during the day (as opposed to
  service-call volume) has no relationship to churn. Only the *service*-call count matters (§3.2
  rank #1–2), not general call activity.

Both are worth stating explicitly: a retention strategy targeted at "recently-joined" or
"heavy-daytime-caller" segments would not be supported by evidence in this dataset.

### 3.5 A note on the billing-cluster's internal correlation (bearing on R3)

`data_usage` and `total_charge` correlate at r=0.74 (p≈0); `day_mins` and `monthly_charge`
correlate at r=0.57 (p=4.7e-284). `total_charge` is a derived sum (`monthly_charge + overage_fee`,
per Stage 4 transform), so part of this correlation is definitional, not behavioral. This is why
§3.2 ranks #4–9 are presented as one blurred signal (R3) rather than six independent findings —
treating them as independent would overstate the number of distinct drivers present.

---

## 4. Operational findings (from the pipeline)

This is the **control case** in a 5-dataset cleaning benchmark (per `01_business_brief.yaml`):
the dataset was asserted clean going in, and the pipeline's job was to prove it does not
manufacture changes on clean input. The record from `validation_report.md` and
`06_viz_ready_report.txt` supports that:

- **0 rows removed** (raw 3,333 → viz_ready 3,333, 0.0% filtered). No exact duplicates, no
  physically-impossible negatives, no decimal-typo outliers, no disguised nulls found anywhere
  in the 3,333 × 12 raw-column scan.
- **0 corrective value changes** logged in `change_log.csv`. Of 615 total change-log rows, 0 are
  value corrections; the only non-structural entries are 602 non-destructive
  `data_plan_usage_conflict_flag` = True flags (raised for visibility, not corrected — see §3.3).
- **Distribution-shift check (V6) passed at 0.0000%** median/IQR shift across all 8
  outlier-checked columns, because 0 statistical-outlier or decimal-typo corrections were applied.
- **Because 0 rows were filtered and 0 values were corrected, there is no risk in this report of
  cleaning decisions having silently reshaped the distributions being analyzed.** This is a
  meaningfully different (and stronger) evidentiary position than a dirtier dataset would carry —
  every number in §3 reflects the raw distribution directly, not a cleaned/imputed/filtered
  approximation of it.
- **The one substantive flag** raised was `data_plan_usage_conflict_flag` (602/3,333 = 18.1% of
  all rows; 602/2,411 = 25.0% of `data_plan=0` rows), covering rows where `data_plan=0` but
  `data_usage>0`. Stage 1/4 judged this a plausible legitimate telecom behavior (residual/trial
  usage without a formal paid plan) rather than a data error, and both the plan and usage values
  were kept as-is. §3.3 above tests whether this population behaves differently with respect to
  churn — it does, modestly (Cramer's V=0.05 within the `data_plan=0` group), which is consistent
  with, but does not prove, the "not an error" judgment.
- **What this implies about the source system:** nothing needs fixing upstream for this dataset —
  that is itself the operational finding. Unlike the other four datasets in this benchmark, there
  is no form-validation bug, column-mapping defect, or clock/timezone issue to report here. If
  this control case had instead shown injected defects, that would indicate a pipeline bug in the
  cleaning stages, not a source-system problem — it did not.

---

## 5. What we cannot say

- **Causality on contract_renewal (R2).** The data cannot distinguish "non-renewal causes churn"
  from "customers who were already planning to leave decline to renew" (reverse causality) — both
  produce the same cross-sectional association. Answering this requires **time-ordered data**:
  the date of the renewal decision relative to the date of the churn event, which this snapshot
  does not carry (there is no date column in this schema at all, confirmed in `01_business_brief.yaml`).
- **No account/customer identifier exists** (confirmed in the business brief and Stage 4.11 dup
  check). This is a single-snapshot, one-row-per-account file — there is no way to observe
  behavior change *leading up to* churn (e.g., did service calls spike in the weeks before churn,
  or was a high call count simply a stable trait of some accounts?). A panel/longitudinal version
  of this dataset (repeated observations per account over time) would let R1 and R2 be tested as
  *leading* indicators rather than concurrent correlates.
- **No cost data on retention outreach.** R1's cost/risk section is qualitative because this
  dataset has no cost-per-outreach or historical save-rate field to quantify ROI.
- **Why data_usage is *negatively* associated with churn** (§3.2 rank #6 — churners use *less*
  data on average) is not something this dataset can explain; it is counterintuitive and worth
  flagging for human review before anyone builds a "high data usage = high risk" narrative — the
  opposite is what the data shows.
- **Whether this pattern generalizes beyond this snapshot.** This is one static file; no
  train/test time split or holdout was evaluated (no date field exists to build one), so none of
  the effect sizes above should be read as predictive-model performance metrics.

---

*Reproducibility: every statistic in this report was computed by `stage9_analytics.py` in this folder, run
against `viz_ready.csv`. Re-run with `python stage9_analytics.py` to regenerate all numbers.*
