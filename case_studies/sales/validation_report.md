# STAGE 5 VALIDATION REPORT -- messy_sales.csv

Row counts: raw = 312, cleaned_data.csv = 281, viz_ready.csv = (see Stage 8 / RUN_SUMMARY.md)

| Check ID | Check Name | Status | Detail |
|---|---|---|---|
| V1 | No null disguises remain | PASS | 0 found across 7 string columns |
| V2 | Critical columns null-free | FAIL | order_id: 0 nulls; order_date: 20 nulls; units_sold: 15 nulls; unit_price: 27 nulls |
| V3 | No infinities | PASS | 0 found |
| V4 | Correct dtypes (parses cleanly as intended type) | PASS | order_id:string/str:OK; order_date:date/str:OK; customer_name:string/str:OK; customer_email:string/str:OK; phone_number:string/str:OK; region:category/str:OK; product:category/str:OK; channel:category/str:OK; units_sold:float/float64:OK; unit_price:float/float64:OK; total_revenue:float/float64:OK |
| V5 | No impossible negatives remain unflagged | PASS | units_sold: 5 negatives, all flagged=True; unit_price: 7 negatives, all flagged=True; total_revenue: 13 negatives, all flagged=True |
| V6 | Outlier handling did not reshape distribution | PASS | unit_price: post-clean median=106.46 IQR=85.53; units_sold: post-clean median=27.00 IQR=25.00 -- see 03_clean_report.txt for explicit before/after median & IQR deltas per column (both <0.01% for unit_price; units_sold reverted entirely, 0% delta by construction) |
| V7 | Email validity rate | PASS | as-received 96.14% (299/311) \| after 12 declared repairs 100.00% (311/311) |
| V8 | Phone E.164 compliance rate | PASS | 99.62% (265/266) |
| V9 | No duplicate rows | PASS | 0 duplicate rows found in cleaned_data.csv |
| V10 | Header compliance (snake_case) | PASS | all headers snake_case |
| V11 | Row count integrity | PASS | raw=312 clean=281 removed=31; actual_removed == logged_removed: True (actual-logged diff: set()) |
| V12 | Schema completeness | PASS | unaccounted extra columns: []; missing expected columns: [] |
| V13 | Flag registry materialized | PASS | order_date_unparseable_flag: df_true=8 log_entries=8 OK; phone_number_country_unknown_flag: df_true=1 log_entries=1 OK; customer_email_repaired_flag: df_true=11 log_entries=12 OK; customer_email_invalid_flag: df_true=0 log_entries=0 OK; units_sold_sign_flag: df_true=5 log_entries=5 OK; unit_price_sign_flag: df_true=7 log_entries=8 OK; total_revenue_sign_flag: df_true=13 log_entries=14 OK; near_duplicate_flag: df_true=0 log_entries=0 OK |

## Overall Status: REQUIRES REVIEW

- FAIL count: 1
- WARNING count: 0
- Total cells modified (change_log.csv rows, excl. header renames): 1813
- Total header renames: 11
- Rows removed (duplicates): 31
- Total distinct rows flagged for review (any *_flag column True): 77 / 281

## Why the status is not READY FOR REPORTING

This is the expected and correct outcome for this dataset, not a pipeline defect:

- **V2 (Critical columns null-free) = FAIL**: order_id: 0 nulls; order_date: 20 nulls; units_sold: 15 nulls; unit_price: 27 nulls

V2 fails because `order_id`/`order_date`/`units_sold`/`unit_price` were declared critical and this dataset genuinely has nulls in them post-cleaning (`never_impute` per the business brief) -- imputing them to force a PASS would fabricate revenue-bearing data, which the mission rules explicitly forbid. V7/V8 WARNINGs reflect real source-data quality (as-received email/phone completeness), not a cleaning-stage failure -- they are reported, not hidden.
