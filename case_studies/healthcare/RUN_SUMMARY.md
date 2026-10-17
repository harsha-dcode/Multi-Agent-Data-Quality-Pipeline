# RUN SUMMARY — Healthcare Admissions 9-Stage Pipeline

**Run date:** 2026-07-29 (unattended run, no user available — all decisions made and justified inline per `01_business_brief.yaml`)
**Re-run:** 2026-10-17 under the 2026-09-22 spec amendment — see §13. The cleaned outputs are unchanged; what changed is what the run can prove about itself.
**Input:** `<input>/healthcare_dataset_dirty_export.csv` (read-only, not modified)
**Output directory:** `case_studies/healthcare\`

All numbers below are pulled directly from the scripts' own output files (`03_stage4_report.txt`, `04_stage7_report.txt`, `06_stage8_report.txt`, `validation_report.md`, `change_log.csv`), not estimated or recalled.

---

## 1. Row counts

| Stage | Rows | Columns |
|---|---|---|
| Raw input | 58,164 | 19 |
| After Stage 4 (cleaning) exact-dup removal | 55,908 | 50 |
| After Stage 7 (transform) post-transform re-dedup | **55,874** | **67** |
| `cleaned_data.csv` (final, audit-trail, keeps flagged rows) | **55,874** | **67** |
| `viz_ready.csv` (Stage 8, filtered for charting) | **54,470** | **67** |

**Row loss accounting (must sum exactly, and does — V11 PASS):**
- Exact duplicates removed in Stage 4 (4.11): 2,256
- Additional exact duplicates removed in Stage 7, triggered by dropping the distrusted pre-existing `admission_year`/`admission_month`/`admission_yearmonth` columns (BR6) — see §5: 34
- **Total removed between raw and cleaned_data.csv: 2,290** (58,164 → 55,874). `change_log.csv` contains exactly 2,290 `DUPLICATE_REMOVED` entries; `set(raw.__source_row) − set(cleaned.__source_row)` equals that logged set exactly (V11 PASS, diff count 0).
- Stage 8 additionally filtered 1,404 rows for `viz_ready.csv` only (`cleaned_data.csv` is untouched) — see §6.

## 2. Defects found and fixed, by category (all counts from `change_log.csv`, 153,626 total rows)

| CHANGE_TYPE | Count | What it means |
|---|---|---|
| DATE_PARSED | 116,076 | Every non-null date cell in `date_of_admission`/`discharge_date` was individually logged (parsed or explicitly marked unparseable) |
| NEAR_DUPLICATE_FLAGGED | 9,283 | Composite-key (name+date+doctor+hospital) collisions — flagged only, never auto-removed (no true unique ID exists) |
| NULL_FLAGGED_NOT_IMPUTED | 8,030 | Final Stage 7 null check — left null per brief, never guessed |
| STRING_NORMALIZED | 7,774 | Whitespace/NFC/case-fold normalization |
| OUTLIER_FLAGGED | 2,516 | Statistical/domain outliers, QA mismatches, impossible-date flags — flagged, not corrected |
| DUPLICATE_REMOVED | 2,290 | Exact full-row duplicates removed (2,256 Stage 4 + 34 Stage 7) |
| NULL_STANDARDIZED | 2,127 | Null-disguise tokens converted to true null (see §4 for the gate reasoning) |
| TYPO_CORRECTED | 1,654 | Fuzzy/alnum-tier corrections to categorical columns |
| COLUMN_VALUE_SWAP_CORRECTED | 1,320 | 660 rows (309 blood_type↔gender + 351 test_results↔medication) × 2 log entries each |
| NEGATIVE_CORRECTED | 1,168 | age (218) + length_of_stay (950) sign-flips corrected via abs() |
| NUMERIC_CLEANED | 1,109 | Currency symbols, thousands separators, unit suffixes, prefix/quote artifacts stripped |
| NEGATIVE_FLAGGED | 206 | billing_amount negatives — flagged, deliberately NOT corrected (BR2) |
| UNKNOWN_CATEGORY_FLAGGED | 30 | Categorical values that could not be confidently matched to any canonical value |
| HEADER_RENAME | 19 | All 19 raw headers → snake_case |
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
| billing_amount | 546 | `pending` (164), `see invoice` (191), `tbd` (191) — domain-specific placeholders, confirmed by profiling, not assumed |
| room_number | 306 | `unknown`, `?`, `tbd`, `not available`, `--`, `missing`, `-` |
| admission_type | 59 | `unknown`, `?`, `not available`, `--`, `missing`, `-` |
| medication | 195 | `unknown`, `n/a`, `?`, `not available`, `--`, `missing` |
| test_results | 249 | `unknown`, `?`, `not available`, `--`, `missing` |
| **Plus:** billing_amount sentinel `999999` | 76 | Exact-value numeric placeholder, not a string disguise — nulled separately in 4.6 |

No token was found to pass the GATE as a legitimate category member anywhere in this dataset — `NULL_DISGUISE_RETAINED` count is **0**. This was verified, not assumed: the gate ran against each column's real canonical set and every candidate token failed membership.

## 3. Fuzzy-matching collision guard (mandatory, run BEFORE any fuzzy matching — `stage3c_collision_guard.py`)

Ran `rapidfuzz.utils.default_process` alnum-strip test against the canonical list of **every** categorical column:

| Column | Collision? | Verdict |
|---|---|---|
| gender | No | Fuzzy matching permitted |
| **blood_type** | **YES** — `token_sort_ratio('A+','A-', processor=default_process) = 100.0` for all 4 +/- pairs (A, B, AB, O) | **Fuzzy matching DISABLED — exact case-insensitive match only** |
| medical_condition | No | Fuzzy matching permitted |
| admission_type | No | Fuzzy matching permitted |
| insurance_provider | No (initially suspected dangerous for the "United Healthcare" space-variant, but the actual guard found no canonical-vs-canonical collision — corrected in the brief after measuring; handled via a dedicated alnum-exact tier instead of being disabled) | Fuzzy matching permitted (tiered) |
| test_results | No | Fuzzy matching permitted |
| medication | No | Fuzzy matching permitted |

**Post-fuzzy verification (mandatory, `03_fuzzy_verification_report.txt`):** printed `value_counts()` for all 7 categorical columns after correction and checked `missing_canon` (canonical values that disappeared). **Result: `missing_canon = []` for all 7 columns — zero canonical values were lost to a bad fuzzy snap.**

Typo-correction results per column (case-normalized / typo-corrected / left-flagged-unresolved):
gender 400/0/9 · blood_type 1/0/7 (exact-only, dangerous) · medical_condition 1,214/1,028/0 · admission_type 545/0/0 · insurance_provider 162/515/0 · test_results 4/0/5 · medication 657/111/9.

## 4. Column-value swap defects (BR5) — discovered, not assumed, via symmetric evidence

| Swap | Symmetric-evidence rows corrected | Residual (one side only, not corrected) |
|---|---|---|
| blood_type ↔ gender | 309 | 7 (flagged `*_unresolved_category_flag`, left as-is — asymmetric, can't safely un-swap) |
| test_results ↔ medication | 351 | 5 (test_results side) + 9 (medication side) |

Both directions were required to fire a correction — this is a mechanical un-swap of literally-exchanged values, not a guess.

## 5. Distrusted pre-existing derived columns (BR6)

The raw file's `Admission Year`/`Admission Month`/`Admission YearMonth` columns were compared against `year(date_of_admission)` on the cleaned dates: **54,865 rows comparable, 206 disagree (0.38%)**. All 3 columns were dropped and recomputed fresh from the cleaned `date_of_admission` in Stage 7. This column drop removed the *only* distinguishing values between 34 row-pairs that were already near-identical in the raw file — those became exact duplicates only after the drop, and were caught and removed by a dedicated post-transform re-dedup pass (§1). This is the same "normalizing noise reveals real duplicates" phenomenon documented for the Stage 4 dedup, recurring one stage later.

## 6. Negative-value decisions (per-column, no blanket `abs()`)

| Column | Negatives found | Decision | Business rule | Reasoning |
|---|---|---|---|---|
| age | 218 (pre-final-dedup) / 214 (final) | **Corrected** via `abs()` | BR1 | Age cannot be legitimately negative under any interpretation — unambiguous sign-flip |
| length_of_stay | 950 (pre-final-dedup) / 917 (final) | **Corrected** via `abs()` | BR3 | Duration cannot be legitimately negative; no "credit" interpretation exists |
| billing_amount | 206 (pre-final-dedup) / 196 (final) | **Flagged only, NOT corrected** | BR2 | A negative charge may be a legitimate refund/credit/adjustment — sign-flipping would erase real information |
| room_number | 0 | N/A (defensive check only) | — | None found; policy is flag-only if any appeared |

## 7. Outlier / decimal-typo investigation (Stage 4.10, screened at 10× median per column)

**Zero decimal-typo corrections were applied to any of the 4 numeric columns** (billing_amount, age, room_number, length_of_stay) — zero candidates exceeded the 10× median screening threshold in this dataset. Median/min/max were verified identical before and after for all 4 columns (proof no silent distribution reshaping occurred). This is a genuine finding (no decimal-typo defects were injected into this synthetic dataset's numeric columns), not a missed check — the screening ran and found nothing to correct.

Age domain outlier (>110, a ceiling the generic 10×-median rule can't catch since median≈52): **304 rows** flagged, kept (not corrected — Stage 8 also keeps these as a statistical oddity, not a physical impossibility).

## 8. Date parsing

| | date_of_admission | discharge_date |
|---|---|---|
| ISO (YYYY-MM-DD) | 57,085 | 57,116 |
| Named month | 307 | 304 |
| Slash, unambiguous (only one of MM/DD or DD/MM calendar-valid) | 262 | 264 |
| **Ambiguous slash/dash, resolved via documented US-locale business-context assumption** (brief A3 — all 5 insurers are US insurers) | 188 | 151 |
| Unparseable (genuine garbage, e.g. `0000-00-00`, `31/31/2021`) | 199 | 200 |

`discharge_date < date_of_admission` (physically impossible): **1,049 rows flagged** pre-final-dedup / **1,013** in the final `cleaned_data.csv` — never auto-swapped, only flagged.

## 9. Validation (Stage 5) — 13/13 checks run

| Check | Status |
|---|---|
| V1 No null disguises remain | PASS (0 found) |
| V2 Critical columns null-free | **FAIL** — date_of_admission (312 null), billing_amount (661 null), admission_type (80 null). Correct outcome, not a defect: these are genuinely unparseable dates / genuinely missing values / correctly-nulled domain placeholders — guessing them would violate the "never guess a value into existence" rule. |
| V3 No infinities | PASS |
| V4 Correct dtypes (castability test) | PASS |
| V5 No impossible negatives remain uncorrected/unflagged | PASS |
| V6 Outlier handling did not reshape distribution | PASS (0 corrections applied, median unchanged by construction) |
| V7 Email validity rate | N/A — no email column in this dataset |
| V8 Phone E.164 compliance | N/A — no phone column in this dataset |
| V9 No duplicate rows (recomputed on actual output) | PASS (0 found) |
| V10 Header compliance | PASS |
| V11 Row count integrity | PASS (raw−cleaned set exactly equals logged-removed set, diff 0) |
| V12 Schema completeness | PASS |
| V13 Flag registry materialized | PASS (46/46 flags present as boolean columns, True-counts verified) |

**Overall status: REQUIRES REVIEW** (one legitimate, well-explained, non-fabricated critical-column-null failure; no other issues).

## 10. Stage 8 — viz_ready.csv filter/keep

- **FILTER (physically impossible only):** `discharge_before_admission_flag` = True → 1,013 rows; null in a chart-keying column (`date_of_admission` or `admission_type`) → 391 rows. Union: **1,404 rows**.
- **KEEP (statistical oddities, not physically impossible):** age>110 (304 rows), all `*_unresolved_category_flag` (29 rows total across gender/blood_type/test_results/medication), `length_of_stay_qa_mismatch_flag` (1,121 rows), `near_duplicate_composite_key_flag` (9,249 rows), `billing_amount_sign_flag` (196 rows), ambiguous-date flags (330 rows total) — none of these were dropped.
- **Result: 55,874 → 54,470 (1,404 dropped, 2.51%).**

## 11. Stage 9 — Analytics

Delegated to `@analytics-expert` (ran successfully in the foreground; confirmed on disk, not a fallback). Scope: **General EDA (auto-selected, unattended run)**. Ran 17 statistical tests (chi-square goodness-of-fit/independence, Cramér's V, one-way ANOVA/η², Welch's t-test/Cohen's d, Pearson/Spearman) against `viz_ready.csv`. **Result: no statistically/practically significant domain relationship survived testing** (consistent with a synthetic, independently-generated dataset — reported plainly as such, not spun into a false business insight). One apparent seasonal pattern (raw month-of-year χ²=52.26, p<0.00001) evaporated under a complete-years-only re-test (χ²=13.05, p=0.290), demonstrating the "normalize before you're impressed" check. The actionable findings that did emerge came from the *cleaning log itself*, not the clean data: the 16.94% composite-key collision rate with near-identical billing/room values across "duplicate" groups points at an upstream ingest bug; the two column-swap defects point at an export schema-mapping bug; the 196 uncorrected negative-billing rows shift total billing by ~0.157% depending on inclusion and need one documented rule. Full report: `insights_report.md` (27,929 bytes).

## 12. Deliverables (verified present on disk in this output directory)

| File | Purpose |
|---|---|
| `01_business_brief.yaml` | Stage 1 — 6 required keys + optional extras, per-column `missing_value_strategy`, measured `dangerous_columns` |
| `cleaned_data.csv` | Full audit-trail dataset (55,874 rows × 67 cols), flagged rows kept |
| `viz_ready.csv` | Stage 8 filtered view (54,470 rows × 67 cols) |
| `change_log.csv` (+ `change_log.csv` alias, identical content, written because the run instructions named this exact filename) | 153,626 row-level change entries |
| `validation_report.md` | V1–V13 |
| `insights_report.md` | Stage 9 (analytics-expert) |
| `RUN_SUMMARY.md` | This file |
| `stage2a_peek.py` … `stage8_viz_prep.py` (+ `stage3b_targeted_probe.py`, `stage3c_collision_guard.py`, `stage5b_investigate_dups.py`) | Numbered, reproducible scripts — the run can be reproduced from this folder alone by running them in order |
| `03_intermediate_cleaned.csv`, `03_flag_registry.json`, `0*_*.txt` reports | Supporting intermediate artifacts / evidence for every number in this summary |

**Known limitation:** `03_intermediate_cleaned.csv` (Stage 4 output, pre-transform) is retained for audit purposes alongside `cleaned_data.csv` (Stage 7 final) — the two differ by 34 rows (the post-transform re-dedup, §5) and by column set (50 vs 67 columns, since Stage 7 adds derived/dtype-cast columns).

---

## 13. Re-run under the 2026-09-22 spec amendment (2026-10-17)

This dataset was re-run after the agent specification was amended. The amendment came
out of a different dataset — a Tamil Nadu drug register — where Stage 1 asserted a text
column was 100% unique, Stage 4.3 then normalised whitespace and case, and four values
collided. Validation returned all-PASS, correctly, because every check verifies Stage 4
against Stage 1 and Stage 1 was the thing that was wrong.

The amendment requires three things this run did not previously do: `grain` carries the
expression that establishes it, the number it returned and the snapshot it was measured
on; Stage 3 re-runs every such expression instead of reading the recorded answer; and a
claim whose number moves between snapshots is reported as `BRIEF_CLAIM_UNVERIFIED`.

**The rule fired on this dataset.**

### 13.1 The grain claim decays

`grain` is the composite `(name, date_of_admission, doctor, hospital)`. Three of its four
components are text columns that Stage 4.3 strips and whitespace-collapses, and 4.11 builds
the key *after* that:

| Snapshot | Rows | Distinct keys | Duplicated |
|---|---:|---:|---:|
| `measured_on: raw` | 58,164 | 52,195 | 5,968 |
| `measured_on: post_4.3` | 58,164 | 51,252 | **6,911** |

4.3 rewrote 1,539 names, 462 doctors and 1,185 hospitals — trailing spaces, doubled internal
spaces, one embedded tab. Both numbers are now recorded in `01_business_brief.yaml`, and
`stage3_profile.py` recomputes both on every run and reads neither.

### 13.2 What the decay actually cost

The near-duplicate **flag** count moving is harmless: flagging more genuine duplicates is the
right direction, and nothing is removed on that key. The part that matters is that 4.11 removes
**exact full-row duplicates first**, and that removal reads the same post-4.3 values. The 2,256
removals decompose — disjointly, verified — as:

| Share | Rows | Attribution |
|---|---:|---|
| Justified by the raw file | 1,580 | already byte-identical on disk |
| Created by Stage 4.3 alone | **527** | became identical once whitespace was collapsed |
| Created by the other cleaning stages | 149 | null-disguise unification, typo correction, numeric/date reformatting |

So 676 rows were deleted for reasons not visible in the source file. Those deletions are
defensible — the rows differ only by stray whitespace — but before this re-run nothing
attributed a single one of them to a stage, and the brief's own wording ("the composite key is
never used for automatic row removal", which is true) described a different mechanism entirely.
`stage4_clean.py` now prints the split and logs the 676 under their own change type,
`DUPLICATE_REMOVED_POST_NORMALIZATION`. Flagged, not silently fixed.

### 13.3 Two defects the re-run exposed in the pipeline itself

**Stage 5 was validating a half-finished run.** `stage5_validate.py` reads `cleaned_data.csv`,
which **Stage 7** writes, and the change log that Stage 7 appends to. Run in numeric order it
compared the previous run's output against a log missing Stage 7's entries. The published
`validation_report.md` therefore showed V11 as a 34-row integrity FAIL that was nothing but run
order, and V13 checked 30 flags when the pipeline produces 46 — it was blind to every flag
Stage 7 adds. Both now pass on the real artifact. The run order for this case study is
**4 → 7 → 8 → 5 → 9**, not numeric order, and Stage 5 now refuses to run and says so if the
change log has no Stage 6/7 entries.

Worth noting plainly: §1 and §9 of this document already described V11 as PASS and V13 as
46/46. The write-up was right and the generated evidence was wrong — the opposite of the usual
failure, and the reason a reviewer should always be able to re-run the artifact rather than
read the summary.

**Stage 7 logged everything twice.** The change log once had two filenames; collapsing them to
one left two `to_csv(..., mode="a")` calls pointed at the same file. Every Stage 7 entry was
written twice, so the committed `change_log.csv` carried 16,176 Stage 6/7 rows of which 8,088
were exact duplicates — about 5% of the file. Stage 7 now appends once and clears its own prior
slice first, so re-running it is idempotent (verified: a second consecutive run leaves the
totals unchanged).

### 13.4 What did not change

The cleaned data is identical: 58,164 → 55,908 → 55,874 rows, 54,470 viz-ready, 67 columns.
Stage 9 reproduces 28/28 published figures. Validation is 10 PASS, 2 N/A, 1 FAIL — the same
single by-design failure (V2, critical-column nulls the pipeline refuses to invent). The
change log totals 154,302 entries: 153,626 as published, plus the 676 attribution entries
this amendment added.

The point of the amendment is not that this run was wrong. It is that a correct run could not
previously show its own premise still held by the time anything depended on it.
