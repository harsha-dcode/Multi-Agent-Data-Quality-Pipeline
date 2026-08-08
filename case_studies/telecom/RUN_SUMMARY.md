# RUN SUMMARY — telecom_churn.csv (control case)

**Input:** `<input>/telecom_churn.csv`
SHA-256 (first 16): `9ba8203038355a2a` — matches the provenance record in `case_studies/README.md`.
**Output directory:** `case_studies/telecom\`
**Run type:** Unattended (no user available mid-run). Every judgment call below is a stated
default, not a guess presented as fact.

This dataset is the **control case** in a 5-dataset benchmark: it was expected to already be
clean, and the point of running it is to prove the pipeline does not manufacture changes to look
productive. The result below is a genuine, verified near-zero-change run.

---

## Hard numbers

| Metric | Value |
|---|---|
| Raw rows | 3,333 |
| Raw columns | 11 |
| Cleaned rows (`cleaned_data.csv`) | 3,333 |
| Cleaned columns | 30 (11 original + `__source_row` + `total_charge` derived + 17 flag columns) |
| `viz_ready.csv` rows | 3,333 (0 dropped, 0.00%) |
| Cells scanned for disguised nulls | 36,663 (3,333 rows × 11 cols), 100% scan, not sampled |
| Disguised-null tokens found | **0** |
| Exact duplicate rows found/removed | **0** |
| Near-duplicate pairs flagged | N/A — no identifier column exists in this schema |
| Impossible negative values found | **0** (across all 8 checked columns) |
| Decimal-typo outlier corrections applied | **0** |
| Statistical outliers flagged (not modified) | **0** |
| Out-of-range values on closed code sets (`churn`, `contract_renewal`, `data_plan`) | **0** |
| Logical inconsistency flagged (`data_plan=0` & `data_usage>0`) | 602 / 3,333 rows (18.1%) — flagged, NOT corrected |
| Fuzzy-matching-eligible columns | **0** of 11 (collision guard run explicitly; no string/categorical columns exist) |
| Total `change_log.csv` rows | 615 (11 `HEADER_RENAME` + 602 `LOGICAL_INCONSISTENCY_FLAGGED` + 1 `DERIVED_COLUMN_ADDED` + 1 `COLUMN_REORDERED`) |
| Corrective value changes (any cell whose value was altered) | **0** |
| Validation checks run | 13 of 13 (V1–V13) |
| Validation checks PASS | 11 |
| Validation checks N/A | 2 (V7 email, V8 phone — no such columns exist in this schema) |
| Validation checks FAIL | 0 |
| Overall validation status | **READY FOR REPORTING** |
| Churn rate | 14.49% (483/3,333) |

---

## What was found, stage by stage

**Stage 1 (Business Brief).** Domain: telecom subscriber churn. Grain: one row per subscriber
account (no ID column exists — stated as an explicit assumption). Critical columns: `churn`
(target) and `monthly_charge` (closest field to a revenue figure). `churn`, `contract_renewal`,
`data_plan` set as closed `{0,1}` code sets with `never_impute`. `dangerous_columns: {}` — written
explicitly after running the collision guard, not left blank by default.

**Stage 2/3 (Extraction/Profiling).** Loaded with `dtype=str, keep_default_na=False` so pandas
never silently interpreted anything as null. Every one of 36,663 cells was cast to string,
stripped, case-folded, and compared against the full 14-token null-disguise set — 0 hits, verified
two independent ways (full scan + direct `==''` cross-check). File hash matches the benchmark's
recorded provenance for this input.

**Stage 4 (Cleaning).** Collision guard run explicitly against all 11 columns before any fuzzy
matching was attempted: 0 columns are string/categorical (the three flag columns are numeric
`{0,1}`, the rest are continuous numeric measures), so 0 columns were eligible and 0 fuzzy
corrections were made — reported explicitly rather than silently skipped, per the run's mandate.
Header normalization renamed all 11 PascalCase headers to snake_case (the only class of change
applied to every row). Numeric cleaning found no currency symbols, no thousands separators, no
locale ambiguity. Impossible-negative check: 0 negatives in any of 8 checked columns. Decimal-typo
outlier check (median-ratio test, screened at >10× median per column, verified >0 medians before
testing): 0 candidates cleared the 10× threshold in any column. Exact-duplicate check: 0 of 3,333
rows are byte-identical across all 11 data columns. Near-duplicate check: N/A, no identifier
column exists to compare. One genuine issue was found and investigated: 602 rows (18.1% of all
rows, 25.0% of `data_plan=0` rows) have `data_plan=0` but `data_usage>0`. This was judged a
plausible legitimate telecom behavior (residual/basic data usage without a formally billed plan),
not a data defect — both values were **flagged for visibility, not corrected**. Stage 9's
independent statistical check on this population (§3.3 of `insights_report.md`) found it churns at
13.5% vs 17.8% for true-zero-usage no-plan accounts — a real, small, significant difference that
supports (without proving) the "not an error" judgment.

**Stage 5 (Validation).** All 13 checks run, not a subset. 11 PASS. V7 (email validity) and V8
(phone compliance) report N/A because this schema has no email or phone column — a fact about the
schema, not a skipped check. V6 (outlier handling did not reshape the distribution) shows exactly
0.0000% median/IQR shift on every one of the 8 columns checked, which is the expected and correct
result given 0 corrections were applied to any of them — this is the check that would have caught
a bad decimal-typo repair, and it had nothing to catch.

**Stage 7 (Transformation).** Final dtypes re-affirmed (all 11 already matched Stage 4's cast — 0
additional `DTYPE_CAST` entries needed). One derived column added: `total_charge = monthly_charge
+ overage_fee`, applied uniformly and logged once (not once per row, since it is a deterministic
formula, not a row-level correction). Columns reordered: `__source_row` → categorical descriptors
→ numeric measures → derived → flags. Final null check: 0 nulls anywhere, so 0
`NULL_FLAGGED_NOT_IMPUTED` and 0 `NULL_IMPUTED` entries — nothing to flag or impute.
`__source_row` preserved through the index reset, confirmed unique and row-count-matched.

**Stage 8 (Pre-viz prep).** 17 flag columns inventoried (8 `*_sign_flag`, 8 `*_outlier_flag`, 1
`data_plan_usage_conflict_flag`) — this is not the zero-flag-columns bug scenario; flag columns
exist, they are simply mostly all-False, which is a different and valid state. Filter basis: the
8 `*_sign_flag` columns (physically impossible negatives) — all True-count 0, nothing to filter.
`*_outlier_flag` columns kept per spec default (statistical oddity, not impossibility) — moot here,
all 0. `data_plan_usage_conflict_flag` kept — both underlying values are individually valid and
in-range; forcing one to be "wrong" would be guessing. Result: `viz_ready.csv` is row-identical to
`cleaned_data.csv`, 0 rows dropped (0.00%).

**Stage 9 (Analytics).** Delegated to `@analytics-expert` (confirmed real invocation, ran to
completion — no fallback needed). General EDA, auto-selected and labeled as such since this is an
unattended run. Every claimed correlate was tested (chi-square/Cramer's V/odds ratio for binary
predictors, Welch's t-test + Mann-Whitney + Cohen's d for continuous ones), ranked by effect size
rather than raw p-value given n=3,333. Strongest signal: `cust_serv_calls ≥ 4` is a sharp
churn-rate threshold (11.3% → 51.7%, Cramer's V=0.31, OR=8.4). Second: `contract_renewal=0`
(11.5% → 42.4% churn, OR=0.176 for renewal), flagged as correlational, not provably causal, since
this dataset has no date field to establish sequence. Two genuine nulls reported: `account_weeks`
(tenure) and `day_calls` both show no relationship to churn (p=0.34, p=0.32) — stated plainly
rather than omitted. Report explicitly notes that because 0 rows were filtered and 0 values were
corrected in cleaning, none of its statistics reflect a cleaning artifact.

---

## Independent verification performed

`07_verify_writeback.py` re-derived every number above directly from the on-disk CSVs (not from
the cleaning scripts' own console output), per the rule that a step reporting success is not
evidence it worked:
- `total_charge` write-back mismatches: 0 (every one of 3,333 rows checked, not sampled)
- `data_plan_usage_conflict_flag` write-back mismatches: 0
- Non-snake_case headers remaining: none
- `cleaned_data.csv` and `viz_ready.csv` cover identical `__source_row` sets: True

`05_validate.py` independently recomputes V1–V13 from `_raw_str_with_source_row.pkl`,
`cleaned_data.csv`, and `change_log.csv` — it does not trust `03_clean.py`'s or `04_transform.py`'s
own printed claims.

---

## Assumptions made unattended (stated, not asked)

1. No account/customer ID exists in this schema; row identity is carried by `__source_row` alone.
   If an ID column was dropped upstream of this file, duplicate-row detection cannot distinguish
   "same subscriber logged twice" from "two different subscribers with identical rounded features."
   0 exact duplicates were found either way, so this did not end up mattering for this run.
2. `data_plan_usage_conflict_flag` rows (602) were flagged, not corrected — per the mission rule
   against guessing which of two individually-valid columns is "wrong."
3. Currency for `monthly_charge`/`overage_fee` assumed USD (consistent with this schema's known
   public origin); not stated explicitly anywhere in the raw file itself.

---

## Output directory contents (verified via `08_final_check.py`)

| File | Bytes |
|---|---:|
| `01_business_brief.yaml` | 8,008 |
| `cleaned_data.csv` | 519,151 |
| `viz_ready.csv` | 516,119 |
| `change_log.csv` | 157,432 |
| `validation_report.md` | 5,402 |
| `insights_report.md` | 17,492 |
| `RUN_SUMMARY.md` | (this file) |

Plus numbered, reproducible scripts: `00_peek.py`, `02_extract_profile.py`, `03_clean.py`,
`04_transform.py`, `05_validate.py`, `06_viz_ready.py`, `07_verify_writeback.py`, `07_eda.py`
(Stage 9, written by `@analytics-expert`), `08_final_check.py` — and their companion `*_report.txt`
outputs. The run reproduces end-to-end from this folder alone by running the numbered scripts in
order.

---

## Bottom line

This run found **zero data quality defects** requiring correction: no disguised nulls, no
duplicate rows, no impossible negatives, no decimal-typo outliers, no out-of-range closed-code-set
values, and no columns eligible for (or requiring) fuzzy matching. The only substantive finding
was a 602-row logical-inconsistency pattern that was investigated, judged legitimate, and flagged
rather than silently corrected. `viz_ready.csv` is row-identical to the raw input. This is the
correct and expected outcome for the benchmark's control case, and — per the mandate for this run —
it is reported as an honest zero, not padded with manufactured changes.
