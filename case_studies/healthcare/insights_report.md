# Healthcare Admissions — Insights Report

**Scope:** General EDA (auto-selected, unattended run) — Stage 9 of the Multi-Agent Data Quality
Pipeline. No user was available to choose between General EDA / KPIs / hypothesis testing /
forecasting / all; per this pipeline's documented unattended-run convention, General EDA is the
default.

**Dataset analysed:** `viz_ready.csv` — 54,470 rows × 67 columns (the filtered, chart-ready view;
1,404 rows physically-impossible or null-chart-key rows were already removed by Stage 8, see Data
Quality Caveats §7). **Not real PHI** — this is a synthetic, Kaggle-style, defect-injected
hospital-admissions dataset built for BI-dashboard / analytics-portfolio demonstration, not
clinical or regulatory use.

All numbers below were computed directly from `viz_ready.csv` with pandas/scipy (chi-square
goodness-of-fit, chi-square independence with Cramér's V, one-way ANOVA with η², Welch's t-test
with Cohen's d, Pearson/Spearman correlation). No number in this report is estimated or eyeballed.

---

## 1. The headline

**This dataset carries no usable business signal.** Every demographic, clinical, and financial
cross-cut tested — 17 tests in total — came back statistically null or with a negligible effect
size (all p > 0.10 except three inflated by tiny residual-garbage categories, corrected in §3;
after correction, every one of the 17 is null). Gender is 50.05%/49.95% male/female (p=0.877),
blood type is uniform across all 8 canonical types (p=0.979), medical condition is uniform across
all 6 conditions (p=0.931), test result is independent of condition (Cramér's V=0.011), admission
type (V=0.004), and gender (V=0.006), and billing amount is uncorrelated with length of stay
(r=-0.002, p=0.596) or age (r=-0.002, p=0.577). This is the signature of independently-drawn
synthetic fields, not a real hospital population — say so plainly rather than manufacturing a
"finding" from noise (see §3, §6, §7).

**What is actionable is entirely on the operational/pipeline side.** Two things deserve real
follow-up: (1) 16.94% of rows (9,227 of 54,470) share a full name+date+doctor+hospital key, and in
97.1% of the comparable duplicate groups the billing_amount is byte-for-byte identical across
every member — that is not two real, independent admissions coinciding, that is a duplicate
record from an upstream double-write, and it was flagged but never removed because no true unique
ID exists in this source (§6, §7). (2) The gender/blood_type and test_results/medication
column-swap bug that the pipeline auto-corrected for ~590 rows still has 27 residual rows where
the swap logic couldn't confidently reverse a leaked value (§7) — worth fixing at the export
source, not just patching downstream forever.

---

## 2. Recommendations

**No domain/clinical/demographic business recommendation is supported by this data (see R5 and
§3, §4, §5 for the full null-result inventory).** The recommendations below are therefore
operational and data-governance actions — they are what the pipeline's own damage record, not the
clean numbers, actually supports.

### R1 — Treat the 9,227 near-duplicate-key rows as a likely double-write bug, not legitimate repeat admissions, and investigate the ingest/export path
- **Do what:** Have data engineering trace the write path for records sharing
  (name, date_of_admission, doctor, hospital) — check for retried API writes, ETL replay, or
  export-job re-runs that append instead of upsert. Do **not** blanket-delete these rows yet
  (see Falsified-if).
- **Why:** 9,227 of 54,470 viz_ready rows (16.94%) share this composite key across 4,635 groups.
  Of the 4,490 groups where billing_amount is comparable across members, 4,361 (97.1%) have an
  **identical** billing_amount to the cent across every member, and of 4,494 comparable groups,
  100% share the same room_number. Billing_amount is drawn from what looks like a continuous
  distribution — two genuinely independent admissions coinciding on the exact same dollar figure
  *and* the same room *and* the same doctor *and* the same date is not plausible by chance.
- **Who:** Data engineering / ETL team owning the export job that produces
  `healthcare_dataset_dirty_export.csv`.
- **Cost/risk:** Low engineering cost to add logging/idempotency keys and audit the write path.
  Risk of acting wrong: patients genuinely *can* be readmitted with a coincidentally similar bill,
  so deleting on this signal alone without confirming against source-system encounter IDs could
  destroy real data — pipeline was right to flag-not-remove pending a true unique key (brief A2).
- **Falsified if:** Checking a sample of these duplicate-key groups against source-system
  timestamps/logs shows genuinely distinct transaction or encounter IDs for each row — i.e., if a
  hidden unique identifier upstream proves these are two real events, this is not a duplication
  bug and the flag should stay informational-only.

### R2 — Fix the gender↔blood_type and test_results↔medication column-swap bug at the export source; the pipeline's mechanical un-swap already caught the bulk, but leaves residual unfixable rows every run
- **Do what:** Have the export/schema-mapping owner check whether `gender`/`blood_type` and
  `test_results`/`medication` are adjacent columns in the source query or file layout — a
  column-ordering or off-by-one mapping bug is the most likely mechanical cause of a systematic
  two-column swap (nobody types "B+" into a gender field or "Ibuprofen" into a test-results
  field).
- **Why:** `blood_gender_swap_corrected_flag` = 276 rows and
  `test_results_medication_swap_corrected_flag` = 314 rows were successfully auto-corrected in
  this run (mechanically un-swapped). But 13 rows remain uncorrected in the gender/blood_type pair
  (`gender_unresolved_category_flag`=8 rows still holding blood-type-like values such as B+, A-,
  O-, AB+, AB-, O+; `blood_type_unresolved_category_flag`=5 rows still holding "Male"/"Female"),
  and 14 rows remain uncorrected in the test_results/medication pair
  (`test_results_unresolved_category_flag`=5 rows holding medication-like values including a
  misspelled "Pencillin"; `medication_unresolved_category_flag`=9 rows holding "Abnormal" /
  "Inconclusive" / "Normal"). These residuals escaped fuzzy-match correction and will recur on
  every future extract until the mapping bug itself is fixed.
- **Who:** Source-system export/ETL owner (upstream of this pipeline's Stage 2 extraction).
- **Cost/risk:** Low — a schema/query fix. If not fixed, expect ~0.5–0.7% of rows per future
  extract to need this same swap-correction pass indefinitely, plus a small irreducible residue
  (~13–14 rows this run) requiring manual review each time.
- **Falsified if:** Inspecting the export query/schema shows gender/blood_type (or
  test_results/medication) were never adjacent columns — ruling out a mechanical column-shift and
  pointing instead to a different origin (e.g., manual re-keying error), which would need a
  different fix.

### R3 — Do not build a "billing per day of stay" dashboard tile with this data
- **Do what:** Exclude any billing_amount ÷ length_of_stay derived metric from the BI dashboard
  this project is meant to demonstrate.
- **Why:** length_of_stay and billing_amount are statistically independent
  (Pearson r=-0.0023, p=0.596, n=52,160; Spearman ρ=-0.0023, p=0.602, tested on the
  billing-sign-clean subset, §5). Dividing by an unrelated variable does not reveal a real daily
  rate, it amplifies noise: the derived per-day series has a coefficient of variation of 1.71
  versus 0.55 for billing_amount alone — i.e., ~3x noisier relative to its own mean.
- **Who:** Whoever builds/owns the BI-dashboard demonstration (this pipeline's stated end use).
- **Cost/risk:** Free to skip. If built anyway, a viewer is likely to read a noisy ratio as a
  meaningful "cost efficiency" KPI, which is a credibility risk the moment anyone checks the
  underlying correlation.
- **Falsified if:** A future data refresh (e.g., swapping in real EHR/billing data instead of this
  synthetic generator) shows length_of_stay and billing_amount are no longer independent — then
  the ratio becomes meaningful and this recommendation should be revisited.

### R4 — Document one explicit rule for whether billing totals include the 190 uncorrected negative billing_amount rows, and apply it consistently across every downstream chart/rollup
- **Do what:** Pick and document (e.g., in a dashboard data dictionary) whether "total billing" =
  gross charges including credits/refunds, or gross charges only — then apply the same choice
  everywhere billing is summed or averaged.
- **Why:** Per business rule BR2, the 190 rows flagged by `billing_amount_sign_flag` were left
  **uncorrected** (not sign-flipped) because a negative charge could legitimately be a refund or
  credit. Including vs excluding them changes total billing by $2,150,403.83 (0.157% of the
  $1,373,357,879.08 excluding-negatives total) and mean billing by ~$130 (25,451.17 vs
  25,581.30) — small, but enough that two people computing "total billing" independently will get
  different numbers unless the rule is written down.
- **Who:** Owner of the billing/finance-facing dashboard view.
- **Cost/risk:** Essentially free — a documented toggle/definition. Risk of skipping it is a small
  but real reproducibility gap, not a large financial misstatement.
- **Falsified if:** Someone can confirm from the source system that these 190 rows are data-entry
  errors rather than refunds (e.g., no matching credit-memo reference exists) — in that case they
  should be corrected or excluded outright rather than governed by a business rule that assumes
  they might be legitimate.

### R5 — When presenting this project, state plainly that the domain signal is null and why, rather than reporting a subgroup pattern as a finding
- **Do what:** In any portfolio write-up or interview discussion of this project, lead with "the
  synthetic generator produced independent, uniform fields — no demographic/clinical/financial
  relationship was detectable" rather than cherry-picking one of the 17 tests that happened to
  land under p=0.05 by chance.
- **Why:** Every cross-cut tested came back null or negligible once contaminating garbage
  categories were excluded (§3, §7): gender 50.05/49.95% (χ²=0.024, p=0.877), blood type uniform
  8-way (χ²=1.60, p=0.979), medical_condition uniform 6-way (χ²=1.34, p=0.931), medication uniform
  5-way (χ²=1.04, p=0.903), test_results uniform 3-way (χ²=1.30, p=0.523), admission_type uniform
  3-way (χ²=3.67, p=0.159), length_of_stay uniform 1–30 (χ²=36.87, p=0.149); test_results vs.
  medical_condition (Cramér's V=0.011, p=0.252), vs. admission_type (V=0.004, p=0.800), vs. gender
  (V=0.006, p=0.441); medical_condition vs. gender (V=0.006, p=0.882); age Male vs. Female
  (Cohen's d=-0.004, p=0.610); length_of_stay vs. admission_type (η²=0.00006, p=0.230);
  billing_amount vs. medical_condition (η²=0.00017, p=0.109), vs. insurance_provider
  (η²=0.00004, p=0.763), vs. admission_type (η²=0.00001, p=0.759), vs. admission_year (p=0.651);
  length_of_stay vs. billing_amount (r=-0.002, p=0.596); age vs. billing_amount
  (r=-0.002, p=0.577). This uniform-marginals-plus-null-cross-cuts pattern everywhere is the
  signature of independently generated synthetic columns.
- **Who:** Whoever presents or interviews on this project.
- **Cost/risk:** None to state it. The risk of *not* stating it is presenting an apparent finding
  that is actually sampling noise — a reviewer who reruns the test gets the same null and the
  credibility cost is real.
- **Falsified if:** A larger sample, a different random seed of the same generator, or a switch to
  real hospital data shows a repeatable non-null pattern in one of these specific cuts — then it
  becomes a generator quirk worth documenting (not evidence of true randomness) or a real
  business finding (if from real data).

---

## 3. Business findings (from the data)

### 3.1 Admissions volume and trend
- Date range: 2019-01-06 to 2024-05-07. Both edge years are partial: 2019 has only 2 admissions in
  January and 1 each in March/April before volume ramps up to 671 in May (data collection
  effectively starts mid-2019); 2024 has full Jan–Apr coverage (~890/month) but only 214 in May
  before the extract cuts off on 2024-05-07.
- 2020–2023 are the four **complete** years (all 12 months present): 11,075 / 10,693 / 10,831 /
  10,841 admissions respectively — flat, no visible year-over-year growth or decline trend.
- **Raw pooled month-of-year counts look "significant"** (χ²=52.26, p<0.00001, df=11) — but this
  is an artifact of the partial 2019/2024 edge years distorting a few months' totals, exactly the
  kind of pattern this pipeline's own analysis bar warns against crediting at face value.
  Restricting to the 4 complete years (2020–2023) and re-running the same test: χ²=13.05, p=0.290.
  **No seasonal admissions pattern survives the normalization.** (Normalizing further by
  days-in-month barely moves the picture — 28.9 to 30.9 admissions/day across months — consistent
  with no real seasonality.)
- **Finding: flat admissions volume, no seasonality (p=0.290 on complete years).** This is a null
  result worth recording, not a gap in the analysis.

### 3.2 Demographics
- Age (excluding the 287 `age_domain_outlier_flag` rows, age>110): mean 51.20, median 51, IQR
  34–68, range 0–89, n=53,906. Including those 287 outlier rows pulls the mean up slightly to
  51.73 and the max to 150 — see §7 for why those rows are kept but should be excluded from any
  age summary.
- Gender (canonical Male/Female only, excluding 8 `gender_unresolved_category_flag` rows that
  hold leaked blood-type values, see §7): 27,057 Male / 27,021 Female, n=54,078. χ²=0.024,
  p=0.877 — statistically indistinguishable from 50/50.
- Blood type (canonical only, excluding 5 unresolved-category rows): uniform across all 8 types,
  6,693–6,820 each, χ²=1.60, p=0.979 (8-way goodness-of-fit) — essentially perfectly uniform.
- Age is independent of gender: Welch's t-test, Male mean 51.17 vs. Female mean 51.25, t=-0.51,
  p=0.610, Cohen's d=-0.004 (negligible). Medical condition is independent of gender (Cramér's
  V=0.006, p=0.882, n=54,078).

### 3.3 Clinical (condition / test results / medication)
- medical_condition: uniform across all 6 conditions (9,017–9,150 each), χ²=1.34, p=0.931.
- test_results (canonical only, excluding 5 unresolved rows holding leaked medication names):
  uniform across Abnormal/Normal/Inconclusive (17,891–18,107), χ²=1.30, p=0.523.
- medication (canonical only, excluding 9 unresolved rows holding leaked test_results values):
  uniform across all 5 medications (10,750–10,882), χ²=1.04, p=0.903.
- test_results is independent of medical_condition (χ²=12.52, p=0.252, dof=10, Cramér's
  V=0.011, n=53,998), independent of admission_type (χ²=1.65, p=0.800, dof=4, V=0.004), and
  independent of gender (χ²=1.64, p=0.441, dof=2, V=0.006). All negligible effect sizes on top of
  non-significant p-values — no clinical-outcome pattern exists to report.

### 3.4 Operational (admission type / length of stay)
- admission_type: near-uniform across Elective/Urgent/Emergency (17,949–18,292), χ²=3.67,
  p=0.159 — no significant skew.
- length_of_stay (authoritative column, all rows): mean 15.51 days, median 15, IQR 8–23,
  n=52,874. Restricted to the dominant 1–30 day range (52,855 of 52,874 non-null rows, 99.96%),
  the distribution is uniform: χ²=36.87, p=0.149. A small tail of 19 rows (1 at 0 days, 18 at
  31–36 days) sits outside that uniform range but is too small to characterize statistically.
- length_of_stay does **not** differ by admission_type: one-way ANOVA F=1.47, p=0.230,
  η²=0.000056 (Elective mean 15.52, Emergency 15.58, Urgent 15.43 — differences of a few tenths of
  a day, not clinically or operationally meaningful).
- length_of_stay_qa_mismatch_flag = 205 rows (0.38% of viz_ready) where the authoritative
  length_of_stay value disagrees with `discharge_date - date_of_admission` recomputed from the
  cleaned dates; mean absolute disagreement is 3.69 days on those 205 rows. Any LOS-based
  reporting should be aware the two candidate LOS values disagree here (see §7).

### 3.5 Financial (billing_amount)
- billing_amount, excluding the 190 negative-flagged rows: mean $25,581.30, median $25,593.87,
  std $14,188.53, n=53,686. Including the 190 negative rows: mean $25,451.17, n=53,876 (see §4 and
  R4 for the sign-inclusion caveat and its dollar impact).
- No relationship found between billing_amount and: medical_condition (one-way ANOVA F=1.80,
  p=0.109, η²=0.000168), insurance_provider (F=0.46, p=0.763, η²=0.000035), admission_type
  (F=0.28, p=0.759, η²=0.000010), or admission_year (F=0.66, p=0.651 — no inflation/trend across
  2019–2024).
- billing_amount is uncorrelated with length_of_stay (Pearson r=-0.0023, p=0.596, n=52,160;
  Spearman ρ=-0.0023, p=0.602) and with age (Pearson r=-0.0024, p=0.577, n=53,143, age-outlier
  rows excluded). See R3 — a per-day-of-stay billing metric would be actively misleading given
  this independence.
- insurance_provider is itself near-uniform across the 5 canonical providers (10,611–10,945),
  χ²=5.72, p=0.221.

---

## 4. Operational findings (from the pipeline)

These come from `03_stage4_report.txt`, `05_validate.py` / `validation_report.md`, and
`04_stage7_report.txt` — the cleaning log, not the clean file — and describe what was broken
upstream, not what the business looks like today.

- **Near-duplicate composite key, 9,227 rows in viz_ready (16.94%), 4,635 groups.** As detailed in
  R1, 97.1% of comparable groups share an identical billing_amount and 100% of comparable groups
  share the identical room_number across every member — strong evidence of upstream double-writes,
  not legitimate repeat admissions. The pipeline correctly declined to auto-delete these (no true
  unique patient/record ID exists in this source per the Stage 1 brief), but this analysis
  provides fresh evidence that the flag-not-remove decision should now be escalated to an actual
  ingest-path audit rather than left flagged indefinitely.
- **Two independent column-swap bugs**, both mechanically un-swapped by the pipeline but each with
  a residue the fuzzy-match correction couldn't resolve: gender↔blood_type (276 corrected, 13
  residual across `gender_unresolved_category_flag` + `blood_type_unresolved_category_flag`) and
  test_results↔medication (314 corrected, 14 residual). Two columns spontaneously swapping values
  in bulk is a column-mapping/export-schema bug, not a typing error — see R2.
- **Billing amount sentinel values:** `billing_amount_sentinel_flag` = 67 rows in viz_ready where
  billing_amount was the exact placeholder 999999 — treated as missing (null), not a real charge.
  These 67 rows are folded into the 594 total billing_amount nulls below.
- **Negative billing amounts, 190 rows (0.35%), uncorrected by design (BR2).** A negative charge
  may be a legitimate refund/credit, so the pipeline flagged rather than sign-flipped these.
  Financial impact of the inclusion/exclusion choice: see R4 and §3.5.
- **Null rates (never imputed, per explicit "never guess a value into existence" policy):**
  length_of_stay is the highest at 2.93% (1,596/54,470 rows), followed by billing_amount 1.09%
  (594), room_number 1.00% (544), insurance_provider 0.97% (526), test_results 0.86% (467),
  medication 0.73% (399), gender 0.70% (384), discharge_date and blood_type ~0.57% (311 each),
  age 0.51% (277). date_of_admission and admission_type have 0 nulls in viz_ready specifically
  because Stage 8 already dropped every row null in a chart-keying column (391 rows, folded into
  the 1,404-row Stage 8 filter — see §7). Every analysis above that used `.dropna()` implicitly
  excludes these null rows; none were filled with an assumed value.
- **Row-level duplicate removal upstream:** 2,290 exact duplicate rows were removed between raw
  (58,164) and cleaned_data.csv (55,874) at Stage 4, plus a further 34 exact duplicates removed
  at Stage 7 after a column was dropped and re-triggered a dedup pass. This is separate from, and
  in addition to, the 9,227 near-duplicate (non-exact) rows discussed above and in R1 — exact dupes
  are gone; near-dupes remain and are the bigger, unresolved signal.
- **Hospital/doctor/patient-name cardinality is extremely high relative to row count:** 39,599
  unique hospitals, 40,391 unique doctors, and 49,148 unique names across only 54,470 rows — i.e.,
  most hospitals and doctors appear only once or twice in the entire dataset. This is inconsistent
  with a real finite hospital/provider network and is further evidence the source is a synthetic
  generator producing fresh random names per row rather than sampling from a real roster. Any
  "top hospital" or "top doctor" ranking built on this data would be ranking noise, not real
  provider volume.

---

## 5. What we cannot say

- **No causal or even correlational business story exists in this data.** Every tested
  relationship among demographics, clinical fields, operational fields, and billing came back
  null (§3). This dataset cannot answer "which condition costs more," "does admission type affect
  length of stay," "do certain demographics get worse test outcomes," or similar questions —
  not because the analysis was insufficient, but because the generator produced these columns
  independently of each other.
- **We cannot confirm whether the 9,227 near-duplicate rows are true duplicates or genuine repeat
  admissions** without a real unique encounter/transaction ID from the source system — this
  dataset has none (Stage 1 brief, confirmed by 49,148 unique names across 54,470 rows, i.e. some
  names are legitimately repeated). The 97.1% identical-billing signal is strong circumstantial
  evidence (R1) but is not proof; it would take source-system logs to settle definitively.
- **We cannot confirm whether the 190 negative billing_amount rows are refunds or entry errors**
  (§3.5, R4) — that requires a source-system reference (e.g., a credit-memo or transaction-type
  field) that does not exist in this extract.
- **We cannot say why length_of_stay tops out at a hard 30–36 day ceiling** (§3.4) — whether this
  reflects the generator's parameter range or a real institutional discharge policy is not
  answerable from this file alone.
- **We cannot rule out that the tiny amount of non-uniformity observed anywhere (e.g., the raw,
  uncorrected month-of-year χ²=52.26) reflects a real seasonal signal that a longer, fully-complete
  multi-year extract might reveal** — this dataset's edge-year partial coverage (§3.1) makes that
  specific question untestable here.

---

## 6. Data Quality Caveats — which pipeline decisions could bend which conclusions

| Decision | Rows affected | What it could bend |
|---|---|---|
| **near_duplicate_composite_key_flag** kept, not removed (no true unique ID exists, brief A2) | 9,227 (16.94%) | Any count-based metric (admissions volume, per-condition counts, per-hospital/doctor counts) is inflated to the extent these are true duplicates — see R1. Aggregate means/medians (age, billing, LOS) are far less affected since duplicated rows just replicate the same value rather than skewing the distribution shape. |
| **billing_amount_sign_flag** — 190 negative rows kept uncorrected (BR2: could be legitimate refund/credit) | 190 (0.35%) | Any billing_amount total or mean depends on an inclusion/exclusion choice that changes the total by $2.15M (0.157%) and the mean by ~$130 — see R4. All ANOVA/correlation results in this report used the sign-excluded subset; the effect sizes were negligible regardless of that choice, so the null findings are robust to it, but the reported dollar figures are choice-dependent. |
| **age_domain_outlier_flag** — 287 rows kept with age>110 (up to 150) | 287 (0.53%) | Age summary statistics (§3.2) are computed on the outlier-excluded subset; including them pulls mean age from 51.20 to 51.73 and max from 89 to 150. Any age-based finding computed without excluding these would be measuring an implausible tail, not the real population. |
| ***_missing_flag** columns — nulls left null everywhere, never imputed | 0.51%–2.93% per column (highest: length_of_stay at 2.93%, 1,596 rows) | Every statistic in this report that used a null-bearing column implicitly dropped those rows (pandas `.dropna()` / `describe()` default behavior) rather than treating null as zero or filling a guess. This slightly shrinks effective sample sizes reported alongside each test but does not bias direction — no imputation-driven bias is possible here since none occurred. |
| **length_of_stay_qa_mismatch_flag** — 205 rows where authoritative LOS disagrees with discharge-admission date arithmetic | 205 (0.38%) | Any LOS-based metric could differ by a mean of ~3.69 days on just these 205 rows depending on which of the two candidate LOS values is used; this report used the authoritative `length_of_stay` column throughout, consistent with pipeline documentation that the QA-recomputed column is reference-only. |
| ***_unresolved_category_flag** — small residual leaked-category values (gender/blood_type/test_results/medication) | 8+5+5+9 = 27 total (<0.05%) | All categorical breakdowns and chi-square/Cramér's-V tests in §3.2–3.3 explicitly excluded these rows to avoid contaminating a canonical-category test with garbage values (the initial uncorrected run inflated gender's χ² to 162,194 purely from these residuals — corrected before reporting, see analysis script). |
| **Stage 8 pre-filter** — 1,404 rows (2.51% of cleaned_data.csv) already removed before this file existed: 1,013 `discharge_before_admission_flag` rows (physically impossible) + 391 rows null in a chart-keying column (date_of_admission or admission_type) | 1,404 (2.51% of cleaned_data.csv, not of viz_ready) | This report analyzes viz_ready.csv as instructed, so these rows are simply absent from every statistic above — not a caveat on this report's numbers, but a caveat on comparing this report's counts directly against cleaned_data.csv (55,874 rows) or the raw file (58,164 rows). |

---

## 7. Notes on report methodology

- Three categorical goodness-of-fit tests (gender, blood_type, and by extension any breakdown
  touching those columns) were initially contaminated by the residual `*_unresolved_category_flag`
  rows — e.g., the raw gender value_counts included "A-", "O-", "B+", "AB+", "AB-", "O+" at counts
  of 1–2 each (leaked blood-type values), which inflated a naive chi-square test to χ²=162,194
  (an artifact of comparing count-of-1 categories against an expected value near 6,760, not a real
  gender skew). All results reported in §3 were recomputed after excluding these
  `*_unresolved_category_flag` rows from the relevant categorical column — this is the corrected,
  reported number throughout.
- All ANOVA and correlation tests involving billing_amount used the `billing_amount_sign_flag`-
  excluded subset (i.e., dropped the 190 negative rows) since a negative charge is not a directly
  comparable magnitude to a positive one; §3.5 and §6 report the dollar-level sensitivity of this
  choice separately.

---

*Report generated 2026-07-29 from `viz_ready.csv` (54,470 rows × 67 columns) plus
`validation_report.md`, `04_stage7_report.txt`, `06_stage8_report.txt`, and `03_stage4_report.txt`
in the same directory. All statistics computed via pandas 3.0.2 / scipy 1.18.0 from the actual
file — none estimated.*
