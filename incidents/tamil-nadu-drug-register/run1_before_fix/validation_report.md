# Validation Report — Tamil Nadu Drug Manufacturer Licence Register

Source: `drug_manlist_1_0.csv` | Pipeline run date: 2026-09-22 | Encoding: Windows-1252 (cp1252)

## Row counts

| Stage | Rows | Columns |
|---|---|---|
| Raw (`input\drug_manlist_1_0.csv`) | 549 | 12 |
| Cleaned (`cleaned_data.csv`) | 549 | 43 |
| Viz-ready (`viz_ready.csv`) | 548 | 46 |

Note: the source note accompanying this run estimated "~736 records." The file has 737 raw
physical lines including the header, but the true CSV record count (correctly parsed with the
csv module and confirmed by pandas, both counting embedded newlines inside quoted multi-line
address/date cells as part of the same record) is **549 data rows**, all with a consistent
12 fields. This is a structural fact of the source file, not a parsing shortfall — reported in
Stage 2 and re-confirmed here.

No rows were removed between cleaned_data.csv and the raw file (0 exact duplicates found).
1 row was excluded from viz_ready.csv for a physically-impossible value (see V5/Stage 8 note
below); it remains in cleaned_data.csv as the audit trail requires.

## V1–V13 Validation Table

| Check | Name | Status | Detail |
|---|---|---|---|
| V1 | No null disguises remain | PASS | 0 found |
| V2 | Critical columns null-free | PASS | s_no: 0, name: 0, address: 0 |
| V3 | No infinities | PASS | 0 found |
| V4 | Correct dtypes | PASS | s_no int64; 6 date columns datetime64; name/address/licence-no columns string; all 18 flag columns + 9 derived status columns bool; num_licences_held/num_licences_expired int64 |
| V5 | Impossible negatives flagged | PASS | form_25_expiry_before_issue_flag: 1; form_28_expiry_before_issue_flag: 1; form_28d: 0 — flagged, not corrected (no reliable way to infer true dates) |
| V6 | Outlier handling did not reshape distribution | PASS (N/A) | No numeric measure columns exist in this dataset (it is an identifier/date registry); Stage 4.10 decimal-typo detection was never invoked, so there is nothing that could have reshaped a distribution |
| V7 | Email validity rate | PASS (N/A) | No email columns in this dataset |
| V8 | Phone E.164 compliance rate | PASS (N/A) | No phone columns in this dataset |
| V9 | No duplicate rows | PASS | `df.drop(columns='__source_row').duplicated().sum()` recomputed on the actual cleaned output = 0 |
| V10 | Header compliance | PASS | all headers snake_case, no whitespace/special characters |
| V11 | Row count integrity | PASS | `set(raw.__source_row) - set(clean.__source_row)` = `{}` = the set of `__source_row` values logged as `DUPLICATE_REMOVED` (also `{}`) — sets identical |
| V12 | Schema completeness | PASS | every column in cleaned_data.csv is exactly one of: the 12 expected-schema columns, `__source_row`, one of the 18 registered flag columns, or one of the 12 documented Stage-7 derived columns; set difference in both directions is empty |
| V13 | Flag registry materialized | PASS | all 18 flags in the Stage 4 flag registry exist as boolean columns on the cleaned dataset, and each True-count matches its corresponding change-log entry count |

**Overall Status: READY FOR REPORTING**

All 13 checks pass. V6–V8 pass as declared **not applicable** (documented above) rather than
vacuously true — this dataset has no numeric measure, email, or phone columns to check.

## Summary statistics

- Total rows in (raw): 549
- Total rows out (cleaned_data.csv): 549 — 0 rows removed
- Total rows out (viz_ready.csv): 548 — 1 row excluded (physically impossible expiry-before-issue)
- Total changelog entries: 5,429
  - NULL_STANDARDIZED: 2,683
  - DATE_PARSED: 1,502
  - STRING_NORMALIZED: 1,207
  - HEADER_RENAME: 12
  - DERIVED_COLUMN_ADDED: 12
  - OUTLIER_FLAGGED: 6
  - IMPOSSIBLE_NEGATIVE_FLAGGED: 2
  - NEAR_DUPLICATE_FLAGGED: 2
  - DTYPE_CAST: 2
  - COLUMN_REORDERED: 1
- Flag columns materialized: 18, covering 4 categories (unparseable dates, expiry-before-issue,
  cancelled licences, suspected licence-ID corruption) plus encoding-artifact and
  near-duplicate review flags
- Total distinct QC issues flagged across the dataset: 377 True flag-cells across 18 flag columns
  (a single row can carry more than one flag)

## Operational finding (why this run matters to the stated business goal)

Of 549 registered establishments:
- 487 hold a Form 25 licence; **478 of those (98.2%) are currently expired** as of 2026-09-22
- 265 hold a Form 28 licence; **254 of those (95.8%) are currently expired**
- 4 hold a Form 28D licence; 3 of those are currently expired
- **532 of 549 establishments (96.9%) have at least one expired licence** — see `insights_report.md`
  for the full operational breakdown and caveats on this number (in particular: it has not been
  adjusted for cancelled licences, which are a separate and stricter category than "expired").

This is reported here as a validation-stage fact (it falls directly out of V5/derived-column
checks); the interpretation and recommended action are Stage 9's job, not this report's.
