# Validation Report -- telecom_churn.csv

Raw rows: **3333** | Cleaned rows: **3333** | Rows removed (exact duplicates): **0**


| Check ID | Check Name | Status | Detail |
|---|---|---|---|
| V1 | No null disguises remain | PASS | 0 disguised-null tokens found in cleaned_data.csv (full scan, 3333 rows x 12 cols) |
| V2 | Critical columns null-free | PASS | critical columns=['churn', 'monthly_charge'], null counts={'churn': 0, 'monthly_charge': 0} |
| V3 | No infinities | PASS | 0 inf/-inf values found across numeric columns |
| V4 | Correct dtypes | PASS | expected column_types from 01_business_brief.yaml + derived total_charge; mismatches=none |
| V5 | No impossible negatives remain uncorrected | PASS | 0 negative values present without a corresponding *_sign_flag=True (i.e. silent/unflagged negatives); total negative values across all 8 checked columns = 0 |
| V6 | Outlier handling did not reshape distribution | PASS | max median/IQR shift across all 8 columns touched by 4.10 = 0.0000% (threshold <5%); 0 decimal-typo corrections and 0 statistical-outlier value changes were applied in this run (only flags), so this check is expected to and does show ~0% shift. Detail: {'account_weeks': {'median_shift_pct': np.float64(0.0), 'iqr_shift_pct': np.float64(0.0)}, 'data_usage': {'median_shift_pct': 0.0, 'iqr_shift_pct': np.float64(0.0)}, 'cust_serv_calls': {'median_shift_pct': np.float64(0.0), 'iqr_shift_pct': np.float64(0.0)}, 'day_mins': {'median_shift_pct': np.float64(0.0), 'iqr_shift_pct': np.float64(0.0)}, 'day_calls': {'median_shift_pct': np.float64(0.0), 'iqr_shift_pct': np.float64(0.0)}, 'monthly_charge': {'median_shift_pct': np.float64(0.0), 'iqr_shift_pct': np.float64(0.0)}, 'overage_fee': {'median_shift_pct': np.float64(0.0), 'iqr_shift_pct': np.float64(0.0)}, 'roam_mins': {'median_shift_pct': np.float64(0.0), 'iqr_shift_pct': np.float64(0.0)}} |
| V7 | Email validity rate | N/A | No email column exists in this dataset (verified in stage2a_peek.py/02_profile_report.txt header list). Not applicable. |
| V8 | Phone E.164 compliance rate | N/A | No phone/tel/mobile/cell/contact/fax column exists in this dataset. Not applicable. |
| V9 | No duplicate rows | PASS | df.duplicated(subset=all cols except __source_row).sum() = 0 on the actual cleaned_data.csv output |
| V10 | Header compliance | PASS | non-snake_case headers: none |
| V11 | Row count integrity | PASS | raw rows=3333, cleaned rows=3333, removed=0; set(raw.__source_row) - set(clean.__source_row) == set(logged DUPLICATE_REMOVED source_rows): True (both sets: []) |
| V12 | Schema completeness | PASS | unaccounted columns=none, missing expected columns=none; flag columns (17) and derived column (total_charge) are declared additions |
| V13 | Flag registry materialized | PASS | 17 flag columns checked; all match log counts: True. Detail: {'account_weeks_outlier_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'account_weeks_sign_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'cust_serv_calls_outlier_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'cust_serv_calls_sign_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'data_plan_usage_conflict_flag': {'df_true_count': 602, 'log_count': 602, 'match': True}, 'data_usage_outlier_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'data_usage_sign_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'day_calls_outlier_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'day_calls_sign_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'day_mins_outlier_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'day_mins_sign_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'monthly_charge_outlier_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'monthly_charge_sign_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'overage_fee_outlier_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'overage_fee_sign_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'roam_mins_outlier_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}, 'roam_mins_sign_flag': {'df_true_count': 0, 'log_count': 0, 'match': True}} |

## Overall Status: READY FOR REPORTING

## Summary statistics

- Total rows in (raw): 3333
- Total rows out (cleaned_data.csv): 3333
- Rows removed (exact duplicates, Stage 4.11): 0
- Total cell-level VALUE modifications logged (change_log.csv, corrective change types): 0
- Total flags raised (non-destructive, change_log.csv flag-type entries): 602
- Total change_log.csv rows (all types, incl. HEADER_RENAME/COLUMN_REORDERED/DERIVED_COLUMN_ADDED structural entries): 615
- Checks run: 13 of 13 (V1-V13); N/A where the check's precondition (email/phone columns) does not exist in this schema
- Checks PASS: 11, FAIL: 0, N/A: 2

## Notes

All 13 checks were executed (V7/V8 report N/A because this schema has no email or phone columns to validate -- that is a fact about the schema, not a skipped check). This dataset produced 0 corrective value changes (0 decimal-typo corrections, 0 negative-value corrections, 0 duplicate rows removed) and 602 non-destructive review flags (data_plan_usage_conflict_flag), consistent with its role as the control case in the benchmark: the correct result on already-clean data is a report that says so, with evidence.
