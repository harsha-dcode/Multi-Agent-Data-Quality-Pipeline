# Validation Report -- house_50k_sample.csv

Run date: 2026-07-29 (unattended)

Raw rows: 50000 | Cleaned rows: 49864 | viz_ready rows: (see Stage 8 / RUN_SUMMARY.md)

| Check ID | Check Name | Status | Detail |
|---|---|---|---|
| V1 | No null disguises | PASS | 0 found across 8 string columns |
| V2 | Critical columns null-free | PASS | checked ['property_id', 'country', 'property_type', 'city', 'listing_date', 'total_area', 'final_sale_price', 'listing_price', 'currency']: 0 nulls in all |
| V3 | No infinities | PASS | 0 inf values found |
| V4 | Correct dtypes | PASS | 0 mismatches -- all 46 brief-declared columns semantically correct (int64/float64 cast confirmed, listing_date parses cleanly via parse_dates, category columns' value sets are subsets of their brief canonical sets). CSV write/read cannot preserve pandas category/datetime64 dtype metadata -- that is a property of the text file format, not a defect; see 03_transform_report.txt for the in-memory dtype enforcement that was actually applied before writing. |
| V5 | No impossible negatives silently uncorrected | PASS | all negative-impossible columns have 0 negatives except total_area, which is fully flagged via total_area_sign_flag (994/994 negatives flagged) |
| V6 | Outlier handling did not reshape distribution | PASS | {'total_area': 'median shift 0.018%, IQR shift 0.145%', 'price_per_sqm': 'median shift 0.001%, IQR shift 0.056%', 'final_sale_price': 'median shift 0.014%, IQR shift 0.015%', 'listing_price': 'median shift 0.015%, IQR shift 0.015%', 'land_area': 'median shift 0.008%, IQR shift 0.018%', 'property_tax': 'median shift 0.000%, IQR shift 0.051%', 'hoa_fee': 'median shift 0.000%, IQR shift 0.000%'} |
| V7 | Email validity rate | N/A | No email columns present in this dataset |
| V8 | Phone E.164 compliance rate | N/A | No phone columns present in this dataset |
| V9 | No duplicate rows | PASS | 0 duplicate rows found on re-check of cleaned_data.csv |
| V10 | Header compliance (snake_case) | PASS | all 60 headers snake_case |
| V11 | Row count integrity | PASS | raw=50000 clean=49864 removed=136; removed_set == logged_removed: True |
| V12 | Schema completeness | PASS | unaccounted extra columns: NONE; missing expected columns: NONE |
| V13 | Flag registry materialized | PASS | {'total_area_sign_flag': 'df_true_count=994, log_count(surviving rows)=994, match=True', 'built_year_future_flag': 'true_count=0, expected 0, OK', 'total_area_outlier_flag': 'df_true_count=4848, log_count(surviving rows)=4848, match=True', 'price_per_sqm_outlier_flag': 'df_true_count=1573, log_count(surviving rows)=1573, match=True', 'final_sale_price_outlier_flag': 'df_true_count=424, log_count(surviving rows)=424, match=True', 'listing_price_outlier_flag': 'df_true_count=426, log_count(surviving rows)=426, match=True', 'land_area_outlier_flag': 'df_true_count=0, log_count(surviving rows)=0, match=True', 'land_area_decimal_typo_flag': 'df_true_count=1, log_count(surviving rows)=1, match=True'} |

## Overall Status: READY FOR REPORTING


## Summary statistics

- Total rows in (raw): 50000
- Total rows out (cleaned_data.csv): 49864
- Rows removed: 136 (136 exact full-row duplicates, Stage 4.11)
- Total change-log entries: 11068
- Change type breakdown: {'OUTLIER_FLAGGED': 7289, 'TYPO_CORRECTED': 2641, 'NEGATIVE_FLAGGED': 996, 'DUPLICATE_REMOVED': 136, 'NUMERIC_CLEANED': 3, 'STRING_NORMALIZED': 1, 'DATE_PARSED': 1, 'OUTLIER_DECIMAL_TYPO_CORRECTED': 1}
- Total flag columns materialized: 8
- Total cells actually value-modified (not just flagged): 2642 (2641 city alias corrections + 1 land_area decimal-typo correction + 0 null standardizations)