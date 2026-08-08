# Real-Estate Listings — Insights Report

**Stage 9 scope: General EDA — auto-selected (unattended run).** No user was available to name specific KPIs, so this is a broad exploratory pass over `viz_ready.csv` (48,870 rows × 60 columns), covering price distributions, the effect of property characteristics on price, macro-index relationships, and time trends, plus what the cleaning-pipeline logs imply about the source system.

Dataset analysed: `viz_ready.csv` (48,870 rows). Per the pipeline instructions, `cleaned_data.csv` (49,864 rows) was **not** used because it still carries 994 rows with physically-impossible negative `total_area` that were deliberately excluded from this filtered view.

---

## 1. The headline

**Country is the only property characteristic in this dataset that reliably moves price** — it explains roughly a third of the variance in log price (partial η²=0.37, p<0.001, n=48,870), while property type, condition, property age, HOA fee, property tax, and three of four macro indices show no real effect once you actually test them, despite one of them (`property_type`) clearing p<0.05 on a sign-eyeball basis. Anyone building a pricing model or a "what drives price" dashboard should segment on country (and physical size/room count) and stop treating property type or condition as price levers here. Separately, three pipeline-level issues need attention before this dataset is trusted for anything geographic or currency-based: **latitude/longitude are not tied to real country geography** (about half of Australia's listings show a positive/northern-hemisphere latitude, and about half of India's show negative/southern-hemisphere latitude — both physically impossible for those countries), **the `currency` symbol carries no actual price-scale information** (₹, $, €, £, and AED–labelled prices are statistically indistinguishable in magnitude, which would never happen with real FX rates), and **published mean prices by segment are inflated 10–27% by fewer than 1% of rows** (the 424 `final_sale_price_outlier_flag` listings) — use medians for any headline number.

---

## 2. Recommendations

### R1 — Segment and model price by country and physical size/room count, not by property type or condition
- **Do what:** In any pricing model, dashboard filter set, or "what drives price" narrative, prioritize `country`, `total_area`/`log(total_area)`, `bedrooms`, and `bathrooms` as the explanatory variables. Do not build a "price by property type" or "price by condition" story — the data does not support one.
- **Why:** Multivariate OLS on `log(final_sale_price)` with country, property_type, condition, currency, log(area), bedrooms, bathrooms, and property age (§3.1) gives partial η² of 0.370 for country vs. 0.00014 for property_type and 0.00012 for condition (p=0.33 and p=0.32 respectively, once other factors are controlled). Univariately, `property_type` does clear p=0.0197 (ANOVA) / p=0.011 (Kruskal-Wallis, n=48,870) — but its effect size (η²=0.00031) means it explains about 0.03% of price variance. This is the textbook case of a huge sample detecting a difference that is not practically real. `condition` is fully null even univariately (Kruskal H=1.09, p=0.955).
- **Who:** Whoever owns the pricing/valuation model or the "price drivers" analytics dashboard.
- **Cost / risk:** Low cost — this is a feature-selection decision, not new data collection. Risk of following the recommendation: if property_type genuinely matters in a way this cross-section can't see (e.g., an interaction effect), it would be under-weighted. That's why the effect sizes above were computed, not assumed.
- **Falsified if:** A re-run on a larger or updated sample finds property_type's partial η² is an order of magnitude higher (>0.01) with a coefficient pattern that survives multiple-testing correction, or a country×property_type interaction term becomes significant with non-trivial effect size (an interaction test was not run in this pass — see §5).

### R2 — Report median price per segment, or explicitly caveat the mean, in any dashboard card
- **Do what:** Any "average price by country/type/condition" metric card should show median, or show both with a footnote naming the outlier count.
- **Why:** Excluding the 424 rows flagged `final_sale_price_outlier_flag` (0.87% of the dataset) drops the country-level **mean** final_sale_price by 10.1% (India) to 27.5% (France); the **median** moves by well under 1% in every country (§3.4). These rows were investigated by the cleaning stage and are genuine luxury listings, not typos (cross-checked final_sale_price/listing_price ratio matches the normal population's band for 98% of them) — so they should stay in the data, but a mean-based headline number will silently swing with how many of them land in a given cut.
- **Who:** BI/dashboard owner publishing country- or segment-level price summaries.
- **Cost / risk:** Negligible — swap the aggregation function or add a second line. Risk if ignored: a 20%+ "price jump" in a country gets reported as a market signal when it's a handful of luxury listings.
- **Falsified if:** A segment cut is found where excluding these rows moves the median by a magnitude comparable to the mean (it isn't, in any of the 10 countries checked here).

### R3 — Do not build map/geospatial visuals from `latitude`/`longitude` until the source system is fixed
- **Do what:** Pull any planned map, choropleth, or geo-clustering feature off the roadmap for this dataset; treat lat/long as unusable until re-sourced.
- **Why:** Latitude/longitude ranges are essentially identical across all 10 countries (every country spans roughly -60° to +60° latitude, -150° to +150° longitude, mean near 0 for all). Directly: 2,427 of Australia's 4,861 listings (50%) show a **positive** (northern-hemisphere) latitude, and 2,539 of India's 4,959 listings (51%) show a **negative** (southern-hemisphere) latitude — both are physically impossible for those countries in reality. Coordinates are not derived from country/city; they look independently randomly generated.
- **Who:** Whoever owns the map widget/geo feature, and the upstream listings-source system or data vendor (this is likely a schema/generation defect, not a cleaning-stage miss — there's nothing to "fix" downstream of the raw feed).
- **Cost / risk:** Cost of following this recommendation is zero (you're not building something broken). Risk of ignoring it: any published map is actively wrong, not just imprecise — a stakeholder could infer city-level location patterns that don't exist.
- **Falsified if:** the raw source system confirms lat/long are populated by a legitimate process this analysis isn't accounting for (e.g., anonymization jitter within real bounds) — worth a direct question to the source-system owner before assuming defect, since it wasn't possible to verify against the raw un-cleaned feed here.

### R4 — Treat the `currency` field as unreliable for any FX or "which market is priciest" analysis; confirm intent with the source system owner
- **Do what:** Do not build any report comparing "average listing price in ₹ markets vs $ markets," and do not treat `currency` as informative for cross-country price comparison. If a currency-aware view is needed, ask the source system whether `currency` is meant to reflect real transaction currency at all.
- **Why:** `currency` (5 symbols: $, AED, £, €, ₹) shows no relationship to price magnitude — Kruskal-Wallis on final_sale_price by currency: H=3.18, p=0.53; ANOVA on log price: F=0.97, p=0.42, η²=0.00008 (n=48,870). Median final_sale_price by currency ranges only from 1,354,423 (£) to 1,373,184 (€) — under 1.5% spread. A real ₹-denominated price for an equivalent property should be numerically ~80-90x a real $-denominated one; it is not, here. This corroborates the cleaning stage's prior finding that `currency` is statistically independent of `country` (χ²=44.32, p=0.16, on the full 50k raw rows) — together these two nulls indicate `currency` is very likely a decorative/synthetic label, not a real transactional attribute, in this dataset.
- **Who:** Data engineering / source-system owner for the listings feed.
- **Cost / risk:** Potentially high if a real fix requires backfilling true FX-scaled historical values; low if the answer is simply "don't build currency-based cuts." Risk of ignoring: a "cheapest currency market" report gets published and is meaningless.
- **Falsified if:** the vendor/source confirms `currency` is populated correctly and prices genuinely are not FX-adjusted by design (e.g., listings are entered in a normalized reporting unit regardless of local currency) — in which case this is expected behavior, not a defect, and R4 should be downgraded to a documentation note rather than a fix request.

### R5 — Before publishing any $/bedroom or $/bathroom heuristic, resolve why bedrooms, bathrooms, and total_area are uncorrelated — and why "Land" listings carry bedroom/bathroom counts at all
- **Do what:** Hold off on any per-bedroom or per-bathroom pricing heuristic (common in real-estate reporting, e.g. "$/bedroom by city") until the source of `bedrooms`/`bathrooms`/`total_area` is understood. Specifically ask the source-system owner why `property_type == 'Land'` rows have a median of 5 bedrooms and 4 bathrooms (matching every other property type almost exactly).
- **Why:** `total_area` vs. `bedrooms`: r=-0.0016, p=0.72. `total_area` vs. `bathrooms`: r=0.0054, p=0.23. `bedrooms` vs. `bathrooms`: r=0.0050, p=0.27 (n=48,870, all null). In real listings these are structurally linked (more bedrooms needs more area); here they are statistically independent, and bedroom/bathroom counts for `Land` parcels (median 5 bed / 4 bath, essentially identical to Apartment's median 6 bed / 4 bath) are not conceptually meaningful for vacant land. This is consistent with §4's broader finding that most non-country fields in this dataset behave like independently generated noise.
- **Who:** Source-system/data-generation owner; secondarily, whoever would build a per-bedroom pricing view.
- **Cost / risk:** Low cost to hold off; risk of publishing anyway is a heuristic that means nothing for ~14% of listings (the `Land` and `Studio` types) and is only coincidentally plausible-looking for the rest.
- **Falsified if:** source confirms bedroom/bathroom fields for `Land` represent something legitimate (e.g., permitted/buildable unit counts) rather than a copy-paste of the same generation logic used for habitable property types.

### R6 — Keep `luxury_demand_index` in any pricing model; drop `interest_rate`, `inflation_index`, and `housing_index`
- **Do what:** If a price-prediction or elasticity model is built from this data, include `luxury_demand_index` as a feature and exclude the other three macro indices.
- **Why:** `luxury_demand_index` correlates with log price at r=0.383 (p<0.001, r²=0.146, n=48,870) — a real, moderate signal. `interest_rate` (r=0.008, p=0.063), `inflation_index` (r=-0.0007, p=0.885), and `housing_index` (r=0.006, p=0.191) all show no relationship to log price at this sample size. This re-confirms, on the viz_ready subset specifically (rather than assuming it carries over from the prior 50k-row check), that three of the four macro indices behave like noise here.
- **Who:** Whoever builds the next pricing/elasticity model.
- **Cost / risk:** None — this only removes non-predictive features.
- **Falsified if:** a non-linear or interaction-based re-test (not performed in this linear/rank pass) finds a real relationship for any of the three — e.g., if `interest_rate` matters only in combination with country or listing year.

---

## 3. Business findings

### 3.1 What actually drives price (multivariate OLS on log(final_sale_price), n=48,870, R²=0.507)

| Factor | Partial η² | p-value | Verdict |
|---|---|---|---|
| `country` | 0.370 | <0.001 | **Dominant driver** |
| `bedrooms` | 0.196 | <0.001 | Real, meaningful |
| `log(total_area)` | 0.117 | <0.001 | Real, meaningful |
| `bathrooms` | 0.058 | <0.001 | Real, meaningful |
| `property_age_years` | 0.00007 | 0.060 | Null |
| `currency` | 0.00009 | 0.363 | Null (see R4) |
| `condition` | 0.00012 | 0.316 | Null |
| `property_type` | 0.00014 | 0.333 | Null (multivariate); marginal-but-negligible univariate (see R1) |

Country's effect holds up when restricted to a single property type (checked on `Apartment` only, n=6,934): median price still ranges from 649,341 (India) to 2,101,044 (UAE), the same rank order as the full-sample country medians (634,639 to 2,092,839) — so this is not a property-type-mix artifact. `price_per_sqm` follows the identical country ranking (India lowest at 2,950/sqm, UAE highest at 9,802/sqm), a consistency check that the country effect is a real, area-normalized price-level difference and not just driven by larger properties in some countries.

### 3.2 Macro indices: only one has signal (re-tested on viz_ready, not assumed from prior run)

- `luxury_demand_index` vs. log price: r=0.383, p<0.001, r²=0.146 — real.
- `interest_rate` vs. price: r=0.005 (Pearson on raw price), p=0.31; vs. log price r=0.008, p=0.063 — null.
- `inflation_index` vs. price: r=-0.004, p=0.37 — null.
- `housing_index` vs. price: r=0.003, p=0.58 — null.

This confirms, rather than assumes, the prior finding on this specific 48,870-row subset. Anyone building a model should not spend effort on interest rate/inflation/housing index features (R6).

### 3.3 Physical size matters, but less than expected for real estate — and is uncorrelated with room counts

`log(total_area)` vs. `log(final_sale_price)`: r=0.252, p<0.001, r²=0.063 — a real but modest relationship (in typical real housing markets, floor area alone often explains 30-50%+ of price variance; here it explains about 6%). This is consistent with §3.1's finding that bedrooms (η²=0.196) and bathrooms (η²=0.058) each carry more explanatory weight than area size in the multivariate model — an unusual pattern for real estate, and one explained by §4's finding that `total_area`, `bedrooms`, and `bathrooms` are statistically independent of one another (r≈0.001–0.005, all p>0.2) rather than structurally linked as they would be in genuine listings. `property_age_years` shows no relationship to price at all (r=0.0006, p=0.90).

### 3.4 Outlier-flagged rows pull segment means well beyond their row-share, medians barely move

`final_sale_price_outlier_flag` (424 rows, 0.87% of viz_ready) rows are spread roughly evenly across countries (18-57 rows/country, in proportion to each country's ~4,800-4,970 total). Comparing each country's mean/median final_sale_price with vs. without these rows:

| Country | Mean, % pulled by outlier rows | Median, % pulled |
|---|---|---|
| France | +27.5% | <0.7% |
| Canada | +24.5% | <0.5% |
| USA | +24.8% | <0.5% |
| UAE | +20.4% | <0.5% |
| UK | +20.1% | <0.4% |
| Australia | +19.3% | <0.4% |
| Spain | +16.4% | <0.2% |
| Germany | +14.9% | <0.5% |
| Brazil | +17.6% | <0.2% |
| India | +10.1% | <0.1% |

These rows were cross-checked by the cleaning stage against `listing_price` (ratio matches the normal population's band for 98% of them) and are treated as genuine luxury listings, correctly kept in the data — but any mean-based headline should be read knowing <1% of rows can move it double-digit percentage points. See R2.

### 3.5 Price-to-listing ratio is tight and near 1 everywhere — likely a generation bound, not negotiation behavior

`price_to_listing_ratio` (=final_sale_price/listing_price): mean=1.0039, median=1.0005, range [0.9091, 1.1111], std=0.058 across the whole dataset. By country, medians range only 0.9976 (India) to 1.0021 (Australia) — Kruskal-Wallis H=17.19, p=0.046 (borderline significant at n=48,870, but the practical spread is under half a percentage point). `days_on_market` and `price_revision_count` show no relationship to this ratio (r=-0.0003, p=0.95 and r=0.0045, p=0.32 respectively) — negotiation dynamics that would normally show up here (properties on market longer selling further below ask, or heavily revised listings closing at different ratios) are absent. Combined with the suspiciously symmetric bounds (0.9091 = 1/1.1, 1.1111 = 10/9), this reads as a synthetic generation cap rather than a real negotiation signal — **no business recommendation is supported by price-to-listing ratio**; it should not be used as a "deal quality" metric on this data.

---

## 4. Operational findings (from the pipeline / cleaning log)

- **994 rows with negative `total_area`** were flagged (`total_area_sign_flag`, not corrected — a sign flip on a physically impossible value shouldn't be guessed at) and excluded from this filtered view per instructions; they remain in `cleaned_data.csv` for audit. This is a genuine upstream defect (an area value should never parse as negative) — whatever writes `total_area` upstream needs a non-negative constraint.
- **Latitude/longitude are not tied to country geography** (§ R3) — roughly half of Australia's rows show impossible positive latitude, roughly half of India's show impossible negative latitude. This should be raised with the source system directly; it is not something this cleaning pipeline can fix without a real coordinate source.
- **`currency` carries no real price-scale information** and is statistically independent of `country` (χ²=44.32, p=0.16 on the raw 50k rows, re-confirmed here to also carry no price-magnitude signal: Kruskal-Wallis p=0.53). Together these make `currency` look like a randomly-assigned label rather than a captured transactional attribute (§ R4).
- **City encoding defects, already fixed:** 2,641 rows had `city` values corrected via an explicit alias map — 2,640 were "Sao Paulo" → "São Paulo" (missing diacritic) and 1 was "Munich" → "München" (non-localized spelling). This was handled via an explicit map rather than fuzzy matching, appropriately — `token_sort_ratio('Munich','München')=61.5` is too low to trust a fuzzy matcher not to also merge unrelated city pairs. No further action needed; noted here only so the "why 2,641 corrections" question doesn't get re-asked.
- **1,004 → corrected count 996 negative-flagged / 994 surviving `total_area` rows, 4,848–4,960 `total_area_outlier_flag`, 1,573–1,577 `price_per_sqm_outlier_flag`, 424–426 `final_sale_price`/`listing_price_outlier_flag` rows** were all investigated and kept, not dropped, per the flag registry (`total_area_outlier_flag` verified stable across every property type in this check too: 9.6%-10.3% of every property_type carries the flag, confirming it's genuine scale variation, not a property-type-specific defect). `price_per_sqm_outlier_flag` is confirmed mathematically explained by small `total_area` denominators, not an independent signal — consistent with the cleaning stage's note not to double-count it.
- **`condition` category near-duplication:** "New" carries 14,124 rows vs. ~6,900-7,000 for every other condition value, because a case-fold merge (`'new'` → `'New'`) combined two case-duplicate categories (7,239 rows) during cleaning. This is already handled correctly (Title Case canonicalization) and is the expected, documented state — flagged here only so a downstream analyst doesn't mistake the 2x count for a genuine "New is twice as common" business finding.
- **`bedrooms`/`bathrooms`/`total_area` are mutually independent** (§3.3/§4, r≈0.001-0.005, all p>0.2) and `Land`-type listings carry median bedroom/bathroom counts nearly identical to habitable property types — this looks like a data-generation artifact (fields sampled independently rather than jointly) rather than a cleaning-stage issue, and is worth raising with whoever owns the source data generation process (R5).
- **HOA fee and property tax show no relationship to price** (r=0.003, p=0.54 and r=-0.001, p=0.79 respectively) — in real listings these typically scale with property value; their independence here is another marker consistent with §4's overall pattern of independently-generated fields.

---

## 5. What we cannot say

- **Whether property_type or condition matters within a specific country** — only the pooled multivariate and univariate tests were run; a country×property_type interaction term was not fit. It's possible property type matters in, say, UAE specifically and washes out in the pool. Would need: an interaction-term regression or per-country ANOVA with a multiple-testing correction (10 countries × 7 types shrinks per-cell sample size fast — worth checking power before trusting a per-country result).
- **Why country drives price so strongly** — this dataset cannot distinguish "these are genuinely different, realistic national price levels" from "the generation process assigned a per-country price multiplier." The price-per-sqm ranking is internally consistent (§3.1) but that consistency is equally explainable by either story. No external market benchmark was available in this pipeline to check UAE/India/Brazil price levels against real-world listings data.
- **Whether latitude/longitude are salvageable at the city level even though they fail at the country level** — not checked; would require comparing each `city`'s coordinate spread against that city's real-world bounding box, which needs an external city-coordinate reference table not present in this pipeline.
- **What real value `currency` should have carried** — cannot reconstruct true FX-scaled prices from this file; would need the true transaction currency and a historical FX rate table joined by `listing_date`.
- **Whether the apparent overall synthetic/independent-feature pattern (§3.3, §4) extends to columns not tested here** (e.g., `title`/`description` text, `district`) — those were only spot-checked for parseability and PII, not statistically tested for independence from other fields.
- **Causal direction for `luxury_demand_index`** — the one macro index with real signal (r=0.383) is correlational only; whether it's a leading indicator, a coincident index, or partly *derived from* price in the source system was not established here and would need the index's construction methodology.

---

*Every count and statistic above traces to `viz_ready.csv` (n=48,870 unless otherwise noted), `change_log.csv`, `_flag_registry.json`, and `validation_report.md` in the same directory. Tests used: Pearson/Spearman correlation, one-way ANOVA with η², Kruskal-Wallis, and a multivariate OLS with Type-II ANOVA partial η² — see script outputs referenced throughout.*
