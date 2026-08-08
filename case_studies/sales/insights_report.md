# Sales Orders — Stage 9 Analytics Report

**Scope note:** No user was available to select an analysis scope for this run, so **General EDA** was auto-selected per the Stage 9 default. This report covers distribution shape, group comparisons, correlations, and time trend, all tested statistically, plus what the cleaning pipeline's own defect log implies about the source systems.

**Source file analyzed:** `viz_ready.csv` (266 rows, 34 columns) — **not** `cleaned_data.csv` (281 rows). The 15 rows excluded between the two carried physically impossible negative `units_sold`/`unit_price`/`total_revenue` and were correctly dropped before this analysis; including them would have corrupted every statistic below.

All numbers in this report were computed directly from `viz_ready.csv`, `change_log.csv`, `03_clean_report.txt`, and `validation_report.md` with pandas/numpy/scipy — none are estimated.

---

## 1. The headline

**Don't trust the average order value or a "top customers" leaderboard from this file as-is, and don't greenlight a region/product/channel strategy off it either.** Six orders (2.3% of the file) carry `units_sold` in the thousands and account for **80.5% of total revenue and 95.5% of total units** — the mean total_revenue swings from \$63,215 down to \$4,449 depending only on whether those 6 rows and 13 flagged decimal-shift rows are included, while the median barely moves (\$2,493 → \$2,397). Every group comparison actually run — revenue by region, by product, by fulfillment channel, by B2B/B2C — comes back statistically null (all p > 0.28). The one operational fact worth acting on immediately: 13 rows (and at least one more that slipped past the check) show total_revenue off from its own cross-check field by a clean 100x/50x/10x/0.1x/0.01x — a decimal-shift bug, not noise — and it was deliberately left unresolved in the data because the pipeline can't tell which of the two fields is right. That needs a human with access to the source system, not another cleaning pass.

---

## 2. Recommendations

### R1 — Fix the decimal-shift bug in revenue capture/export before trusting any revenue total
- **Do what:** Audit the order-entry or export pipeline for a scale/currency-multiplier bug (e.g., a units toggle, a currency-cents-vs-dollars mismatch, or a spreadsheet formula pasted with the wrong multiplier) that produces `total_revenue` values exactly 100x, 50x, 10x, 0.1x, or 0.01x the cross-check value (`units_sold * unit_price`).
- **Why:** 13 of 233 comparable rows (`total_revenue` and `revenue_calculated` both present) disagree by >1%, and **all 13 mismatch ratios cluster at clean scalar multiples** (100x: 5 rows, 50x: 2, 10x: 0, 0.1x: 5, 0.01x: 1 — see `03_clean_report.txt` §4.10 cross-column check and `revenue_mismatch_flag` in the data). That pattern is a systematic bug signature, not random entry error. See §3 and §4.
- **Who:** Owner of the order-management/billing export pipeline (the system that populates `total_revenue` independently of `units_sold`/`unit_price`).
- **Cost/risk:** Low cost — this is a source-system investigation, not a re-clean. Risk of inaction: any revenue rollup (dashboards, forecasts) built on raw `total_revenue` is currently wrong by up to 100x on ~5-6% of rows, and that error compounds silently since neither pipeline nor BI tool corrects it.
- **Falsified if:** The 13 flagged rows turn out to have no common upstream cause (e.g., different customers, different months, different systems, no shared scalar pattern on closer inspection) — in which case this is scattered manual entry error, not a systematic bug, and the fix is a validation rule, not a system audit.

### R2 — Do not publish "Top Customers by Revenue" or headline AOV without excluding the 6 bulk-outlier rows and disclosing the exclusion
- **Do what:** Any customer-ranking or average-order-value report built from this data must either (a) report median total_revenue as the headline number, not mean, or (b) split "bulk/wholesale" from "standard" orders into two segments and report each separately.
- **Why:** Mean `total_revenue` is \$63,215 across all 233 comparable rows; excluding the 13 revenue-mismatch rows it's \$58,246 (-7.9%); excluding the 6 `units_sold_outlier_flag` rows (units in the thousands: 4,000/15,000/15,000/16,000/39,000/49,000) it drops to \$12,595; excluding both it's \$4,449 — a 14x swing depending purely on which flags you honor. The **median** moves only from \$2,493 to \$2,397 across the same exclusions (all figures computed directly from `viz_ready.csv`). Separately, "top customer by revenue" changes identity depending on flag handling: raw ranking is led by `meera.krishnan@example.com` at \$5.88M (driven by one \$5.26M bulk row plus one \$258,768 mismatch row); excluding the bulk row she's still #1 at \$364,288 — but \$340,700 of that is a single unflagged row (`ORD-1010`) that could not be cross-checked at all (see R3) and is almost certainly another decimal-shift error. Excluding both bulk rows and mismatch rows entirely, the top customer is `anita.singh@example.com` at \$36,855. See §3.
- **Who:** Whoever owns the exec/BI dashboard or customer-value report consuming this data.
- **Cost/risk:** Zero cost — it's a reporting-methodology change, not a data change. Risk of inaction: a stakeholder makes a customer-retention or forecasting decision based on a ranking that is an artifact of one or two rows, not customer behavior.
- **Falsified if:** The 6 bulk rows and the `ORD-1010`-type unflagged high-value rows are confirmed against source invoices as real, distinct, legitimate transactions (not duplicated or mis-keyed) — in which case the concentration is a genuine business fact (see R5) and should be reported as such, not excluded.

### R3 — Require both `units_sold` and `unit_price` to be captured at point of sale so every `total_revenue` value is cross-checkable
- **Do what:** Add a data-entry/API validation rule that rejects an order record missing either `units_sold` or `unit_price`, since `total_revenue` cannot be independently verified without both.
- **Why:** 36 of 266 rows (13.5%) have a non-null `total_revenue` but a null `revenue_calculated` (the cross-check field), because one of the two input fields is missing — meaning these 36 rows' revenue values are currently unauditable. Of these, one (`ORD-1010`: `units_sold`=39, `unit_price`=null, `total_revenue`=\$340,700) is 76x the 75th-percentile order value (\$4,488) with no plausible normal unit price to justify it (implied unit_price would be \$8,736, versus a normal range of roughly \$20–\$200) — it is very likely a decimal-shift error of the same kind flagged in R1, but the `revenue_mismatch_flag` logic could not catch it because it requires both fields present. The true count of revenue errors in this file is therefore probably higher than the 13 currently flagged.
- **Who:** Order-entry/checkout system owner (same team as R1, likely the same root cause).
- **Cost/risk:** Low — a form/API required-field validation. Risk of inaction: an unknown number of additional decimal-shift errors remain silently unflagged and unauditable in every future extract of this data.
- **Falsified if:** Manual review of `ORD-1010` and similar high-value, uncheckable rows against source records shows the value is correct (e.g., a genuinely large single-item order) rather than a scale error.

### R4 — Use `customer_email`, never `customer_name`, as the customer key for any customer-level cut
- **Do what:** Repoint any "distinct customers," "orders per customer," or "customer lifetime value" calculation to `customer_email`; treat `customer_name` as a display field only.
- **Why:** `customer_name` has 83 unique raw values across 266 rows, but `customer_email` has only 15 — meaning the same ~15 real people are represented under an average of 5.5 name variants each (case differences, titles like "Mr.", punctuation). Using `customer_name` for any grouping would fragment real customers into false "distinct" counts. This is also consistent with the pipeline log: 2 of the 31 pre-cleaning duplicate rows removed were the *same* `order_id` differing only in `customer_name` capitalization.
- **Who:** Whoever builds customer-level reporting or a CRM sync from this data; ideally the source system should also add a stable numeric `customer_id`, since even email is a soft key (email changes, shared family emails, etc.) not a guaranteed unique identifier.
- **Cost/risk:** Zero cost to switch the grouping key in existing reports. Risk of inaction: customer counts and per-customer value are silently wrong today.
- **Falsified if:** A source-system audit shows `customer_email` is not in fact stable per person (e.g., shared inboxes across different real customers) — unlikely given the 1:5.5 name-to-email ratio pattern here, but worth a source-system check before treating email as a permanent key.

### R5 — Get business sign-off on whether the 6 bulk orders are real before using them in any forecast
- **Do what:** Route the 6 `units_sold_outlier_flag` rows (`ORD-1223`, `ORD-1121`, `ORD-1279`, `ORD-1100`, `ORD-1119`, `ORD-1152`; units_sold 4,000–49,000 against a normal range of ~1–50) to sales ops / finance for invoice-level confirmation before they're used in any revenue forecast or bulk/wholesale-segment strategy.
- **Why:** These 6 rows are 2.3% of orders but 95.5% of total units and 80.5% of total revenue in this file — an extreme concentration that materially changes any headline number they touch (see R2). The pipeline's own decimal-typo-correction logic tested dividing them by 10/100/1000 and found the corrected values fit normal unit economics *worse* than leaving them alone (`03_clean_report.txt` §4.10: "repair rate 2.07% > 1% cap... reinterpreting them as a scale/segment finding"), so they were deliberately kept as real orders, not corrected as typos. That is a statistical judgment, not a business confirmation. One inconsistency worth a specific look: `ORD-1223` (4,000 units) is tagged `channel=B2C` — a 4,000-unit single order under a consumer/B2C label is unusual and worth checking against the other 5, which are tagged Wholesale/Brick & Mortar or have a missing channel.
- **Who:** Sales operations or finance, with access to the underlying invoices/contracts.
- **Cost/risk:** Low — a targeted 6-row invoice lookup. Risk of inaction: if even one of these 6 is a duplicate or data-entry error rather than a real bulk order, current revenue/volume concentration figures (and any forecast built on them) are substantially wrong.
- **Falsified if:** Invoice lookup confirms all 6 as legitimate, distinct wholesale contracts — at which point this becomes a genuine "concentration risk" finding for the business (heavy reliance on a handful of large accounts) rather than a data-quality question.

### R6 — Replace free-text region entry with a constrained dropdown
- **Do what:** Convert the `region` field at the point of capture from free text to a fixed 5-value dropdown (North/South/East/West/Northeast).
- **Why:** Raw region values before cleaning included entries like `'Nort'`, `'Sourh'`, `'Esat'`, `'north east'`, `'-'` (34 distinct raw strings collapsing to 5 canonical values — `02_profile_report.txt`). In the final `viz_ready.csv`, 22 of 266 rows (8.3%) still carry `region_fuzzy_review_flag = True`, meaning their region was assigned via fuzzy string match at only 70–84% confidence — lower-confidence than an auto-correct, i.e., a human should double check these before trusting a region cut. `product` and `channel` needed no such lower-confidence correction in the final file (0 fuzzy-review flags for both here), so this is specific to `region`'s input mechanism.
- **Who:** Order-entry/CRM UI owner.
- **Cost/risk:** Low (a standard UI dropdown change). Risk of inaction: continued need for fuzzy-match correction on every future load, with a non-zero misclassification rate at the 70-84% confidence band.
- **Falsified if:** Region is confirmed to already be a dropdown in the live system and free text only appears in this historical extract — in which case the fix is already in place and this is moot.

### R7 — Add calendar-date validation to the order-date picker
- **Do what:** Enforce real calendar-date validation (reject Feb 29 in a non-leap year, April 31st, etc.) at the point of order-date entry.
- **Why:** 8 of 266 rows in this file have `order_date_unparseable_flag = True` because the date string was genuinely invalid on the calendar in the source (5 instances of `29/02/2023` — 2023 is not a leap year — and 3 instances of `31/04/2024` — April has 30 days). These were deliberately left null rather than guessed. Combined with 11 further rows null for other reasons, 19/266 rows (7.1%) have no usable order date, which limits every time-series cut in §3.
- **Who:** Order-entry/checkout UI owner.
- **Cost/risk:** Low — standard date-picker validation. Risk of inaction: continued unusable rows in every time-series report.
- **Falsified if:** These dates originate from a free-text field or a legacy import rather than a live date picker — in which case the fix belongs on the import/ETL side, not the UI.

### R8 — Investigate the source of the 9.9% pre-cleaning duplicate rate
- **Do what:** Check the order-capture system for a double-submit or non-idempotent retry pattern.
- **Why:** 31 of 312 raw rows (9.9%) were removed as duplicates before any other cleaning — 29 exact full-row duplicates plus 2 rows sharing an `order_id` and differing only in `customer_name` capitalization (`03_clean_report.txt` §4.11). A near-10% duplicate rate at raw ingestion is high enough to suggest a systemic cause (e.g., a form re-submitted on a slow network, or a retry without an idempotency key) rather than isolated manual error.
- **Who:** Order-capture/API engineering.
- **Cost/risk:** Low to investigate. Risk of inaction: continued inflation of raw row counts and continued reliance on downstream dedup logic to catch it, which is not guaranteed to be exhaustive.
- **Falsified if:** The duplicates trace to a known, already-mitigated batch import issue (e.g., a one-time backfill re-run) rather than an ongoing capture bug.

---

## 3. Business findings

**All group-comparison tests below use a "clean" subset (n=247) that excludes `revenue_mismatch_flag` and `units_sold_outlier_flag` rows, because including them would let 6-19 extreme rows drive the result for any group they happen to fall in — this is stated per-test.**

### 3.1 Revenue does not differ significantly by region, product, or channel — all null
- **Region** (5 groups, clean subset, n=220 with non-null revenue): Kruskal-Wallis H=4.84, p=0.304; one-way ANOVA F=1.03, p=0.394, η²=0.024 (negligible effect size even ignoring the non-significance). **No evidence of regional revenue difference.**
- **Product** (4 groups, n=226): Kruskal-Wallis H=1.24, p=0.743. **No evidence of a revenue difference by product code.**
- **Fulfillment channel** — Retail/Wholesale/Online/Brick & Mortar (n=181 comparable rows carrying a fulfillment-type value; recall `channel` conflates fulfillment type and B2B/B2C segment as sibling values, treated separately here per the domain note): Kruskal-Wallis H=0.95, p=0.814. **No evidence of a revenue difference by fulfillment type.**
- **Segment B2B vs B2C** (n=26 B2B, n=11 B2C — small): Mann-Whitney U=110, p=0.280; Welch's t=-0.47, p=0.640. B2B mean \$2,916/median \$1,602; B2C mean \$3,268/median \$3,874. **No significant difference, and n=11 for B2C gives this test very little power — do not treat this as evidence of equivalence, just as "not detected here."**

These are four independent null results. Read together, they say: within this file, revenue per order does not depend measurably on where the order was placed, which of the 4 products it was for, or how it was fulfilled or segmented. That is a real, useful finding — it means any "region X underperforms" or "B2C orders are worth more" narrative someone might pitch from a glance at this data is not supported.

### 3.2 Order volume (not revenue) does vary by product and by fulfillment channel — real but modest effects
- **Product mix is not uniform**: chi-square goodness-of-fit vs. equal shares, χ²=27.63, df=3, p<0.0001, Cramér's V=0.20 (small-to-moderate). Alpha is ordered most (87/266 rows with a product value, 32.7% of the 226 non-null), Delta least (35, 15.5%); Beta 44 (19.5%), Gamma 60 (26.5%).
- **Fulfillment-type mix is not uniform**: χ²=41.52, df=3, p<0.0001, Cramér's V=0.28 (moderate). Online dominates (76/181, 42.0%), Brick & Mortar is rare (15/181, 8.3%); Retail 48 (26.5%), Wholesale 42 (23.2%).
- **Segment mix (B2B vs B2C)**: χ²=5.33, df=1, p=0.021, Cramér's V=0.33 — but on only n=48 rows carrying a segment value, so treat this as suggestive, not conclusive: B2B (32) outnumbers B2C (16) 2:1.
- **Region mix is uniform**: χ²=6.23, df=4, p=0.183 — no evidence orders skew toward any one region.
- Since §3.1 found revenue-per-order does not differ by product or channel, these volume-mix findings are about **order frequency, not order value** — e.g., Alpha and Online generate more orders, not bigger ones.

### 3.3 Six orders account for 80.5% of revenue and 95.5% of units — extreme concentration
Computed directly on `viz_ready.csv`: total `total_revenue` across all 266 rows = \$14,729,126; the 6 `units_sold_outlier_flag` rows alone sum to \$11,857,570 (80.5%). Total `units_sold` = 144,466; the same 6 rows sum to 138,000 units (95.5%). This is the single largest number in the dataset and drives most of the AOV instability discussed in R2. See R5 for the recommended next step — this cannot be resolved from the data alone; it needs invoice confirmation.

### 3.4 Average order value is not a stable number in this file — report median, or segment first
Mean `total_revenue`: \$63,215 (n=233, all comparable rows) → \$58,246 excluding the 13 `revenue_mismatch_flag` rows (-7.9%) → \$12,595 excluding the 6 `units_sold_outlier_flag` rows only → \$4,449 excluding both (-93% from the starting mean). Median across the same four cuts: \$2,493 → \$2,444 → \$2,414 → \$2,397 (moves less than 4% total). This is a textbook case of a mean being dominated by a handful of rows while the median is robust — see R2.

### 3.5 `unit_price` and `units_sold` are uncorrelated — no evidence of volume discounting or premium-pricing behavior
Pearson r=-0.007, p=0.920 (clean subset, n=208); Spearman ρ=-0.005, p=0.941. On the full data including bulk-outlier rows, r=-0.016, p=0.810. **Null result, reported as a finding**: there is no detectable relationship between the price charged per unit and the quantity ordered, in either direction. This also means any per-unit-economics narrative ("bulk buyers get better/worse pricing") is not supported here.

### 3.6 `region` and `product` are independent
Chi-square test of independence on the 5×4 region-by-product crosstab (clean subset): χ²=10.53, df=12, p=0.570, Cramér's V=0.14. No evidence that product choice varies by region.

### 3.7 `unit_price` distribution is symmetric except for one confirmed outlier
Including the single `unit_price_outlier_flag` row (value \$3,047, roughly 29x the median), skewness = 13.95 and a Shapiro-Wilk test strongly rejects normality (W=0.193, p<1e-6) — but excluding that one row, skewness drops to 0.055 (essentially symmetric) with mean \$107.89/median \$104.97 (n=240). This confirms the pipeline's decision to leave that row flagged-but-uncorrected was reasonable — it is a genuine, isolated outlier, not evidence the whole column is skewed. Any "average unit price" figure should exclude or separately report that one row.

### 3.8 No statistically significant monthly seasonality, with one important negative check
Order counts per month (247 rows with a usable date, spanning Jan–Dec 2024) range from 14 (May, December) to 33 (July). A chi-square goodness-of-fit test against equal probability per month gives χ²=17.44, df=11, p=0.096 — not significant at α=0.05. Re-running the test with expected counts weighted by days-per-month (accounting for Feb 2024 being a leap-year 29 days and the varying month lengths) gives χ²=17.86, df=11, p=0.085 — same conclusion, still not significant. **Per the known "manufactured December spike" failure mode**: the data does *not* end mid-month — the latest order date is 2024-12-30 and December's 14 orders are spread across dates 3rd through 30th, not clustered at the start of the month — so December's low count is not a truncation artifact, it's just a low-order month within noise. **No seasonality is claimed here; this is a genuine null result**, and with only 12 months of data the test has limited power to detect a real seasonal effect if one exists — more time periods would be needed to resolve this either way.

### 3.9 Customer identity: `customer_name` is not a usable key (see R4)
83 unique raw `customer_name` values map to only 15 unique `customer_email` values (average 5.5 name variants per real customer, e.g., "ARJUN MEHTA" / "arjun mehta" / "Mr. Arjun Mehta"). Any customer-level cut must use `customer_email`.

---

## 4. Operational findings — what the cleaning log says about the source systems

| Finding | Rows | What it implies |
|---|---|---|
| `total_revenue` disagrees with `units_sold * unit_price` by a clean 100x/50x/10x/0.1x/0.01x scalar | 13 / 233 comparable rows (6.44% in cleaned_data.csv, 13 survive to viz_ready.csv) | Systematic decimal-shift or currency-scale bug in whichever system independently populates `total_revenue` — not manual entry noise (see R1). Neither field was corrected; both retained for downstream judgment. |
| `total_revenue` present but not cross-checkable (`units_sold` or `unit_price` missing) | 36 / 266 (13.5%) | The revenue error rate above is a *floor*, not the true rate — one of these 36 (`ORD-1010`, \$340,700) is a near-certain additional undetected decimal-shift error (see R3). |
| `units_sold` in the thousands (4,000–49,000) vs. a normal 1–50 range | 6 / 266 (2.3%) | Pipeline's own decimal-typo correction was tested and explicitly rejected (correcting worsened the unit-economics fit) — left as a real bulk-order segment, not a typo. This segment is 95.5% of units and 80.5% of revenue (§3.3) — needs business confirmation, not further cleaning (R5). |
| `units_sold` has a fractional value ending in exactly `.5` | 6 / 266 (2.3%) | All six are X.5 exactly (36.5, 41.5, 42.5, 46.5, 48.5, 49.5) — a suspiciously uniform pattern suggesting a systematic cause (e.g., two half-case units summed, or an averaging formula copied into a quantity field) rather than random data entry, though this is a hypothesis, not confirmed from the data alone. |
| `unit_price` statistical outlier (\$3,047 vs. median \$105.47) | 1 / 266 | Tested against decimal-typo correction and found no clean match — left flagged, uncorrected. Confirmed as a genuine isolated outlier in §3.7. |
| `order_date` unparseable — genuinely invalid calendar dates in source | 8 / 266 (3.0%) (5x `29/02/2023`, 3x `31/04/2024`) | UI/import allows selecting or entering calendar-impossible dates — needs date-picker validation, not a smarter parser (R7). |
| `order_date` null overall (unparseable + other causes) | 19 / 266 (7.1%) | Limits every time-series cut in §3.8 to 247 usable rows. |
| `region` corrected via fuzzy match at 70-84% confidence (below the 85% auto-correct bar) | 22 / 266 (8.3%) | Region field accepts free text with real typo variety (raw data included "Nort", "Sourh", "Esat" — `02_profile_report.txt`); needs a dropdown (R6). `product` and `channel` needed 0 such low-confidence corrections in this final file. |
| `customer_email` repaired (format issue auto-fixed) | 10 / 266 (3.8%) | Modest contact-data quality issue at intake; as-received email validity was 96.14% (299/311) before repair, 100% after. |
| `phone_number` country code unknown/inferred | 1 / 266 flagged unknown; 168/294 normalized numbers had country code *inferred* rather than stated | Most phone numbers arrive without an explicit country code and are inferred from a 10-digit Indian-mobile pattern — a reasonable but non-verifiable assumption; contact data, not a sales-value concern. |
| Raw duplicate rows removed before cleaning | 31 / 312 (9.9%) — 29 exact, 2 same-`order_id`-differing-only-in-name-capitalization | A near-10% duplicate rate at ingestion suggests a systemic double-submit or non-idempotent retry issue upstream, not isolated error (R8). |
| Physically impossible negative values (excluded from viz_ready.csv, this file) | 15 / 281 (5.34%) in `units_sold`/`unit_price`/`total_revenue` | Excluded from every statistic above per this file's stated construction. The pipeline log (`03_clean_report.txt` §4.9) shows negatives appear independently across all three fields (5/8/14 respectively before viz_ready filtering) — consistent with a sign-flip bug (e.g., refunds recorded as negative sales in the same field) rather than isolated typos; worth its own investigation if this file is regenerated, though it is out of scope for a report built on the already-filtered viz_ready.csv. |

---

## 5. What we cannot say

- **Whether region/product/channel truly have no revenue effect, or whether n=266 (and per-group subsets as small as n=11 for B2C) is simply underpowered to detect a real but modest effect.** All tests in §3.1 are honest nulls given the data in hand, but they are not proof of equivalence. A larger sample, or the same analysis repeated on a full year-over-year extract, would sharpen this.
- **Whether the 6 bulk orders (§3.3) are legitimate wholesale transactions or a data/duplication bug.** The pipeline's own decimal-typo test found no clean correction and left them as a "real segment" judgment call — that is a statistical inference, not a confirmed business fact. Only invoice-level lookup (R5) can resolve this, and until it is, no revenue forecast should be built on these 6 rows.
- **Which of `total_revenue` or `revenue_calculated` (`units_sold * unit_price`) is correct for the 13 flagged mismatch rows**, or for the ~36 rows that cannot be cross-checked at all (R3). The pipeline deliberately did not guess (Business Rule BR1) — resolving this requires the source system of record, not further analysis of this file.
- **True seasonality.** 247 dated rows over 12 months (~20/month) gives limited statistical power; the current data neither confirms nor rules out a real seasonal pattern (§3.8, p=0.085–0.096, borderline non-significant either way).
- **Whether this dataset reflects real production behavior or is a synthetic/test extract.** All 291/312 raw customer emails share the domain `example.com` (`02_profile_report.txt`), and every group-comparison test in §3.1 came back null. That combination — uniformly synthetic-looking email domains plus a run of clean nulls across every cross-cut — is itself worth naming plainly: it is consistent with (though not proof of) generated or sampled test data rather than a live sales ledger. If this file is meant to represent real customer behavior, that should be confirmed before any of §2's business-facing recommendations (R2, R4, R5) are acted on for an actual go-to-market decision; the operational/data-quality recommendations (R1, R3, R6–R8) stand regardless of provenance, since they describe pipeline and form-validation behavior, not customer behavior.
- **The root cause behind the X.5 non-integer `units_sold` values and the sign-flipped negative rows.** Both are named as plausible hypotheses in §4, not confirmed diagnoses — they need a source-system walkthrough to verify.

---

*Report generated from `viz_ready.csv`, `change_log.csv`, `03_clean_report.txt`, `05_viz_ready_report.txt`, `02_profile_report.txt`, and `validation_report.md` in `case_studies/sales\`. All statistics computed with pandas/scipy; no figures were estimated or eyeballed.*
