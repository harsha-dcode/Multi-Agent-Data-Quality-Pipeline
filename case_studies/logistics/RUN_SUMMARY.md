# RUN SUMMARY — Logistics Supply Chain Dataset

Unattended 9-stage pipeline run. No user available to ask; every judgment call is documented
inline in `01_business_brief.yaml` (business rules BR1–BR9, assumptions A1–A3) and in the
`REASON` field of every affected `change_log.csv` row.

**Input:** `<input>/logistics_supply_chain_dataset_v3.csv`
**Output directory:** `case_studies/logistics\`
**Run date:** 2026-07-29

---

## 1. Row counts

| Stage | Rows | Notes |
|---|---|---|
| Raw input | 30,102 | 35 columns, UTF-8, no BOM, no structural anomalies |
| cleaned_data.csv | 30,000 | 84 columns (35 source + `__source_row` + 43 flag columns + 5 derived columns) |
| viz_ready.csv | 29,354 | 646 rows dropped (2.1533%) — see §5 |

Rows removed between raw and cleaned: **102** (exact full-row duplicates, Stage 4.11). Verified via
V11: `set(raw.__source_row) - set(clean.__source_row)` exactly equals the 102 `__source_row`
values logged as `DUPLICATE_REMOVED` — confirmed programmatically, not asserted.

## 2. Defects found, per category (counts are on the final 30,000-row cleaned_data.csv unless noted)

| Category | Count | Column(s) | Disposition |
|---|---|---|---|
| Exact duplicate rows | 102 | all 35 source columns | Removed (kept first occurrence) |
| Null disguises (empty string only; no other disguise tokens present in raw data) | 33,247 cells | actual_delivery_date(230), delay_days(230), driver_id(7,228), shipment_weight_kg(900), fuel_cost_inr(1,203), customer_rating(1,718), delay_reason(21,738) — pre-dedup counts | Standardized to null, left null (per-column `missing_value_strategy`, none imputed) |
| Categorical typos/case variants auto-corrected (>=85 similarity or exact case-insensitive) | 2,074 | delivery_status(1,087), customer_type(400), transport_mode(459), product_category(128) | Corrected to canonical form |
| Categorical corrections in review band (70–84 similarity) | 112 | delivery_status ("delay"->"Delayed") | Corrected, `delivery_status_fuzzy_review_flag=True` on 111 surviving post-dedup rows |
| Categorical values left UNKNOWN (<70 similarity) | 266 | transport_mode(235: "Road Transport", "Airways" — see below), product_category(31: "Clothing") | NOT corrected, `*_unknown_category_flag=True` |
| Explicit synonym-map corrections (historical city renames, transport-mode synonyms) | 280 | destination_city(45: Bombay/Calcutta/Madras/Bengaluru), transport_mode(235: Airways->Air, Road Transport->Road) | Corrected via declared exact-match map (BR7/BR8), not the fuzzy engine |
| Title-case normalization (all-upper/all-lower source values) | 49 | destination_city (BANGALORE/CHENNAI/MUMBAI/bangalore/chennai/mumbai) | Corrected |
| Date logic violations (actual_delivery_date < dispatch_date — physically impossible) | 646 | actual_delivery_date, dispatch_date | Flagged only, neither date corrected (BR6); rows removed from viz_ready.csv |
| Impossible negative values corrected | 89 | shipment_weight_kg | abs() applied (BR3 — sign-flip evidence: median(abs(neg))=36.81 vs column median=36.89) |
| Impossible/ambiguous negative values flagged, NOT corrected | 150 | shipping_cost_inr | BR4 — magnitude mismatch rules out sign-flip; may be legitimate credit |
| Legitimate negative values flagged for transparency (not errors) | 3,008 + 3,547 | delay_days (early delivery), profit_inr (loss-making shipment) | BR1/BR2 — not treated as impossible |
| Out-of-range values flagged, NOT corrected | 120 | customer_rating (values -1.0, 0.0, 6.0, 7.5, 9.0 outside valid 1.0–5.0 scale) | BR5 — no decimal-typo divisor lands them back in range |
| Decimal-typo corrections APPLIED (column repair rate <=1%) | 226 | fuel_cost_inr(72), operational_cost_inr(154) | Value divided by 10/100 per row, `*_decimal_typo_flag=True` |
| Decimal-typo repair STOPPED at column level (repair rate >1%) | 3,101 + 3,345 + 2,066 + 798 = 9,310 candidates | shipment_weight_kg(6.754%), shipment_volume_cbm(7.139%), shipping_cost_inr(4.372%), revenue_inr(1.804%) | **NOT corrected.** All candidates flagged `*_outlier_flag=True` instead. See §4. |
| Header renames | 34 | all source columns | PascalCase/acronym-aware -> snake_case (e.g. `Shipping_Cost_INR` -> `shipping_cost_inr`, not `shipping_cost_i_n_r`) |

**Phone/Email (Stages 4.7/4.8): N/A** — no phone or email column exists in this dataset.
**Stage 6 Data Integration: N/A** — single source file.

## 3. Collision-guard results (Stage 4.4, mandatory before any fuzzy matching)

Ran `canonicals_collide()` (thefuzz `utils.full_process` preprocessing check) against all 9
categorical columns with a closed canonical set. **Result: 0 collisions.** Fuzzy matching was
authorized on all 9 columns.

| Column | Collision? | Fuzzy matching used |
|---|---|---|
| delivery_status | No | Yes |
| customer_type | No | Yes |
| industry | No | Yes |
| transport_mode | No | Yes |
| vehicle_type | No | Yes |
| product_category | No | Yes |
| return_status | No | Yes |
| warehouse_region | No | Yes |
| destination_region | No | Yes |

Highest within-set similarity found (informational, not a collision): `Not Returned` vs
`Returned` = 80 (below the 85 auto-correct threshold); `Freight Train` vs `Express Freight Train`
= 76.

**Scorer used:** `max(fuzz.ratio, fuzz.token_sort_ratio)`, both punctuation-preserving
(`full_process=False`), not `token_sort_ratio` alone (BR9). Justification: `token_sort_ratio`
tokenizes on whitespace and scores `"whole sale"` vs `"Wholesale"` at only 53 (would be
incorrectly dropped as UNKNOWN), while plain Levenshtein `ratio` correctly scores it 95 (this
typo affected 77 rows in `customer_type`).

**Post-fuzzy verification (mandatory, `02_post_fuzzy_verification.txt`):** printed `value_counts()`
for all 9 columns after correction and checked every canonical value against the post-clean
index. **`missing_canon = []` for all 9 columns** — no canonical value disappeared as a result of
fuzzy matching.

**Two columns needed an explicit synonym map instead of the fuzzy engine** (BR7/BR8), because the
correct correction is a real word-substitution/historical-rename, not a typo, and scored below the
70 flag threshold on both scorers: `destination_city` (Bombay->Mumbai, Calcutta->Kolkata,
Madras->Chennai, Bengaluru->Bangalore — 45 rows) and `transport_mode` (Airways->Air,
"Road Transport"->Road — 235 rows).

## 4. Decimal-typo screening (Stage 4.10) — the repair-rate gate

Per spec: if more than ~1% of a column's rows would be "corrected" as decimal typos, that is
evidence of a misread column scale/unit, not a population of individual typos — stop and report
instead of correcting. This gate fired on **4 of 6** screened columns:

| Column | Median | Candidates (>10x median) | Would-be repair rate | Decision |
|---|---|---|---|---|
| shipment_weight_kg | 37.17 | 3,112 | 6.754% | **STOPPED** — flagged outlier, not corrected |
| shipment_volume_cbm | 0.18 | 3,357 | 7.139% | **STOPPED** — flagged outlier, not corrected |
| shipping_cost_inr | 1,453.44 | 2,071 | 4.372% | **STOPPED** — flagged outlier, not corrected |
| revenue_inr | 9,610.65 | 798 | 1.804% | **STOPPED** — flagged outlier, not corrected |
| fuel_cost_inr | 4,294.76 | 74 | 0.239% | Applied — 72 rows divided by 10, 2 flagged statistical outlier |
| operational_cost_inr | 430.61 | 208 | 0.512% | Applied — 154 rows divided by 10/100, 54 flagged statistical outlier |

V6 (validation) confirms the two APPLIED columns did not reshape the distribution
(median/IQR shift <1.2% each), and confirms the four STOPPED columns are exactly as untouched
as intended — their pre/post median shift is <1% because nothing was changed. This column-level
stop is the single most consequential engineering decision in this run: an earlier draft of the
cleaning script applied the divisor correction regardless of repair rate, which would have
silently rewritten 6.75% of `shipment_weight_kg` and reshaped its distribution. Caught by
re-running the sanity check the spec requires, not by trusting the "N corrected" log line.

## 5. Stage 8 — viz_ready.csv filter decision

**Filter (physically impossible only):** `date_logic_violation_flag` — 646 rows where
`actual_delivery_date < dispatch_date`. Cannot be charted honestly on any delivery-performance
timeline; which of the two dates is wrong cannot be determined, so neither was corrected upstream,
and the row is excluded from the chart-facing file only (it remains in `cleaned_data.csv`, the
audit trail).

**Kept (statistical oddities, not impossible):** every other flag — negative shipping cost
(possible legitimate credit), negative delay/profit (legitimate business values), out-of-range
customer rating (bad single-field data, not an impossible shipment), all `*_outlier_flag` /
`*_decimal_typo_flag` from Stage 4.10, all `*_unknown_category_flag` / `*_fuzzy_review_flag`, and
all `*_missing_flag` nulls. Dropping these would discard real rows over a single suspect field.

**Result:** 30,000 -> 29,354 rows (**646 dropped, 2.1533%**).

## 6. Validation (Stage 5) — V1 through V13

All 13 checks were run against the final `cleaned_data.csv` (post Stage 7 transform). **12 PASS,
2 N/A (no phone/email column exists in this dataset), 0 FAIL, 0 WARNING.**

| Check | Status | Detail |
|---|---|---|
| V1 No null disguises | PASS | 0 found |
| V2 Critical columns null-free | PASS | all 27 critical columns clean |
| V3 No infinities | PASS | 0 found |
| V4 Correct dtypes | PASS | all match |
| V5 No impossible negatives remain uncorrected/unflagged | PASS | shipment_weight_kg: 0 negative remaining; shipping_cost_inr: 150 negative, all flagged |
| V6 Outlier handling did not reshape distribution | PASS | max shift 1.15% (operational_cost_inr IQR), all others <1% |
| V7 Email validity rate | N/A | no email column |
| V8 Phone E.164 compliance | N/A | no phone column |
| V9 No duplicate rows | PASS | 0 found (recomputed on actual output) |
| V10 Header compliance | PASS | all snake_case |
| V11 Row count integrity | PASS | raw=30,102, clean=30,000, removed sets match exactly (102=102) |
| V12 Schema completeness | PASS | 0 unaccounted columns, 0 missing expected columns |
| V13 Flag registry materialized | PASS | all 43 registered flags exist as dataframe columns |

**Overall status: READY FOR REPORTING.**

Full detail: `validation_report.md`.

## 7. Change log

`change_log.csv`: **53,388 rows**, one row per cell-level change/flag/decision, columns
`STAGE, COLUMN, SOURCE_ROW, CHANGE_TYPE, ORIGINAL_VALUE, NEW_VALUE, REASON`. `SOURCE_ROW` is the
`__source_row` value assigned immediately after extraction (0-based position in the raw file) —
stable across the Stage 4.11 dedup and the Stage 7 index reset, so every log entry remains
resolvable against both the raw file and `cleaned_data.csv`.

## 8. Scripts (reproducible from this folder alone)

| Script | Purpose |
|---|---|
| `stage2_extract.py` | Stage 2 — raw file inventory, structural anomaly check |
| `stage3_profile.py` | Stage 3 — full column-by-column statistical profile |
| `stage3b_correlation_checks.py` | Supplementary Stage 3 — null/business-rule correlation checks that informed Stage 1 decisions |
| `stage3c_more_checks.py` | Supplementary Stage 3 — collision guard, fuzzy-scorer comparison, synonym-map evidence gathering |
| `stage4_clean.py` | Stage 4 — full cleaning pipeline (4.0–4.11), writes `cleaned_data.csv` + `change_log.csv` |
| `stage5_validate.py` | Stage 5 — V1–V13, writes `validation_report.md` |
| `stage7_transform.py` | Stages 6/7 — integration (N/A, single source), dtype enforcement, derived columns, final null policy |
| `stage8_viz_prep.py` | Stage 8 — column ordering, writes `viz_ready.csv` and `cleaned_data.csv`, appends to `change_log.csv` |
| `stage9_analytics.py` | Stage 9 — recomputes every figure cited in `insights_report.md` |
| `verify_writeback.py` | Post-run check that the written files match what the pipeline reported |

Stage 9 (`insights_report.md`) was produced by the `analytics-expert` subagent, invoked directly
by name in the foreground (per `unattended-run-conventions` memory), briefed with the full flag
registry and business context. No fallback agent was needed.

## 9. Final artifact check

| File | Present | Size |
|---|---|---|
| `01_business_brief.yaml` | Yes | ~17 KB |
| `cleaned_data.csv` | Yes | 30,000 rows x 84 cols |
| `viz_ready.csv` | Yes | 29,354 rows x 84 cols |
| `change_log.csv` | Yes | 53,388 rows |
| `validation_report.md` | Yes | 13 checks, READY FOR REPORTING |
| `insights_report.md` | Yes | 30,373 bytes, produced by analytics-expert |

All six required deliverables verified present on disk in
`case_studies/logistics\`.
