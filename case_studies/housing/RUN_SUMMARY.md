# RUN SUMMARY — house_50k_sample.csv (real-estate listings)

**Run type:** Unattended (no user available). Every judgment call below was made by the
agent and justified inline in `01_business_brief.yaml`, `change_log.csv`, and this file, per
the `unattended-run-conventions` memory.

**Input:** `<input>/house_50k_sample.csv`
(50,000 rows x 46 cols, ~24.5 MB, read-only, never modified)

**Output directory:** `case_studies/housing\`

**Reproducibility:** run scripts `stage2_extract.py` -> `stage3_profile.py` -> `stage4_clean.py` ->
`stage7_transform.py` -> `stage5_validate.py` -> `stage8_viz_prep.py` in order, then invoke
`@analytics-expert` on `viz_ready.csv` for Stage 9. Every script opens its own output file
with `encoding="utf-8"`; none rely on shell redirection.

---

## Row counts

| Stage | Rows | Cols | Notes |
|---|---|---|---|
| Raw input | 50,000 | 46 | |
| `cleaned_data.csv` (post Stage 4+7) | 49,864 | 60 | 136 exact full-row duplicates removed (4.11); 14 new columns = 8 flag cols + 5 derived cols + 1 (`__source_row`, minus the fact one raw col (`postal_code`) changed representation not count) |
| `viz_ready.csv` (post Stage 8) | 48,870 | 60 | 994 more rows dropped (physically-impossible negative `total_area`) |

**Drop rate, Stage 8:** 49,864 -> 48,870 (994 dropped, **1.99%**). This is the *only* filter
applied — negative `total_area` is physically impossible to chart honestly. Every other
flagged population (statistical outliers, genuine luxury listings) was **kept** in
`viz_ready.csv` — see "Filter-vs-keep decisions" below.

---

## Stage 1: Business Brief

`01_business_brief.yaml` — all 6 required keys present (`dataset`, `grain`,
`critical_columns`, `allowed_values`, `dangerous_columns`, `missing_value_strategy`),
`missing_value_strategy` populated per-column for all 46 raw columns (no blanket rule).
9 business rules (BR1–BR9) and 2 assumptions (A1–A2) documented with measured evidence.

---

## Defects found and how each was handled

| # | Defect | Rows affected | Action |
|---|---|---|---|
| 1 | Exact full-row duplicates | 136 (0.27%) | Removed (Stage 4.11); `property_id` duplicate count matched exactly, confirming no partial/near-dup reconciliation was needed |
| 2 | `condition` case-duplicate (`new`/`New`) | 7,239 + 7,231 = 14,470 merged | Title-case normalization (4.3) — **not** fuzzy matching; not an edit-distance typo |
| 3 | `city` ASCII-transliteration pairs (`Sao Paulo`/`São Paulo`, `Munich`/`München`) | 1,632 + 1,009 = 2,641 | Explicit alias map (BR2), fuzzy matching **declined** — collision guard measured `token_sort_ratio('Munich','München')=61.5` (below the 70 review floor) |
| 4 | `total_area` negative sign-flip | 996 raw / 994 surviving dedup | **Flagged only** (`total_area_sign_flag`), never corrected — area is not on the abs()-safe list (BR3) |
| 5 | `total_area` heavy right tail | 4,860 raw / 4,848 surviving (9.72–9.92%) | **Flagged** `STATISTICAL_OUTLIER` (BR4) — 9.7%+ of a column exceeds the 1% sanity cap for genuine decimal-typo populations; real scale variation, not corrected |
| 6 | `price_per_sqm` apparent outliers | 1,577 / 1,573 surviving | **Flagged**, not corrected (BR6) — mathematically explained by `final_sale_price/total_area`, ratio band [0.90,1.10] |
| 7 | `final_sale_price` apparent decimal typos | 425 / 424 surviving | **Flagged**, not corrected (BR5) — cross-checked against `listing_price`, ratio band matches normal population (418/425 in-band) |
| 8 | `listing_price` apparent decimal typos | 427 / 426 surviving | **Flagged**, not corrected (BR9) — cross-checked against `final_sale_price` (421/427 in-band). **Caught during development**: the naive generic-loop divisor test alone would have wrongly corrected 370 of these (0.74%, under the 1% cap, so the cap alone would not have stopped it) |
| 9 | `land_area` single decimal-typo candidate | 1 | **Corrected** — divided by 10, landed in [0.5x,2x] median band, 0.002% repair rate, far under cap |
| 10 | `listing_price`/`hoa_fee` currency-prefix stripping | 50,000 / 25,155 (rest bare) | Symbol verified == row `currency` (0 mismatches), stripped, cast to float (4.6, BR7) |
| 11 | `listing_date` parsing | 50,000 | 100% parsed as DD-MM-YYYY (A1), 0 unparseable |

**Impossible-value decisions (per column, not blanket):**
- `total_area` negative (994 rows): **impossible, flagged, NOT corrected** — sign-flip vs. wrong-column swap can't be distinguished with certainty (BR3)
- `latitude`/`longitude` negative (24,933 / 24,904 rows): **legitimate geography, NOT flagged, NOT corrected** (BR1) — verified both stay within physical range ([-90,90], [-180,180]), 0 out-of-range values
- `built_year` future (>2026): **0 found**; rule stands as a standing flag (`built_year_future_flag`) for future refreshes
- All other quantity columns checked for negatives (`bedrooms`, `bathrooms`, `floors`,
  `parking_spots`, `land_area`, `final_sale_price`, `listing_price`, `price_per_sqm`,
  `hoa_fee`, `property_tax`, `days_on_market`, `price_revision_count`, `interest_rate`,
  `inflation_index`, `housing_index`, `luxury_demand_index`, `postal_code`): **0 negatives
  found in every one, verified not assumed**

---

## Collision-guard results (Stage 4.4), per categorical column

| Column | Guard result | Action |
|---|---|---|
| `country` | Clear (0 collisions) | No fuzzy matching — column already conforms exactly to its 10-value canonical set |
| `property_type` | Clear (0 collisions) | No fuzzy matching — conforms exactly to its 7-value canonical set |
| `condition` | Clear (0 collisions) | Case-duplicate merged via Title Case (not fuzzy matching); other 5 values lexically distinct |
| `currency` | **TRIPS** | Fuzzy matching refused outright — rapidfuzz's default preprocessor strips all 4 non-alphanumeric symbols (₹£$€) to the same empty key. Moot since currency already conforms exactly (5/5 canonical, 0 variants), but the guard was run and would have blocked fuzzy matching regardless |
| `city` | Not run (declined by design) | `token_sort_ratio('Munich','München')=61.5` (below even the 70 review floor) and `token_sort_ratio('Sao Paulo','São Paulo')=88.9` (above the 85 auto-correct floor) — an inconsistent, hard-to-audit basis for one fuzzy pass. Both are ASCII-transliteration pairs, not typos; handled by one explicit alias map instead (BR2) |

**Post-fuzzy/alias verification (missing-canonical check):** 31/31 canonical cities present
after the alias map; 0 unexpected values remaining. All other categorical columns verified
their canonical value sets are fully intact post-clean (printed `value_counts()` for
`condition`, `city`, `currency` — see `02_clean_report.txt`).

---

## Validation (Stage 5) — 13/13 checks run, 11 PASS, 2 N/A, 0 FAIL

See `validation_report.md` for the full table. Summary:
- V1–V6, V9–V13: **PASS**
- V7 (email validity), V8 (phone E.164): **N/A** — this dataset has no email or phone columns
- **Overall status: READY FOR REPORTING**

Notable: V4 (dtype correctness) required distinguishing "CSV cannot preserve
pandas category/datetime64 metadata across a write/read round trip" (a property of the file
format) from an actual dtype defect — validated via semantic checks (value-set conformance
for categories, `parse_dates` for the date column, losslessness check for `postal_code`)
rather than a literal dtype-string comparison. See `stage5_validate.py` comments and
`03_transform_report.txt` for the in-memory dtype enforcement that was actually applied
before writing.

---

## Changelog

`change_log.csv`: **11,068 row-level entries**, columns `STAGE, COLUMN, SOURCE_ROW,
CHANGE_TYPE, ORIGINAL_VALUE, NEW_VALUE, REASON`. Every `SOURCE_ROW` is the `__source_row`
value from the raw file (0-based), preserved through dedup and the Stage 7 index reset.

| CHANGE_TYPE | Count |
|---|---|
| OUTLIER_FLAGGED | 7,289 |
| TYPO_CORRECTED | 2,641 |
| NEGATIVE_FLAGGED | 996 |
| DUPLICATE_REMOVED | 136 |
| NUMERIC_CLEANED | 3 |
| STRING_NORMALIZED | 1 |
| DATE_PARSED | 1 |
| OUTLIER_DECIMAL_TYPO_CORRECTED | 1 |

**Cells with an actual value change (not just a flag):** 2,642 total = 2,641 city alias
corrections + 1 land_area decimal-typo correction. Every other logged event (7,289 + 996 =
8,285 rows) is a **flag**, not a correction — the underlying value was left exactly as
received, per the "never guess a value into existence" rule.

---

## Flag registry (materialized as boolean columns on `cleaned_data.csv`)

| Flag column | True count | Meaning |
|---|---|---|
| `total_area_sign_flag` | 994 | Negative total_area (impossible), not corrected |
| `built_year_future_flag` | 0 | built_year > 2026 (impossible), none found |
| `total_area_outlier_flag` | 4,848 | >10x median, real scale variation (BR4) |
| `price_per_sqm_outlier_flag` | 1,573 | >10x median, explained by total_area (BR6) |
| `final_sale_price_outlier_flag` | 424 | >10x median, genuine luxury (BR5) |
| `listing_price_outlier_flag` | 426 | >10x median, genuine luxury (BR9) |
| `land_area_outlier_flag` | 0 | >10x median candidates with no divisor fit; none found |
| `land_area_decimal_typo_flag` | 1 | Corrected (divided by 10) |

All 8 flags' True counts were cross-checked against `change_log.csv` entry counts for rows
surviving to the final dataset (accounting for the 2 negative-`total_area` rows that were
also among the 136 removed duplicates) — all match exactly (V13 PASS).

---

## Stage 8: Filter-vs-keep

**Filtered (994 rows, 1.99%):** `total_area_sign_flag` only — negative area is physically
impossible to chart honestly.

**Kept (7,289 flagged rows retained):** every `*_outlier_flag` population — all are
statistical oddities with a verified, non-error explanation (real scale variation, or
cross-checked against an independent price column), not data-entry errors. Dropping them
would have manufactured a falsely narrow price/area distribution.

---

## Stage 9: Analytics

**Scope: General EDA — auto-selected (unattended run).** Delegated to `@analytics-expert`
(live invocation, foreground, file-on-disk verified), briefed with full domain context and
the flag registry above. Report: `insights_report.md` (22,715 bytes, 140 lines, verified
present on disk).

**Top findings:**
1. Country is the dominant price driver (partial η²=0.370, p<0.001); property_type and
   condition are practically null once controlled (partial η² 0.0001–0.0003) despite
   property_type clearing p<0.05 univariately — a large-n false positive.
2. **New finding, not in prior lineage memory for this fixture:** latitude/longitude are not
   tied to real country geography — ~50% of Australia's listings show impossible
   positive/northern-hemisphere latitude, ~51% of India's show impossible
   negative/southern-hemisphere latitude. This is a source-system defect, not something
   fixable at the cleaning layer (BR1 was still correct to preserve sign — the problem isn't
   sign convention, it's that the coordinates aren't real).
3. `currency` carries no real price-scale information (Kruskal-Wallis p=0.53 on price by
   currency) — consistent with the cleaning stage's prior finding that currency is
   independent of country (χ²=44.32, p=0.16). Reinforces BR8.
4. The 424 kept `final_sale_price_outlier_flag` rows inflate country-level **means** by
   10–27% while moving **medians** under 1% — validates the Stage 8 keep decision (the rows
   are real) while flagging a downstream reporting risk (use medians for headline numbers).
5. `luxury_demand_index` re-confirmed as a real signal (r=0.383, p<0.001); `interest_rate`/
   `inflation_index`/`housing_index` re-confirmed as noise (p=0.06–0.88) on this subset,
   independently re-tested rather than assumed from the prior lineage.

---

## Final artifact checklist

| File | Status |
|---|---|
| `01_business_brief.yaml` | Present |
| `cleaned_data.csv` | Present (49,864 rows x 60 cols) |
| `viz_ready.csv` | Present (48,870 rows x 60 cols) |
| `change_log.csv` | Present (11,068 rows) |
| `validation_report.md` | Present (13/13 checks run, READY FOR REPORTING) |
| `insights_report.md` | Present (22,715 bytes, verified on disk by @analytics-expert and by this agent) |
| `RUN_SUMMARY.md` | This file |

**Reproducibility scripts** (numbered, all in this directory): `stage2_extract.py`,
`stage3_profile.py`, `stage4_clean.py`, `stage7_transform.py`, `stage5_validate.py`, `stage8_viz_prep.py`.
Intermediate artifacts kept for auditability: `00_inspect_report.txt`,
`01_profile_report.txt`, `02_clean_report.txt`, `03_transform_report.txt`,
`05_viz_prep_report.txt`, `_flag_registry.json`, `_intermediate_post_stage4.csv` (post-Stage-4,
pre-Stage-7 frame).
