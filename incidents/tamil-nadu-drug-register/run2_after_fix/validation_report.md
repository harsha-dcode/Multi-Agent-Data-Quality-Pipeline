# Validation Report — drug_manlist_1_0.csv (Tamil Nadu Drug Manufacturer Licence Register)

## Row counts

| Stage | Row count |
|---|---|
| Raw input | 549 |
| `cleaned_data.csv` (audit trail, flags kept) | 549 |
| `viz_ready.csv` (filtered for charting) | 547 |

No rows were removed between raw and `cleaned_data.csv` — no exact duplicate rows exist
(verified: `df.duplicated(subset=core_columns).sum() == 0`). Two rows were excluded only
from `viz_ready.csv` (see Stage 8 note in the pipeline summary) because they carry a
physically-impossible value (BR1: no licence held at all; BR2: expiry date before issue
date) that would distort a chart.

## V1–V13 results

| Check ID | Check Name | Status | Detail |
|---|---|---|---|
| V1 | No null disguises remain | PASS | 0 null-disguise cells found in string columns |
| V2 | Critical columns null-free | PASS | s_no=0, name=0, address=0 nulls |
| V3 | No infinities | PASS | 0 infinite values found |
| V4 | Correct dtypes | PASS | all checked columns match expected dtype (int64/string/datetime64/bool) |
| V5 | No impossible negatives remain uncorrected | PASS | N/A — no numeric measure columns exist; s_no (only numeric column) has 0 non-positive values |
| V6 | Outlier handling did not reshape distribution | PASS | N/A — Stage 4.10 does not apply (no numeric measure columns); nothing was reshaped |
| V7 | Email validity rate | PASS | N/A — no email column present |
| V8 | Phone E.164 compliance rate | PASS | N/A — no phone column present |
| V9 | No duplicate rows | PASS | `df.duplicated()` recomputed on the actual cleaned output (excl. `__source_row`) = 0 |
| V10 | Header compliance | PASS | all headers snake_case |
| V11 | Row count integrity | PASS | raw rows=549, clean rows=549, rows logged as `DUPLICATE_REMOVED`=0; `set(raw.__source_row) - set(clean.__source_row)` is empty, matching the (empty) removed-row log exactly |
| V12 | Schema completeness | PASS | every column is accounted for as exactly one of: expected-schema column, `__source_row`, a flag-registry column, or a documented Stage-7 derived column; no unaccounted columns in either direction |
| V13 | Flag registry materialized | PASS | every one of the 22 `*_flag` columns' True count reconciles exactly against its corresponding changelog entries (see method note below) |

**V13 method note:** each flag type was reconciled against its specific changelog source
rather than a blanket count: `*_missing_flag` against `NULL_STANDARDIZED` + null-producing
`DATE_PARSED` entries for that column; `*_unparseable_flag` / `*_multi_value_flag` against
`DATE_PARSED` entries carrying the matching reason text; `*_cancelled_flag` /
`*_claa_reference_flag` / `no_licence_held_flag` / `*_expiry_before_issue_flag` against
`OUTLIER_FLAGGED` entries; `near_duplicate_flag` against distinct `SOURCE_ROW` values in
`NEAR_DUPLICATE_FLAGGED` entries. All 22 reconciled with zero discrepancy on the second pass
(the first pass used a cruder substring match and produced 4 false-positive mismatches on the
`*_unparseable_flag` columns, corrected by matching on the actual logged reason text instead).

## Overall Status: **READY FOR REPORTING**

All 13 checks PASS. The N/A results (V5, V6, V7, V8) reflect genuine absence of the
relevant column type in this dataset (no numeric measures, no email, no phone), not
skipped checks — each is stated explicitly with its reasoning rather than silently
omitted.

## Summary statistics

- Total rows in (raw): 549
- Total rows out (`cleaned_data.csv`): 549
- Total rows out (`viz_ready.csv`): 547 (2 dropped, 0.36%)
- Total changelog entries: 4,687
- Total distinct issues flagged (rows with at least one True flag column, excluding the
  9 `*_missing_flag` columns which mirror already-expected "does not hold this licence
  type" nulls): see `near_duplicate_flag` (36 rows / 18 rows across 21 pairs — some rows
  appear in more than one pair), `no_licence_held_flag` (1 row), `*_expiry_before_issue_flag`
  (1 row, both licence types), `*_cancelled_flag` (6 rows total), `*_claa_reference_flag`
  (1 row), `*_unparseable_flag` (9 cells across 4 columns), `*_multi_value_flag` (2 cells)

## Grain re-derivation (Stage 3 vs Stage 1 brief)

The brief's `grain.verified_by` expression was re-run independently in Stage 3 against the
freshly-loaded raw data (not read from the brief's stated conclusion). It reproduced the
identical result: 4 duplicate-address groups (8 rows) after moderate normalization,
545 of 549 addresses distinct. No `BRIEF_CLAIM_UNVERIFIED` finding was raised. This directly
supersedes a prior run's brief, which asserted "ADDRESS is 100% unique across all 549 rows"
without a `verified_by` expression — a claim this run's measurement shows was false.
