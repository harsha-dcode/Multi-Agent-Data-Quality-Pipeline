# STAGE 5 VALIDATION REPORT

Raw rows: **58164**  |  Cleaned rows (cleaned_data.csv): **55874**  |  viz_ready rows: *(see viz_ready.csv / RUN_SUMMARY.md for Stage 8 numbers)*

| Check ID | Check Name | Status | Detail |
|---|---|---|---|
| V1 | No null disguises remain | PASS | 0 found |
| V2 | Critical columns null-free | FAIL | {'date_of_admission': 312, 'billing_amount': 661, 'admission_type': 80} |
| V3 | No infinities | PASS | 0 found |
| V4 | Correct dtypes (castability test, not CSV-round-trip dtype label - see code comment) | PASS | all match |
| V5 | No impossible negatives remain uncorrected/unflagged | PASS | age & length_of_stay negatives corrected (BR1/BR3); billing_amount negatives flagged not corrected (BR2, by design); 0 unflagged silent negatives |
| V6 | Outlier handling did not reshape distribution | PASS | 0 decimal-typo corrections were applied to ANY numeric column in this dataset (see 03_stage4_report.txt Stage 4.10) - medians verified identical before/after by construction; billing_amount: 0 decimal-typo corrections applied; age: 0 decimal-typo corrections applied; room_number: 0 decimal-typo corrections applied; length_of_stay: 0 decimal-typo corrections applied |
| V7 | Email validity rate | N/A | No email column exists in this dataset (19 source columns surveyed in Stage 2/3 - none are email fields) |
| V8 | Phone E.164 compliance rate | N/A | No phone column exists in this dataset (19 source columns surveyed in Stage 2/3 - none are phone fields) |
| V9 | No duplicate rows | PASS | 0 duplicates found on recomputation against actual output |
| V10 | Header compliance (snake_case) | PASS | all compliant |
| V11 | Row count integrity | PASS | raw=58164, cleaned=55874, removed=2290; set(raw.__source_row)-set(clean.__source_row) == set(logged DUPLICATE_REMOVED rows): True (diff count: 0) |
| V12 | Schema completeness | PASS | unaccounted_extra_columns=[]; missing_expected_columns=[] |
| V13 | Flag registry materialized | PASS | 46 flags registered, 46 found as boolean columns; True counts: {'blood_gender_swap_corrected_flag': 304, 'test_results_medication_swap_corrected_flag': 336, 'gender_unresolved_category_flag': 9, 'blood_type_unresolved_category_flag': 6, 'medical_condition_unresolved_category_flag': 0, 'admission_type_unresolved_category_flag': 0, 'insurance_provider_unresolved_category_flag': 0, 'test_results_unresolved_category_flag': 5, 'medication_unresolved_category_flag': 9, 'date_of_admission_unparseable_flag': 194, 'date_of_admission_ambiguous_date_flag': 181, 'discharge_date_unparseable_flag': 193, 'discharge_date_ambiguous_date_flag': 149, 'discharge_before_admission_flag': 1013, 'billing_amount_sentinel_flag': 76, 'age_sign_flag': 214, 'billing_amount_sign_flag': 196, 'length_of_stay_sign_flag': 917, 'room_number_sign_flag': 0, 'age_domain_outlier_flag': 304, 'billing_amount_decimal_typo_flag': 0, 'billing_amount_outlier_flag': 0, 'age_decimal_typo_flag': 0, 'age_outlier_flag': 0, 'room_number_decimal_typo_flag': 0, 'room_number_outlier_flag': 0, 'length_of_stay_decimal_typo_flag': 0, 'length_of_stay_outlier_flag': 0, 'length_of_stay_qa_mismatch_flag': 1121, 'near_duplicate_composite_key_flag': 9249, 'age_missing_flag': 301, 'gender_missing_flag': 407, 'blood_type_missing_flag': 325, 'date_of_admission_missing_flag': 312, 'insurance_provider_missing_flag': 559, 'billing_amount_missing_flag': 661, 'room_number_missing_flag': 580, 'admission_type_missing_flag': 80, 'discharge_date_missing_flag': 316, 'medication_missing_flag': 418, 'test_results_missing_flag': 501, 'length_of_stay_missing_flag': 2005, 'admission_year_missing_flag': 312, 'admission_month_missing_flag': 312, 'admission_yearmonth_missing_flag': 312, 'length_of_stay_recomputed_days_missing_flag': 623} |

## Overall Status: REQUIRES REVIEW

## Why the failing checks are the correct outcome, not a defect

**V2 (Critical columns null-free)**: date_of_admission, billing_amount, and admission_type are designated critical because a null there makes the row unusable for this dataset's stated business goal (time-series grain, financial rollups, operational cuts). Their nulls are NOT fabricated data quality - they are genuinely unparseable dates (garbage patterns like `0000-00-00`, `31/31/2021`), genuinely missing source values, or domain-specific null-disguise tokens (`pending`, `see invoice`, `TBD`) correctly nulled per the brief's gate logic. The alternative - guessing a date or a dollar amount - is explicitly prohibited by this pipeline's mission rule ('never guess a value into existence'). This failure is the pipeline correctly refusing to hide a real data quality problem; see `*_missing_flag` and `*_unparseable_flag` columns for exactly which rows and why. Detail: {'date_of_admission': 312, 'billing_amount': 661, 'admission_type': 80}

No other checks failed.

## Summary Statistics
- Total rows in (raw): 58164
- Total rows out (cleaned_data.csv): 55874
- Exact duplicates removed: 2290
- Total change-log entries: 154302
- Total flag columns materialized: 46
- Total flagged issues (sum of all flag column True counts, rows may be multi-flagged): 22500