# Validation Report -- Logistics Supply Chain Dataset

Raw rows: 30102 | Cleaned rows: 30000 | viz_ready rows: (see Stage 8 section below)

| Check ID | Check Name | Status | Detail |
|---|---|---|---|
| V1 | No null disguises | PASS | 0 found |
| V2 | Critical columns null-free | PASS | all clean |
| V3 | No infinities | PASS | 0 found |
| V4 | Correct dtypes | PASS | all match |
| V5 | No impossible negatives remain uncorrected/unflagged | PASS | shipment_weight_kg: 0 negative, 0 UNFLAGGED; shipping_cost_inr: 150 negative, 0 UNFLAGGED |
| V6 | Outlier handling did not reshape distribution | PASS | shipment_weight_kg: median_shift=0.57% iqr_shift=0.16% OK; shipment_volume_cbm: median_shift=0.27% iqr_shift=0.16% OK; shipping_cost_inr: median_shift=0.18% iqr_shift=0.09% OK; fuel_cost_inr: median_shift=0.05% iqr_shift=0.82% OK; operational_cost_inr: median_shift=0.02% iqr_shift=1.15% OK; revenue_inr: median_shift=0.00% iqr_shift=0.02% OK |
| V7 | Email validity rate | N/A | No email column in this dataset |
| V8 | Phone E.164 compliance rate | N/A | No phone column in this dataset |
| V9 | No duplicate rows | PASS | 0 found |
| V10 | Header compliance | PASS | all snake_case |
| V11 | Row count integrity | PASS | raw=30102 clean=30000 removed_actual=102 removed_logged=102 sets_match=True |
| V12 | Schema completeness | PASS | unaccounted_extra_cols=[] missing_expected_cols=[] |
| V13 | Flag registry materialized | PASS | 43 flags checked, all present as columns |

## Overall Status: READY FOR REPORTING

## Summary statistics

- Total rows in (raw): 30102
- Total rows out (cleaned_data.csv): 30000
- Total rows removed (exact duplicates): 102
- Total change-log rows (cell-level modifications/flags logged): 53388
- Total flag columns materialized: 43
- date_logic_violation_flag (physically impossible, BR6): 646
- shipment_weight_kg_sign_flag (corrected via abs(), BR3): 89
- shipping_cost_inr_negative_flag (flagged not corrected, BR4): 152
- delay_days_negative_flag (legitimate early delivery, BR1): 3018
- profit_inr_negative_flag (legitimate loss, BR2): 3567
- customer_rating_out_of_range_flag (BR5): 122

### Decimal-typo screening (Stage 4.10) -- columns where repair was STOPPED, not applied
- shipment_weight_kg: repair_rate=6.754% (>1% threshold), 3112 candidates flagged STATISTICAL_OUTLIER, 0 corrected
- shipment_volume_cbm: repair_rate=7.139% (>1% threshold), 3357 candidates flagged STATISTICAL_OUTLIER, 0 corrected
- shipping_cost_inr: repair_rate=4.372% (>1% threshold), 2071 candidates flagged STATISTICAL_OUTLIER, 0 corrected
- revenue_inr: repair_rate=1.804% (>1% threshold), 798 candidates flagged STATISTICAL_OUTLIER, 0 corrected