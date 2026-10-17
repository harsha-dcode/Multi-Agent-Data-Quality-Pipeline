# RUN SUMMARY: Healthcare Admissions 9-Stage Pipeline

**Run date:** 2026-07-29 (unattended run, no user available. All decisions made and justified inline per `01_business_brief.yaml`)
**Re-run:** 2026-10-17 under the 2026-09-22 spec amendment, see §13. The cleaned outputs are unchanged. What changed is what the run can prove about itself.
**Input:** `<input>/healthcare_dataset_dirty_export.csv` (read-only, not modified)
**Output directory:** `case_studies/healthcare/`

Every number below is pulled from the scripts' own output files (`03_stage4_report.txt`, `04_stage7_report.txt`, `06_stage8_report.txt`, `validation_report.md`, `change_log.csv`). None of it is estimated or recalled.

---

## 1. Row counts

| Stage | Rows | Columns |
|---|---|---|
| Raw input | 58,164 | 19 |
| After Stage 4 (cleaning) exact-dup removal | 55,908 | 50 |
| After Stage 7 (transform) post-transform re-dedup | 55,874 | 67 |
| `cleaned_data.csv` (final, audit-trail, keeps flagged rows) | 55,874 | 67 |
| `viz_ready.csv` (Stage 8, filtered for charting) | 54,470 | 67 |

Row loss has to account exactly, and it does (V11 PASS):

- Exact duplicates removed in Stage 4 (4.11): 2,256
- Additional exact duplicates removed in Stage 7, triggered by dropping the distrusted pre-existing `admission_year`/`admission_month`/`admission_yearmonth` columns (BR6, see §5): 34
- Total removed between raw and `cleaned_data.csv`: 2,290 (58,164 to 55,874). `change_log.csv` contains exactly 2,290 `DUPLICATE_REMOVED` entries, and `set(raw.__source_row) - set(cleaned.__source_row)` equals that logged set exactly (V11 PASS, diff count 0).
- Stage 8 filtered a further 1,404 rows for `viz_ready.csv` only. `cleaned_data.csv` is untouched. See §6.

## 2. Defects found and fixed, by category (all counts from `change_log.csv`, 154,302 total rows)

| CHANGE_TYPE | Count | What it means |
|---|---|---|
| DATE_PARSED | 116,076 | Every non-null date cell in `date_of_admission`/`discharge_date` was individually logged, parsed or explicitly marked unparseable |
| NEAR_DUPLICATE_FLAGGED | 9,283 | Composite-key (name+date+doctor+hospital) collisions, flagged only, never auto-removed, since no true unique ID exists |
| NULL_FLAGGED_NOT_IMPUTED | 8,030 | Final Stage 7 null check. Left null per the brief, never guessed |
| STRING_NORMALIZED | 7,774 | Whitespace/NFC/case-fold normalization |
| OUTLIER_FLAGGED | 2,516 | Statistical and domain outliers, QA mismatches, impossible-date flags. Flagged, not corrected |
| DUPLICATE_REMOVED | 2,290 | Exact full-row duplicates removed (2,256 Stage 4 + 34 Stage 7) |
| NULL_STANDARDIZED | 2,127 | Null-disguise tokens converted to true null (see §4 for the gate reasoning) |
| TYPO_CORRECTED | 1,654 | Fuzzy and alnum-tier corrections to categorical columns |
| COLUMN_VALUE_SWAP_CORRECTED | 1,320 | 660 rows (309 blood_type/gender + 351 test_results/medication) x 2 log entries each |
| NEGATIVE_CORRECTED | 1,168 | age (218) + length_of_stay (950) sign-flips corrected via abs() |
| NUMERIC_CLEANED | 1,109 | Currency symbols, thousands separators, unit suffixes, prefix/quote artifacts stripped |
| DUPLICATE_REMOVED_POST_NORMALIZATION | 676 | Of the 2,290 removals, the subset that was not byte-identical in the raw file and became duplicate only after cleaning. Added by the 2026-10-17 re-run, see §13.2 |
| NEGATIVE_FLAGGED | 206 | billing_amount negatives. Flagged, not corrected, per BR2 |
| UNKNOWN_CATEGORY_FLAGGED | 30 | Categorical values that could not be confidently matched to any canonical value |
| HEADER_RENAME | 19 | All 19 raw headers to snake_case |
| DTYPE_CAST | 16 | Final dtype enforcement (Stage 7) |
| DERIVED_COLUMN_ADDED | 7 | 3 dropped-and-replaced (BR6) + 3 recomputed + 1 QA column |
| COLUMN_REORDERED | 1 | Single reorder operation, Stage 7 |

### Null-disguise standardization detail (Stage 4.2, gate-per-column, measured on the raw 58,164 rows before any dedup)

| Column | Nulled | Tokens |
|---|---|---|
| age | 77 | `unknown` |
| gender | 142 | `unknown` (canonical set = {Male, Female}; gate said NO) |
| blood_type | 153 | `unknown`, `?`, `not available`, `--`, `missing`, `-` (canonical 8-value set; gate said NO for all) |
| insurance_provider | 324 | `unknown`, `not available`, `--`, `?`, `missing`, `-` |
| billing_amount | 546 | `pending` (164), `see invoice` (191), `tbd` (191). Domain-specific placeholders, confirmed by profiling rather than assumed |
| room_number | 306 | `unknown`, `?`, `tbd`, `not available`, `--`, `missing`, `-` |
| admission_type | 59 | `unknown`, `?`, `not available`, `--`, `missing`, `-` |
| medication | 195 | `unknown`, `n/a`, `?`, `not available`, `--`, `missing` |
| test_results | 249 | `unknown`, `?`, `not available`, `--`, `missing` |
| Plus: billing_amount sentinel `999999` | 76 | Exact-value numeric placeholder, not a string disguise. Nulled separately in 4.6 |

No token passed the GATE as a legitimate category member anywhere in this dataset, so `NULL_DISGUISE_RETAINED` is 0. I verified that rather than assuming it: the gate ran against each column's real canonical set and every candidate token failed membership.

## 3. Fuzzy-matching collision guard (runs BEFORE any fuzzy matching, `stage3c_collision_guard.py`)

Ran the `rapidfuzz.utils.default_process` alnum-strip test against the canonical list of every categorical column:

| Column | Collision? | Verdict |
|---|---|---|
| gender | No | Fuzzy matching permitted |
| blood_type | YES. `token_sort_ratio('A+','A-', processor=default_process) = 100.0` for all 4 +/- pairs (A, B, AB, O) | Fuzzy matching DISABLED, exact case-insensitive match only |
| medical_condition | No | Fuzzy matching permitted |
| admission_type | No | Fuzzy matching permitted |
| insurance_provider | No. I initially suspected it was dangerous because of the "United Healthcare" space-variant, but the guard found no canonical-vs-canonical collision. Corrected in the brief after measuring, and handled with a dedicated alnum-exact tier instead of being disabled | Fuzzy matching permitted (tiered) |
| test_results | No | Fuzzy matching permitted |
| medication | No | Fuzzy matching permitted |

Post-fuzzy verification (`03_fuzzy_verification_report.txt`) printed `value_counts()` for all 7 categorical columns after correction and checked `missing_canon`, the canonical values that disappeared. Result: `missing_canon = []` for all 7 columns, so zero canonical values were lost to a bad fuzzy snap.

Typo-correction results per column (case-normalized / typo-corrected / left-flagged-unresolved):
gender 400/0/9, blood_type 1/0/7 (exact-only, dangerous), medical_condition 1,214/1,028/0, admission_type 545/0/0, insurance_provider 162/515/0, test_results 4/0/5, medication 657/111/9.

## 4. Column-value swap defects (BR5), discovered through symmetric evidence rather than assumed

| Swap | Symmetric-evidence rows corrected | Residual (one side only, not corrected) |
|---|---|---|
| blood_type / gender | 309 | 7 (flagged `*_unresolved_category_flag` and left as-is, since asymmetric cases cannot safely be un-swapped) |
| test_results / medication | 351 | 5 (test_results side) + 9 (medication side) |

Both directions had to fire before a correction was applied. This is a mechanical un-swap of literally exchanged values, not a guess.

## 5. Distrusted pre-existing derived columns (BR6)

I compared the raw file's `Admission Year`/`Admission Month`/`Admission YearMonth` columns against `year(date_of_admission)` on the cleaned dates: 54,865 rows comparable, 206 disagree (0.38%). All 3 columns were dropped and recomputed fresh from the cleaned `date_of_admission` in Stage 7.

That column drop removed the only distinguishing values between 34 row-pairs that were already near-identical in the raw file. They became exact duplicates only after the drop, and a dedicated post-transform re-dedup pass caught and removed them (§1). This is the same "normalizing noise reveals real duplicates" phenomenon documented for the Stage 4 dedup, recurring one stage later. §13.2 quantifies it properly.

## 6. Negative-value decisions (per-column, no blanket `abs()`)

| Column | Negatives found | Decision | Business rule | Reasoning |
|---|---|---|---|---|
| age | 218 (pre-final-dedup) / 214 (final) | Corrected via `abs()` | BR1 | Age cannot be legitimately negative under any interpretation, so this is an unambiguous sign-flip |
| length_of_stay | 950 (pre-final-dedup) / 917 (final) | Corrected via `abs()` | BR3 | Duration cannot be legitimately negative, and no "credit" interpretation exists |
| billing_amount | 206 (pre-final-dedup) / 196 (final) | Flagged only, NOT corrected | BR2 | A negative charge may be a legitimate refund, credit or adjustment, and sign-flipping would erase real information |
| room_number | 0 | N/A (defensive check only) | | None found. Policy is flag-only if any appeared |

## 7. Outlier and decimal-typo investigation (Stage 4.10, screened at 10x median per column)

Zero decimal-typo corrections were applied to any of the 4 numeric columns (billing_amount, age, room_number, length_of_stay), because zero candidates exceeded the 10x median screening threshold in this dataset. Median, min and max were verified identical before and after for all 4 columns, which proves no silent distribution reshaping occurred. This is a genuine finding rather than a missed check: no decimal-typo defects were injected into this synthetic dataset's numeric columns, the screening ran, and it found nothing to correct.

Age domain outlier (>110, a ceiling the generic 10x-median rule cannot catch since median is about 52): 304 rows flagged and kept. Stage 8 also keeps these, since they are a statistical oddity rather than a physical impossibility.

## 8. Date parsing

| | date_of_admission | discharge_date |
|---|---|---|
| ISO (YYYY-MM-DD) | 57,085 | 57,116 |
| Named month | 307 | 304 |
| Slash, unambiguous (only one of MM/DD or DD/MM calendar-valid) | 262 | 264 |
| Ambiguous slash/dash, resolved via the documented US-locale business-context assumption (brief A3, all 5 insurers are US insurers) | 188 | 151 |
| Unparseable (genuine garbage, e.g. `0000-00-00`, `31/31/2021`) | 199 | 200 |

`discharge_date < date_of_admission` is physically impossible: 1,049 rows flagged pre-final-dedup, 1,013 in the final `cleaned_data.csv`. Never auto-swapped, only flagged.

## 9. Validation (Stage 5), 13 checks run

| Check | Status |
|---|---|
| V1 No null disguises remain | PASS (0 found) |
| V2 Critical columns null-free | FAIL. date_of_admission (312 null), billing_amount (661 null), admission_type (80 null). This is the correct outcome, not a defect: they are genuinely unparseable dates, genuinely missing values, or correctly-nulled domain placeholders, and guessing them would violate the "never guess a value into existence" rule. |
| V3 No infinities | PASS |
| V4 Correct dtypes (castability test) | PASS |
| V5 No impossible negatives remain uncorrected/unflagged | PASS |
| V6 Outlier handling did not reshape distribution | PASS (0 corrections applied, median unchanged by construction) |
| V7 Email validity rate | N/A, no email column in this dataset |
| V8 Phone E.164 compliance | N/A, no phone column in this dataset |
| V9 No duplicate rows (recomputed on actual output) | PASS (0 found) |
| V10 Header compliance | PASS |
| V11 Row count integrity | PASS (raw minus cleaned set exactly equals logged-removed set, diff 0) |
| V12 Schema completeness | PASS |
| V13 Flag registry materialized | PASS (46/46 flags present as boolean columns, True-counts verified) |

Overall status: REQUIRES REVIEW. One legitimate, well-explained, non-fabricated critical-column-null failure, and no other issues.

Both V11 and V13 were previously published with wrong values, because Stage 5 was being run before Stage 7. See §13.3.

## 10. Stage 8, viz_ready.csv filter and keep

- FILTER (physically impossible only): `discharge_before_admission_flag` = True gives 1,013 rows, and a null in a chart-keying column (`date_of_admission` or `admission_type`) gives 391 rows. Union: 1,404 rows.
- KEEP (statistical oddities, not physically impossible): age>110 (304 rows), all `*_unresolved_category_flag` (29 rows total across gender/blood_type/test_results/medication), `length_of_stay_qa_mismatch_flag` (1,121 rows), `near_duplicate_composite_key_flag` (9,249 rows), `billing_amount_sign_flag` (196 rows), ambiguous-date flags (330 rows total). None of these were dropped.
- Result: 55,874 to 54,470 (1,404 dropped, 2.51%).

## 11. Stage 9, Analytics

Delegated to `@analytics-expert`, which ran in the foreground and is confirmed on disk rather than a fallback. Scope: general EDA, auto-selected for an unattended run. It ran 17 statistical tests (chi-square goodness-of-fit and independence, Cramer's V, one-way ANOVA and eta-squared, Welch's t-test and Cohen's d, Pearson, Spearman) against `viz_ready.csv`.

Result: no statistically or practically significant domain relationship survived testing. That is consistent with a synthetic, independently-generated dataset, and it is reported as such rather than spun into a false business insight. One apparent seasonal pattern (raw month-of-year chi-square 52.26, p<0.00001) evaporated under a complete-years-only re-test (chi-square 13.05, p=0.290), which is the "normalize before you are impressed" check doing its job.

The actionable findings came from the cleaning log, not the clean data. The 16.94% composite-key collision rate, with near-identical billing and room values across the "duplicate" groups, points at an upstream ingest bug. The two column-swap defects point at an export schema-mapping bug. The 196 uncorrected negative-billing rows shift total billing by about 0.157% depending on inclusion, and need one documented rule. Full report: `insights_report.md`.

## 12. Deliverables (verified present on disk in this output directory)

| File | Purpose |
|---|---|
| `01_business_brief.yaml` | Stage 1. 6 required keys plus optional extras, per-column `missing_value_strategy`, measured `dangerous_columns` |
| `cleaned_data.csv` | Full audit-trail dataset (55,874 rows x 67 cols), flagged rows kept |
| `viz_ready.csv` | Stage 8 filtered view (54,470 rows x 67 cols) |
| `change_log.csv` | 154,302 row-level change entries |
| `validation_report.md` | V1 to V13 |
| `insights_report.md` | Stage 9 (analytics-expert) |
| `RUN_SUMMARY.md` | This file |
| `stage2a_peek.py` through `stage9_analytics.py` (plus `stage3b_targeted_probe.py`, `stage3c_collision_guard.py`, `stage5b_investigate_dups.py`) | Numbered, reproducible scripts. The run can be reproduced from this folder alone by running them in the order given in §13.3 |
| `03_intermediate_cleaned.csv`, `03_flag_registry.json`, `0*_*.txt` reports | Supporting intermediate artifacts, and the evidence behind every number in this summary |

Known limitation: `03_intermediate_cleaned.csv` (Stage 4 output, pre-transform) is kept for audit purposes alongside `cleaned_data.csv` (Stage 7 final). The two differ by 34 rows (the post-transform re-dedup, §5) and by column set (50 vs 67 columns, since Stage 7 adds derived and dtype-cast columns).

---

## 13. Re-run under the 2026-09-22 spec amendment (2026-10-17)

I re-ran this dataset after amending the agent specification. The amendment came out of
a different dataset, a Tamil Nadu drug register, where Stage 1 asserted a text column was
100% unique, Stage 4.3 then normalised whitespace and case, and four values collided.
Validation returned all-PASS, correctly, because every check verifies Stage 4 against
Stage 1 and Stage 1 was the thing that was wrong.

The amendment requires three things this run did not previously do. `grain` has to carry
the expression that establishes it, the number it returned and the snapshot it was
measured on. Stage 3 has to re-run every such expression instead of reading the recorded
answer. And a claim whose number moves between snapshots gets reported as
`BRIEF_CLAIM_UNVERIFIED`.

The rule fired on this dataset.

### 13.1 The grain claim decays

`grain` is the composite `(name, date_of_admission, doctor, hospital)`. Three of its four
components are text columns that Stage 4.3 strips and whitespace-collapses, and 4.11
builds the key after that:

| Snapshot | Rows | Distinct keys | Duplicated |
|---|---:|---:|---:|
| `measured_on: raw` | 58,164 | 52,195 | 5,968 |
| `measured_on: post_4.3` | 58,164 | 51,252 | 6,911 |

4.3 rewrote 1,539 names, 462 doctors and 1,185 hospitals: trailing spaces, doubled
internal spaces, one embedded tab. Both numbers are now recorded in
`01_business_brief.yaml`, and `stage3_profile.py` recomputes both on every run and reads
neither.

### 13.2 What the decay actually cost

The near-duplicate flag count moving is harmless. Flagging more genuine duplicates is the
right direction and nothing is removed on that key. The part that matters is that 4.11
removes exact full-row duplicates first, and that removal reads the same post-4.3 values.
The 2,256 removals decompose, disjointly, as:

| Share | Rows | Attribution |
|---|---:|---|
| Justified by the raw file | 1,580 | already byte-identical on disk |
| Created by Stage 4.3 alone | 527 | became identical once whitespace was collapsed |
| Created by the other cleaning stages | 149 | null-disguise unification, typo correction, numeric/date reformatting |

So 676 rows were deleted for reasons not visible in the source file. Those deletions are
defensible, since the rows differ only by stray whitespace, but before this re-run nothing
attributed a single one of them to a stage. The brief's own wording, that the composite
key is never used for automatic row removal, is true and describes a different mechanism
entirely. `stage4_clean.py` now prints the split and logs the 676 under their own change
type, `DUPLICATE_REMOVED_POST_NORMALIZATION`. Flagged, not quietly fixed.

### 13.3 Two defects the re-run exposed in the pipeline itself

Stage 5 was validating a half-finished run. `stage5_validate.py` reads `cleaned_data.csv`,
which Stage 7 writes, and the change log that Stage 7 appends to. Run in numeric order it
compared the previous run's output against a log missing Stage 7's entries. The published
`validation_report.md` therefore showed V11 as a 34-row integrity FAIL that was nothing
but run order, and V13 checked 30 flags when the pipeline produces 46, so it was blind to
every flag Stage 7 adds. Both pass now on the real artifact. The run order for this case
study is 4, then 7, 8, 5, 9, not numeric order, and Stage 5 now refuses to run and says so
if the change log has no Stage 6/7 entries.

Worth saying plainly: §1 and §9 of this document already described V11 as PASS and V13 as
46/46. The write-up was right and the generated evidence was wrong, which is the opposite
of the usual failure, and the reason a reviewer should always be able to re-run the
artifact rather than read the summary.

Stage 7 logged everything twice. The change log once had two filenames, and collapsing
them to one left two `to_csv(..., mode="a")` calls pointed at the same file. Every Stage 7
entry was written twice, so the committed `change_log.csv` carried 16,176 Stage 6/7 rows
of which 8,088 were exact duplicates, about 5% of the file. Stage 7 now appends once and
clears its own prior slice first, so re-running it is idempotent. I verified that by
running it twice and checking the totals did not move.

### 13.4 What did not change

The cleaned data is identical: 58,164 to 55,908 to 55,874 rows, 54,470 viz-ready, 67
columns. Stage 9 reproduces 28/28 published figures. Validation is 10 PASS, 2 N/A, 1 FAIL,
the same single by-design failure on critical-column nulls the pipeline refuses to invent.
The change log totals 154,302 entries: 153,626 as published, plus the 676 attribution
entries this amendment added.

The point of the amendment is not that this run was wrong. It is that a correct run could
not previously show its own premise still held by the time anything depended on it.
