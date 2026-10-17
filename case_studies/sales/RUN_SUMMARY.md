# RUN SUMMARY -- messy_sales.csv (Stage 1-9 pipeline)

Run date: 2026-07-29 (unattended -- no user available mid-run; every judgment call is written into `01_business_brief.yaml` and the stage reports below)

## Source

- Input path: `<input>/messy_sales.csv`
- File size: 33,863 bytes
- MD5: `5e21b26fbb3500d2ee4f428788102705`
- SHA-256: `79f672119c134d5dd5b2556556a4aef526e3f16efd9154ff3b6208f31eebfb34`
- UTF-8 BOM present: **True** (`b'\xef\xbb\xbf'` at byte 0) -- see `00_peek_report.txt`
- Header defects confirmed: `region ` has a trailing space (silent-KeyError risk on `df['region']`); `customer name`, `Customer Email`, `Phone Number`, `Units Sold`, `Total Revenue` all contain embedded spaces requiring snake_case normalization

## Extraction-layer defect quantification (Stage 2)

- Total cells (raw grid, 312 rows x 11 cols): 3,432
- Cells a naive `pd.read_csv()` (no dtype pin, default NA handling) would preserve verbatim: 3,345 (97.47%)
- Cells a naive `pd.read_csv()` would alter or silently null: 87 (2.53%) -- see `00_peek_report.txt` for the row-level examples
- Mitigation: this pipeline loads with `encoding='utf-8-sig', dtype=str, keep_default_na=False`

## Row counts

- Raw rows: 312
- `cleaned_data.csv` rows (audit trail, flagged rows kept): 281 (31 removed as duplicates, 9.94%)
- `viz_ready.csv` rows (chart-ready, impossible-value rows filtered): 266 (15 dropped from cleaned_data.csv, 5.34%)
- Overall raw -> viz_ready: 312 -> 266 (46 fewer rows, 14.74%)

## Duplicate removal breakdown (Stage 4.11)

- Exact post-normalization duplicates removed: 29
- Same-order_id / differs-only-by-customer_name-capitalization (PK-conflict exception): 2
- Total removed: 31 (= raw 312 - cleaned 281 = 31)

## Cross-column check: total_revenue vs units_sold * unit_price (business_rules.BR1)

- Rows with all three fields present (comparable): 209
- Rows disagreeing by more than 1% (excluding sign-flagged rows), recomputed directly from `cleaned_data.csv`: 13 (6.22% of comparable rows)
- Decision: **flagged via `revenue_mismatch_flag`, never recomputed/overwritten** -- which of the three fields is wrong cannot be determined from the data alone (see brief BR1). `revenue_calculated` is retained as a derived column for downstream comparison.
- Note: `03_clean_report.txt` reports 15/233 (6.44%) for this same check because it runs *before* Stage 4.11 deduplication (233 comparable rows out of the pre-dedup 312). The number above is recomputed independently, post-dedup, straight from `cleaned_data.csv` (209 comparable rows out of 281) -- both are correct for their own denominator; don't conflate them.

## Collision guard results (Stage 4.4, run before any fuzzy matching)

- `region`: canonical set ['North', 'South', 'East', 'West', 'Northeast'] -> **no collision -- fuzzy matching SAFE at threshold 85**
- `product`: canonical set ['Alpha', 'Beta', 'Gamma', 'Delta'] -> **no collision -- fuzzy matching SAFE at threshold 85**
- `channel`: canonical set ['Retail', 'Wholesale', 'Online', 'Brick & Mortar', 'B2B', 'B2C'] -> **no collision -- fuzzy matching SAFE at threshold 85**

## Change log breakdown (`change_log.csv`, one row per change)

- Total change-log entries: 1824

| CHANGE_TYPE | Count |
|---|---:|
| STRING_NORMALIZED | 649 |
| DATE_PARSED | 299 |
| PHONE_NORMALIZED | 294 |
| NULL_STANDARDIZED | 276 |
| TYPO_CORRECTED | 122 |
| NUMERIC_CLEANED | 35 |
| EMAIL_NORMALIZED | 32 |
| DUPLICATE_REMOVED | 31 |
| OUTLIER_FLAGGED | 28 |
| NEGATIVE_FLAGGED | 27 |
| EMAIL_REPAIRED | 12 |
| HEADER_RENAME | 11 |
| OUTLIER_DECIMAL_TYPO_CORRECTED | 7 |
| PHONE_COUNTRY_UNKNOWN | 1 |

## Flag registry (materialized boolean columns on `cleaned_data.csv`)

| Flag column | True count (of 281) |
|---|---:|
| `channel_fuzzy_review_flag` | 0 |
| `channel_unknown_category_flag` | 0 |
| `customer_email_invalid_flag` | 0 |
| `customer_email_repaired_flag` | 11 |
| `near_duplicate_flag` | 0 |
| `order_date_unparseable_flag` | 8 |
| `phone_number_country_unknown_flag` | 1 |
| `product_fuzzy_review_flag` | 0 |
| `product_unknown_category_flag` | 0 |
| `region_fuzzy_review_flag` | 23 |
| `region_unknown_category_flag` | 0 |
| `revenue_mismatch_flag` | 13 |
| `total_revenue_sign_flag` | 13 |
| `unit_price_outlier_flag` | 1 |
| `unit_price_sign_flag` | 7 |
| `units_sold_non_integer_flag` | 6 |
| `units_sold_outlier_flag` | 6 |
| `units_sold_sign_flag` | 5 |

## Stage 5 validation (V1-V13)

- Checks PASS: 12
- Checks WARNING: 0
- Checks FAIL: 1  (V2 -- critical columns null-free -- fails BY DESIGN: `order_date`/`units_sold`/`unit_price` are `never_impute` per the business brief, so genuine source-data nulls are left visible rather than fabricated. See `validation_report.md` for the full table and the explicit justification section.)
- Full table: see `validation_report.md`

## Stage 8: viz_ready.csv filter

- Filter rule: drop rows where `units_sold_sign_flag` OR `unit_price_sign_flag` OR `total_revenue_sign_flag` is True (physically impossible negative value). Every other flag (fuzzy-review confidence, statistical outliers, revenue mismatch, unparseable dates, near-duplicates) is KEPT -- see `05_viz_ready_report.txt` for the full reasoning per flag.
- Drop: 281 -> 266 (15 dropped, 5.34%)

## Stage 9: analytics

- Performed by: `@analytics-expert` (invoked directly, foreground, per unattended-run convention -- NOT a fallback)
- Scope: General EDA, auto-selected (unattended run, no user available to choose a scope)
- Analyzed: `viz_ready.csv` (266 rows), briefed with full flag-column semantics and cleaning caveats so aggregates are not silently distorted by rows the pipeline had already flagged as suspect
- Headline finding: 6 bulk orders (`units_sold_outlier_flag`, 2.3% of rows) account for the large majority of total revenue and units -- see `insights_report.md` for exact percentages, significance tests, and all 8 recommendations

## Artifact manifest

| Artifact | Size (bytes) | Status |
|---|---:|---|
| `01_business_brief.yaml` | 10,176 | OK |
| `cleaned_data.csv` | 66,272 | OK |
| `viz_ready.csv` | 67,256 | OK |
| `change_log.csv` | 247,474 | OK |
| `validation_report.md` | 3,413 | OK |
| `insights_report.md` | 28,203 | OK |

Numbered scripts in this directory (`stage2a_peek.py` ... `stage8_viz_prep.py`, this script) reproduce the entire run from `messy_sales.csv` alone; run them in numeric order.
