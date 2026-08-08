# Logistics Shipment Analytics — Insights & Recommendations

**Scope note:** This is an unattended pipeline run. No stakeholder was available to pick a focus
area, so the operator auto-selected **General EDA** as the scope. Findings below cover delivery
performance, cost/profitability structure, regional/warehouse patterns, returns, and customer
rating — plus everything the cleaning log reveals about the systems that produced this data.

**Source:** `viz_ready.csv`, 29,354 rows x 84 columns, one row = one shipment (`Order_ID` is
explicitly not the grain — orders legitimately split into multiple shipments). The 646
physically-impossible rows (delivery date before dispatch date) are already removed from this
file. All numbers below were computed with pandas/scipy against this file; none are eyeballed.

---

## 1. The headline

Delivery performance and profitability are driven by two different levers, and they should not
be managed together. **Profitability is a product-category problem** (profit margin varies from
‑2.1% to +59.1% across categories, ANOVA η²=0.594 — a huge effect), not a transport-mode problem
(mode has essentially zero effect on margin, η²=0.0000, p=0.75). **On-time delivery is a
transport-mode and warehouse problem** (Road shipments are on time only 54.4% of the time vs
81.4% for Air, and the four worst warehouses run 20+ points behind the four best). The single
highest-value action available from this data: fix Road/warehouse dispatch reliability (Road is
55% of all shipment volume and its worst-performing lever) and put Books & Stationery pricing
under review (it is the only category losing money on the typical shipment and only breaks even
in aggregate). A large share of the standard cost/weight/volume/revenue aggregates in this
dataset carry a real data-quality caveat — see §4 — and should be read with that in mind before
they go on an executive dashboard.

---

## 2. Recommendations

### R1 — Put Books & Stationery pricing under review; it is the only structurally unprofitable category
- **Do what:** Route Books & Stationery to whoever owns category pricing/contracts for a margin
  review — check freight contract terms, discounting rules, and whether it is an intentional
  loss-leader.
- **Why:** Profit margin differs enormously by product category (one-way ANOVA, F=4299.9,
  p<0.001, η²=0.594 — a very large effect, §3.3). Books & Stationery averages **‑2.13% profit
  margin** (n=2,349), the only category with a negative mean, and **51.7% of its individual
  shipments lose money** vs 11.83% company-wide. The result survives excluding the
  outlier-flagged cost/revenue rows (margin recomputed at ‑2.15% on n=2,343, §4) — this is not a
  cleaning artifact. In aggregate the category is barely profitable (₹223,314 total profit on
  ₹16.0M revenue, ~₹95/shipment mean) — it produces 8.0% of shipment volume but 0.095% of
  company-wide profit (₹235.7M total).
- **Who:** Category/pricing manager for Books & Stationery; finance for margin sign-off.
- **Cost / risk:** A pricing review is low-cost (analyst time). Risk of acting wrong: this could
  be an intentional loss-leader or cross-subsidized category — do not reprice without checking
  contract terms first, or you may lose volume without understanding why it was priced this way.
- **Falsified if:** A category-level cost/contract audit shows the negative margin is by design
  (e.g., a loss-leader agreement with a bundled customer), not a pricing or cost-allocation error.

### R2 — Investigate Road transport reliability: worst on-time rate, largest volume, dominated by traffic/breakdown delays
- **Do what:** Commission a dispatch-ops review of Road shipments focused on route planning
  (traffic) and fleet maintenance (breakdowns), the two largest named delay causes.
- **Why:** Road has the lowest on-time rate of any mode: **54.4%** vs Air 81.4%, Sea 70.2%, Rail
  64.1% (χ²=1694.9, p<0.001, Cramér's V=0.139 — small-to-moderate effect, §3.2). Road carries
  55.2% of all 29,354 shipments, so this is the single largest reliability lever in the network.
  Among the 6,034 delayed Road shipments, Traffic Congestion (30.3%) and Vehicle Breakdown
  (14.6%) together account for 44.9% of named reasons (§3.6).
- **Who:** Road fleet operations / regional logistics manager.
- **Cost / risk:** Route-optimization tooling and a preventive-maintenance program have real
  cost; risk if wrong is spending on the wrong lever. **Important caveat:** `delay_reason`
  categories are mode-exclusive by construction in this dataset — e.g. "Traffic Congestion,"
  "Vehicle Breakdown," "Recipient Unavailable," and "Address Issue" occur *only* on Road rows,
  never on Air/Rail/Sea (§4). That pattern is consistent with the reason field being assigned
  deterministically by mode at data-generation/entry time rather than independently logged per
  incident, so treat the specific reason breakdown as a hypothesis, not a confirmed root cause,
  until checked against real dispatch/telemetry logs.
- **Falsified if:** Real dispatch or GPS telemetry records show Traffic Congestion / Vehicle
  Breakdown incidence does not track the 30.3%/14.6% split reported here, or shows the reason
  field is populated from a fixed lookup table by mode rather than incident-level observation.

### R3 — Audit dispatch process at the four worst-performing warehouses (WH011, WH010, WH004, WH009)
- **Do what:** Run an operational audit (pick/pack/dispatch timing, staffing, dock scheduling) at
  WH011, WH010, WH004, WH009 — all under 53% on-time — and compare their process against WH001,
  WH005, WH003 (68–70% on-time).
- **Why:** On-time rate ranges from 49.3% (WH011) to 70.3% (WH001) across the 12 warehouses
  (χ²=929.2, p<0.001, Cramér's V=0.103, §3.5). This is not explained by an obvious confound: each
  warehouse ships a near-identical transport-mode mix (Road ≈52–59%, Air ≈17–24%, Rail ≈21–24%,
  Sea 0–5% at every warehouse), and mean shipping distance per warehouse does not correlate with
  its on-time rate (r=0.07, p=0.83, n=12 — underpowered but shows no pattern). That rules out the
  two most obvious "it's just their route mix" explanations.
- **Who:** Warehouse operations directors for the four named sites; network ops for the
  cross-warehouse comparison.
- **Cost / risk:** Audit cost is analyst/ops-manager time; low financial risk. Risk if wrong: the
  n=12 warehouse-level distance correlation has essentially no statistical power (n=12), so a
  real distance or SKU-mix confound cannot be fully ruled out from this dataset alone — treat as
  a strong lead, not a proven cause, until the audit confirms an operational (not compositional)
  explanation.
- **Falsified if:** The audit finds the four bottom warehouses ship a materially different
  product mix, customer mix, or destination profile than the top warehouses once broken down at
  shipment level (something this aggregate analysis did not fully rule out).

### R4 — Add server-side range validation ([1.0, 5.0]) to the customer rating capture form
- **Do what:** Add input validation to whatever app/form captures `Customer_Rating` so it cannot
  accept values outside [1.0, 5.0].
- **Why:** 118 of 27,673 non-null ratings (0.43%) fall outside the documented 1–5 scale (values
  observed: ‑1.0, 0.0, 6.0, 7.5, 9.0 — see cleaning log `customer_rating_out_of_range_flag`).
  These were correctly excluded from all rating statistics in this report (§3.7) rather than
  clipped or imputed, per the pipeline's flag-not-fix rule — but at source, nothing currently
  stops a client from submitting them.
- **Who:** Owner of the customer feedback capture form/API.
- **Cost / risk:** A client-side/server-side range check is a small, low-risk change.
- **Falsified if:** The values above 5 (6.0, 7.5, 9.0) turn out to belong to a different intended
  scale (e.g., a 0–10 NPS-style field merged in error from another system) rather than being
  simple entry errors — that would call for a schema fix, not just a range clamp. Worth a 5-minute
  check with the product owner before implementing.

### R5 — Do not trust `shipment_weight_kg`, `shipment_volume_cbm`, `shipping_cost_inr`, or
`revenue_inr` aggregates without checking the flagged/unflagged split; escalate the scale
question to the source-system owner
- **Do what:** Before publishing any dashboard KPI built on these four columns, compute it both
  including and excluding the `*_outlier_flag` rows (numbers below) and disclose the gap. Also
  ask the source-system/ETL owner whether a unit inconsistency (e.g., grams vs kg on part of the
  intake pipeline, or a batch-multiplier applied inconsistently) could explain it.
- **Why:** Stage 4.10 of the cleaning pipeline explicitly *stopped* attempting decimal-typo
  repair on these four columns because the would-be repair rate exceeded the 1% safety threshold
  — meaning the scale problem is too widespread to be individual typos. The unflagged/flagged
  mean gap is large: shipment weight 63.3 kg (excl., n=25,441) vs 221.3 kg (incl., n=28,476) — a
  3.5x difference; shipment volume 0.31 cbm vs 1.01 cbm — 3.2x; shipping cost ₹2,400 vs ₹5,870 —
  2.4x; revenue ₹14,135 vs ₹20,528 — 1.5x (§4). However, this is **not simple noise**: outlier-
  flagged weight rows are heavily concentrated in Industrial Equipment (46.2% of flagged rows vs
  8.3% of all shipments) and Furniture/Chemicals (17.2%/15.7% vs 8.8%/8.8% baseline) — categories
  that plausibly do ship heavier/bulkier units. So at least part of this is genuine product-mix
  variation, not pure data corruption, and it should not be treated as "just exclude the
  outliers."
- **Who:** ETL/source-system owner for these four fields; whoever maintains the executive
  dashboard that consumes them.
- **Cost / risk:** A source-system unit audit costs engineering time; the risk of *not* doing it
  is that every dashboard KPI on cost, revenue, weight, or volume for this dataset is silently
  sensitive to a 1.5–3.5x swing depending on an analyst's inclusion choice, with no way for a
  dashboard viewer to know which was used.
- **Falsified if:** The source-system audit finds no unit/scale inconsistency and the flagged
  rows are confirmed to be ordinary large shipments correctly recorded — in that case, the
  outlier flags should be retired, not treated as a standing caveat.

### R6 — No domain recommendation is supported for a distance-based shipping-cost pricing model — treat this as a data-collection gap, not a proven finding
- **This is a null result stated plainly, not an oversight.** `distance_km` explains
  essentially none of the variance in `shipping_cost_inr` (Pearson r=0.071, p=8.9e‑34, n=29,354 —
  statistically significant only because of the huge sample size; r²=0.005, i.e. distance
  explains 0.5% of cost variance). This holds within every individual transport mode too
  (r=0.068–0.094, all still ~r²<1%; Sea is not even significant, p=0.09, n=475). Even restricting
  to non-outlier-flagged shipping-cost rows, the correlation only rises to r=0.164 (r²=0.027,
  still weak). For a logistics network, cost being this decoupled from distance is unusual and
  worth a direct question rather than a guessed cause.
- **What to collect/check instead:** Ask the pricing/finance team whether `shipping_cost_inr` is
  actually computed from distance in the source tariff system, or from a flat-rate/weight-based/
  contract-based schedule instead. If distance-based pricing is expected, this points at a
  join/lookup problem upstream (wrong distance value joined to the wrong shipment) rather than a
  real business fact; if it is not distance-based by design, this is simply confirmation that
  `distance_km` should not be used as a proxy for cost in any dashboard.
- **Who:** Pricing/finance data owner.

---

## 3. Business findings

All statistics below use `viz_ready.csv` (n=29,354) unless a subset is noted. "Delivered"
subsets exclude `delivery_status == "In Transit"` (n=229, 0.78%) because `delay_days` is
inherently unknown before delivery (per business rule; not a data defect).

### 3.1 Delivery status mix
| Status | Count | % |
|---|---|---|
| On Time | 18,220 | 62.07% |
| Delayed | 8,488 | 28.92% |
| Early | 2,417 | 8.23% |
| In Transit | 229 | 0.78% |

`delay_days == 0` corresponds to exactly the 18,220 On Time rows, and negative `delay_days`
(2,417 rows) corresponds exactly to the Early rows. This 1:1 correspondence means
`delivery_status` is a deterministic re-derivation of `delay_days`, not an independently observed
field — treat the two as one signal, not two corroborating ones, when building dashboards.
Negative `delay_days` is legitimate early arrival (business rule BR1) and is retained throughout
this analysis, not excluded.

### 3.2 Transit time and on-time rate by transport mode
| Mode | Mean transit days | Mean delay days | On-time rate | n |
|---|---|---|---|---|
| Air | 1.84 | 0.29 | 81.36% | 6,343 |
| Sea | 15.95 | 0.26 | 70.19% | 475 |
| Rail | 7.57 | 0.74 | 64.07% | 6,344 |
| Road | 5.61 | 1.15 | 54.37% | 16,192 |

- Transit time by mode: one-way ANOVA F=4976.3, p<0.001, **η²=0.339** (large effect) — mode
  strongly determines how long a shipment takes, as expected.
- Delay days (deviation from schedule) by mode: ANOVA F=123.0, p=3.4e‑79, **η²=0.0125** (tiny
  effect despite the astronomically small p-value — with n=29,125 almost any group difference is
  "significant"; the practical size of the effect is small).
- Delivery status x mode: χ²=1694.9, p<0.001, **Cramér's V=0.139** (small-to-moderate). Road's
  on-time disadvantage is real but the association is not overwhelming — most of Road's own
  shipments are still delivered on time.

### 3.3 Profitability structure
- Profit margin overall: mean 28.27%, median 29.29% (n=29,354). 11.83% of all shipments are
  loss-making (`profit_inr_negative_flag`, 3,473 rows) — this is real signal per business rule
  BR2, not an error.
- **By transport mode: no effect.** ANOVA F=0.407, p=0.748, **η²=0.0000**. Mean margins: Air
  28.02%, Rail 28.47%, Road 28.28%, Sea 28.41% — all within noise of each other. This is a
  genuine null result: do not manage profitability through mode choice.
- **By product category: huge effect.** ANOVA F=4299.9, p<0.001, **η²=0.594**.

| Category | Mean margin % | Median margin % | n |
|---|---|---|---|
| Books & Stationery | ‑2.13 | ‑1.03 | 2,349 |
| Food & Beverages | 11.27 | 11.87 | 2,854 |
| FMCG | 16.13 | 16.99 | 5,864 |
| Furniture | 21.04 | 21.61 | 2,073 |
| Clothing (unclassified bucket, see §4) | 23.37 | 25.30 | 31 |
| Clothing & Apparel | 25.18 | 25.74 | 3,231 |
| Chemicals | 32.19 | 32.76 | 2,583 |
| Auto Parts | 35.17 | 35.91 | 2,661 |
| Industrial Equipment | 43.00 | 43.63 | 2,423 |
| Electronics | 55.44 | 56.07 | 2,982 |
| Pharmaceuticals | 59.11 | 59.70 | 2,303 |

- Cost per kg by mode (derived `cost_per_kg` column, right-skewed — treat mean with caution,
  median is more robust): Air mean ₹1,391 / median ₹325; Sea mean ₹598 / median ₹91; Road mean
  ₹539 / median ₹122; Rail mean ₹375 / median ₹92 (n=6,144/453/15,708/6,171 respectively; nulls
  from missing weight excluded). Air is the most expensive mode per kg by a wide margin, as
  expected for air freight.

### 3.4 Returns
- Overall return rate: 8.57% (2,517 of 29,354).
- **By product category: strong effect.** χ²=1177.4, p<0.001, **Cramér's V=0.200** (moderate —
  the largest categorical effect size found in this analysis). Clothing & Apparel (21.8%) and the
  unclassified "Clothing" bucket (25.8%, n=31, see §4) return far more than any other category;
  Chemicals is lowest at 2.9%. This matches an intuitive apparel-fit/sizing return pattern.
- **By transport mode: null result.** χ²=0.865, p=0.834, Cramér's V=0.005. Return rate is flat
  across Road/Rail/Air/Sea (8.3–9.3%) — transport mode has no relationship with whether a
  shipment gets returned, which makes sense (returns are a product-fit issue, not a shipping
  issue) and is worth stating explicitly rather than assuming a relationship exists.

### 3.5 Warehouse and regional performance
| Warehouse | n | On-time rate | Delayed rate | Mean profit margin % | Return rate |
|---|---|---|---|---|---|
| WH011 | 1,145 | 49.35% | 42.36% | 28.61 | 9.17% |
| WH010 | 1,478 | 50.54% | 41.81% | 27.95 | 7.44% |
| WH004 | 2,845 | 52.30% | 40.18% | 27.43 | 9.14% |
| WH009 | 1,762 | 52.89% | 39.50% | 27.96 | 8.40% |
| WH008 | 2,372 | 59.27% | 31.20% | 27.98 | 8.01% |
| WH002 | 4,117 | 60.34% | 31.33% | 28.39 | 8.87% |
| WH007 | 2,297 | 61.52% | 29.65% | 28.37 | 8.45% |
| WH012 | 596 | 64.60% | 24.16% | 29.08 | 8.05% |
| WH006 | 2,438 | 67.84% | 23.63% | 28.69 | 9.02% |
| WH003 | 2,723 | 68.20% | 21.63% | 28.22 | 9.25% |
| WH005 | 3,490 | 69.17% | 20.52% | 28.33 | 8.34% |
| WH001 | 4,091 | 70.28% | 19.80% | 28.60 | 8.16% |

χ²=929.2, p<0.001, Cramér's V=0.103 (small-to-moderate). Note profit margin and return rate are
essentially flat across warehouses (27.4–29.1% margin, 7.4–9.3% returns) — the warehouse effect is
specific to on-time delivery, not profitability or returns.

- Destination region on-time rate: South 69.4%, West 66.3%, Central 63.1%, North 57.0%, East
  50.8% (χ²=824.7, p<0.001, Cramér's V=0.097 — small-to-moderate). East is the weakest-performing
  destination region.

### 3.6 Delay reasons (delayed shipments only, n=8,488; 170 have no captured reason)
Top reasons: Traffic Congestion 1,790 (21.1%), Bad Weather 1,745 (20.6%), High Volume Season
1,304 (15.4%), Vehicle Breakdown 868 (10.2%), Recipient Unavailable 636 (7.5%), Strike/Bandh 562
(6.6%), Scheduling Delay 509 (6.0%), Address Issue 426 (5.0%), Documentation Issues 310 (3.7%),
Customs Clearance 147 (1.7%), Port Congestion 21 (0.2%). **Data-provenance note:** cross-tabbing
reason against mode shows several reasons occur *exclusively* on one mode — Traffic Congestion,
Recipient Unavailable, Address Issue, and Vehicle Breakdown occur only on Road; Port Congestion
and Customs Clearance occur only on Sea/Air. This is consistent with the reason field being
generated/assigned by a rule keyed on transport mode rather than logged independently per
incident — treat any specific-reason root-cause claim as a hypothesis to validate against real
operational records, not a confirmed diagnosis (see R2's caveat).

### 3.7 Customer rating (valid range only, [1.0, 5.0])
118 of 27,673 non-null ratings (0.43%) are out of range and excluded per business rule BR5 (see
§4). Valid n=27,555. Mean 3.71, median 3.90, std 0.99.
- Rating vs. `delay_days`: Pearson r=‑0.571, p<0.001 (n=27,555) — a genuinely strong negative
  relationship (r²=0.326, i.e. delay explains about a third of rating variance).
- Rating by delivery status: ANOVA F=30,894.0, p<0.001, **η²=0.692** (very large effect). Mean
  rating: Delayed 2.44, On Time 4.20, Early 4.50. This is the strongest relationship found in the
  entire dataset and directly supports prioritizing on-time performance (R2, R3) as a customer
  satisfaction lever, not just an operational metric.

### 3.8 Distance relationships / synthetic-data check
- `distance_km` vs `shipping_cost_inr`: r=0.071, p=8.9e‑34 (n=29,354) — statistically significant
  purely from sample size, but r²=0.005: distance explains essentially none of shipping cost
  variance. See R6.
- `shipment_weight_kg` vs `shipment_volume_cbm`: r=0.545, p<00.001 (n=28,476) — a sensible,
  moderate-strength physical relationship (heavier shipments tend to be bulkier). This one
  behaves as expected and is not a synthetic-flatness concern.
- `actual_transit_days` vs `distance_km`: r=0.455, p<0.001 (n=29,125) — moderate, sensible
  (farther shipments take longer), though transport mode is a likely confound (Sea covers similar
  distances to Road/Air/Rail on average — see below — but takes far longer).
- Mean distance is nearly flat across transport modes: Air 1,424 km, Sea 1,488 km, Rail 1,365 km,
  Road 1,259 km. Mode choice in this dataset is **not** primarily a function of distance (a Sea
  shipment travels, on average, about the same distance as a Road shipment, despite taking ~3x
  longer) — worth knowing before assuming any distance-based mode-selection logic exists in the
  source system.
- Customer type (Enterprise/Retail/Wholesale) vs delivery status: χ²=12.44, p=0.053 — **not
  significant at the conventional 0.05 threshold** (borderline). Customer type does not
  meaningfully predict delivery outcome; do not build a "prioritize Enterprise customers for
  on-time delivery" narrative on this data.
- Road vehicle type (Container/Heavy/Medium/Mini Truck, Pickup Van) on-time rates are flat at
  53.0–55.1% — no vehicle-type effect within Road, consistent with the delay driver being route/
  traffic-level, not vehicle-class-level.

### 3.9 Seasonality
Monthly shipment counts (aggregated across all four years, 2022–2025) show a real Oct–Dec surge:
Jan–Sep average ~1,993 shipments/month vs Oct 3,742 / Nov 3,784 / Dec 3,934 — roughly 88% higher
in Q4. Chi-square goodness-of-fit against a uniform monthly distribution: χ²=3299.7, p<0.001.
This pattern repeats consistently in **every one of the four years** individually (e.g. 2022:
777/810/848 in Oct/Nov/Dec vs ~450 average other months; 2025: 1,067/1,055/1,123 vs ~550 average),
and the dataset's final month (December 2025) runs a complete calendar month (through Dec 31,
2025, confirmed against `shipment_date` max), so this is not an artifact of a truncated final
period the way a naive day-count normalization can manufacture a fake spike. This looks like a
genuine India festival-season/year-end e-commerce demand pattern and is a legitimate planning
input (capacity/staffing) rather than a cleaning artifact.

---

## 4. Operational findings — what the pipeline log says about the source systems

The cleaning log (`change_log`/flag columns) is read here as evidence about the systems that
produced the data, not just a QA checklist.

- **150-ish negative shipping costs are flagged, not corrected (BR4):** 148 rows (0.50%) have
  negative `shipping_cost_inr`. Magnitudes do not match a sign-flip pattern (mean |negative| =
  ₹7,238 vs mean positive = ₹5,963 — meaningfully larger, not a mirror image), so these were left
  as-is on the theory they may be legitimate billing credits/adjustments. Excluding them from the
  mean shipping cost shifts it from ₹5,870 to ₹5,938 (~1.1%) — small impact either way, but the
  billing system has no visible "credit reason" field to distinguish a real credit from an entry
  error. Recommend adding one (see R5-adjacent, not separately actioned here as materiality is
  low).
- **Four columns have a genuinely uncertain scale, not just outliers (Stage 4.10, R5):**
  `shipment_weight_kg` (3,035 flagged, 10.34%), `shipment_volume_cbm` (3,282, 11.18%),
  `shipping_cost_inr` (2,010, 6.85%), `revenue_inr` (778, 2.65%) all had automated decimal-typo
  repair *deliberately stopped* because the would-be repair rate exceeded the pipeline's 1% safety
  threshold — meaning too many rows would have been "corrected," which is itself evidence the
  column's scale/unit is inconsistent across a meaningful share of rows, not that individual
  values are typos. See R5 for the size of this effect on aggregates and the finding that at
  least part of it correlates with genuinely bulkier product categories (Industrial Equipment,
  Furniture, Chemicals) rather than being pure noise.
- **`fuel_cost_inr` and `operational_cost_inr` decimal-typo repairs were trustworthy:** small
  counts (70 and 153 rows respectively) with repair rates under the 1% threshold, so these were
  corrected (divided by 10/100/1000) rather than merely flagged. No caveat needed on these two
  columns.
- **Customer rating out-of-range (BR5):** 118 of 27,673 non-null ratings (0.43%) are impossible
  under the documented 1.0–5.0 scale (values ‑1.0, 0.0, 6.0, 7.5, 9.0). These were flagged, not
  corrected — no arithmetic transform (e.g., /10) lands them back in range — and were excluded
  from every rating statistic in this report. See R4.
- **`transport_mode_unknown_category_flag` (227 rows, 0.77%):** these rows still resolved to a
  valid mode (Road: 165, Air: 62) via the fuzzy/synonym engine but scored low enough on
  confidence to be flagged for manual review. Low materiality (0.77% of rows) but worth a spot
  audit if the mapping logic is ever revisited.
- **`product_category_unknown_category_flag` (31 rows, 0.11%):** all 31 are the literal value
  "Clothing," which scored only 62 on fuzzy match against "Clothing & Apparel" — below the
  pipeline's 70-point auto-correct threshold — and was deliberately left unclassified rather than
  guessed into an existing bucket. Treated in this report as its own small category (§3.3, §3.4)
  per the flag-handling instruction; a human should confirm whether "Clothing" is genuinely a
  distinct category or the same as "Clothing & Apparel" before merging it.
- **Missing-value patterns are almost all designed, not defects:**
  - `driver_id` null for 6,818 rows (23.2%) — Air/Sea shipments have no truck driver, by design.
  - `actual_delivery_date` and `delay_days` both null for exactly 229 rows (0.78%) — these are
    the In Transit shipments; delay is inherently unknown before delivery.
  - `delay_reason` null for 21,036 rows (71.66%) = the 20,866 non-delayed shipments (On
    Time+Early+In Transit) plus 170 delayed shipments with no captured reason. The 170 uncaptured
    reasons among actually-delayed shipments are a genuine (small) gap, not fabricated.
  - `shipment_weight_kg` null for 878 rows (2.99%), `fuel_cost_inr` null for 1,175 rows (4.00%),
    `customer_rating` null for 1,681 rows (5.73%) — all left as legitimate gaps (customer chose
    not to rate; no clean correlation found for the cost/weight gaps), per the brief's
    never-fabricate-a-measurement/identity rule.
- **`shipment_weight_kg_sign_flag` (88 rows):** negative weights were corrected via `abs()` (not
  merely flagged) because the magnitude of the negatives matched the overall column median almost
  exactly (36.81 vs 36.89), consistent with a sign-flip entry error rather than a different unit
  or a real negative-weight scenario (weight has no legitimate negative interpretation). This
  correction is trustworthy and needs no caveat in this report.
- **`date_logic_violation_flag`:** 0 rows in this file, as expected — the 646 physically-
  impossible rows (delivery before dispatch) were already filtered out before this file was
  produced (Stage 8), per the task instructions.

---

## 5. What we cannot say

- **Why** Books & Stationery specifically runs a negative margin. The data confirms the *what*
  (§3.3, R1) at high confidence, but not the *why* — no cost-breakdown-by-line-item or contract
  terms are present in this dataset to distinguish "underpriced," "high-cost carrier lane," or
  "intentional loss-leader." Needs the category's contract/pricing records.
  - **What would answer it:** a per-shipment cost breakdown (carrier base rate, fuel surcharge,
    handling) joined to contract/pricing terms for the category.
- **Whether the Road delay-reason breakdown reflects real operational causes or a data-generation
  rule.** §3.6 shows delay reasons are mode-exclusive, which is consistent with either (a) some
  reasons genuinely only occurring on certain modes (plausible — Customs Clearance really can't
  happen on a domestic Road shipment) or (b) reasons being assigned from a fixed lookup rather
  than logged per incident. This dataset cannot distinguish the two.
  - **What would answer it:** raw incident logs or GPS/telemetry timestamps independent of the
    `delay_reason` field, to check whether the stated reason correlates with independently
    observable events (e.g., a GPS-confirmed traffic slowdown on the recorded route).
- **Whether the four bottom-performing warehouses (R3) have a genuinely different customer or
  destination mix that a shipment-level (not warehouse-level, n=12) analysis would reveal.** The
  transport-mode-mix and average-distance checks in R3 found no obvious confound, but with only
  12 warehouses, the distance correlation test (r=0.07, p=0.83) has essentially no statistical
  power to detect a real relationship if one exists.
  - **What would answer it:** a shipment-level regression of on-time status on warehouse fixed
    effects, controlling for destination, product category, and customer type simultaneously
    (this report only checked mode-mix and mean distance one at a time).
- **Whether the outlier-flagged weight/volume/cost/revenue values (§4, R5) represent a real unit
  inconsistency upstream or genuinely large shipments.** The product-category concentration
  (Industrial Equipment, Furniture, Chemicals) is suggestive of the latter but does not rule out
  a unit bug that happens to be more common for certain shipment types (e.g., a bulk-order entry
  path that both handles heavier goods and has a different, buggy unit-conversion step).
  - **What would answer it:** the raw pre-cleaning source records with a units field, or a direct
    conversation with the source-system owner about whether any intake channel records weight/
    volume/cost in different units for large/bulk orders.
- **Whether the Oct–Dec seasonal spike (§3.9) is driven by demand, capacity planning, or a
  specific customer/industry segment.** The pattern is confirmed real and consistent across four
  years, but this dataset does not indicate the underlying driver (e.g., festival-season retail
  demand vs a specific large Enterprise contract's year-end ordering cycle).
  - **What would answer it:** an Oct–Dec breakdown by `industry` or `customer_type` to see if the
    spike concentrates in one segment or is broad-based.

---

*Report generated by an automated analytics stage against `viz_ready.csv` (29,354 rows, 84
columns). All statistics computed with pandas/scipy; every number above traces to a query against
this file or a count from its `*_flag` columns as documented in `01_business_brief.yaml`. No
number in this report was estimated or eyeballed.*
