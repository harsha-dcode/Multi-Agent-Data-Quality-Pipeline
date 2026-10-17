# Insights Report — Tamil Nadu Drug Manufacturer Licence Register

**Source:** `viz_ready.csv` (547 rows, 58 columns), the filtered/analysis view of the cleaned register.
**Scope chosen:** General EDA, framed around the regulator's stated use case (who to inspect / chase for renewal). Two rows with physically-impossible values (S-No 75, expiry-before-issue; S-No 185, zero licences held) were excluded upstream by the cleaning pipeline and are not referenced here.

---

## 1. How many firms need renewal-chasing?

- **146 of 547 firms (26.7%)** have at least one expired licence (`any_licence_expired = True`); **401 (73.3%)** currently show no expired licence on any held licence type.
- By licence type, among firms that actually **hold** that licence (using `holds_form25/28/28d`, not raw non-null counts, as instructed):
  - Form 25: 486 holders, **129 expired (26.5%)**
  - Form 28: 264 holders, **61 expired (23.1%)**
  - Form 28D: 4 holders, **0 expired** — sample too small (per the brief) to generalize, but worth noting none of the four rare specialised licences are currently lapsed.
- Of the 146 flagged firms, 85 have only Form 25 expired, 17 have only Form 28 expired, and 44 have **both** Form 25 and Form 28 expired simultaneously — these 44 are the highest-priority chase list, since they have no currently-valid licence of either main type on file.
- **Caveat:** the "expired" flag is computed against **2018-03-20**, which is a *proxy* "as-of" date (the latest issue date observed anywhere in the source file), not a real system clock date. If the register was actually compiled later than that, every expiry count above is a **lower bound** — the true chase list is very likely larger. Consistent with this, expiries are heavily concentrated right before that proxy date (2016: 49, 2017: 113, 2018 partial-year: 20, vs. only 9 total before 2016) — this clustering is at least partly a mechanical artifact of how the "as of" date was derived from the same data, not necessarily a genuine recent spike in lapses.
- Six licence numbers carry a literal **"Cancelled"** annotation in the source text (4 in Form 25, 2 in Form 28) — these are not currently active *regardless* of what the computed expiry flag says, since a cancellation is an explicit regulatory action, not a date-based lapse. These 6 rows are worth a manual look, as they may not all be caught by the expiry-date logic.

## 2. Licence-holding patterns

| Segment | Firms | % of 547 | Expired rate within segment |
|---|---|---|---|
| Form 25 only | 280 | 51.2% | 28.9% |
| Form 25 + Form 28 | 206 | 37.7% | 24.8% |
| Form 28 only | 57 | 10.4% | 24.6% |
| Form 28D only | 3 | 0.5% | 0.0% |
| Form 28 + Form 28D | 1 | 0.2% | 0.0% |

- Every firm in the file holds at least one licence type (the one firm with zero licences, S-No 185, was excluded upstream).
- Form 25-only firms are both the largest segment (over half the register) **and** the segment with the highest expiry rate (28.9%) — they are the natural first target for a renewal campaign by sheer volume and risk.
- Form 28D is confirmed rare (4 of 547, ~0.7%), exactly as flagged in the brief — no broad claims are drawn from it beyond "none currently lapsed."
- Typical licence validity term (expiry year − issue year, where both dates are known) is bimodal: **5 years** and **10 years** are by far the most common terms for both Form 25 (213 and 91 of 476 dated pairs) and Form 28 (110 and 54 of 256 dated pairs), with a long tail of much longer gaps (15–64 years) that likely reflect one-time renewals recorded against an original issue date rather than a genuine multi-decade single term. Median term is 10 years for both forms.

## 3. Registration activity over time

- Combined issue-year counts (all three licence types stacked) show a clear, steady **upward trend from the early 1990s through 2017**, not a single sharp "surge" year: roughly 10–20/year in the late 1990s–2000s, climbing to 30–45/year from 2011–2014, and peaking at **69 (2015), 58 (2016), 72 (2017)**. 2018 shows only 4, but that is a partial year (the file's latest observed issue date is 2018-03-20), not a genuine drop-off.
- This reads as sustained, gradually-accelerating growth in Tamil Nadu drug manufacturing registrations over two decades, rather than a one-off policy-driven registration spike. If anything, 2015–2017 is a real high point, plausibly tied to industry growth or a renewal-cycle bunching effect, but there is no isolated anomalous year that stands out against the trend — this is a case where the "surge" hypothesis from the brief is **not strongly supported**; growth is gradual, and it should be reported as such rather than over-narrated.
- A handful of very old issue years survive (1953, 1957, 1960, 1966, ...) — legacy licences still on the active register, several decades old.

## 4. Data governance signal: near-duplicate entries

- **36 of 547 rows (6.6%)** carry `near_duplicate_flag = True`, spanning roughly 21 name/address clusters. Inspecting the clusters confirms the brief's three root causes are all present in this register:
  - **Same firm, split across rows** (data governance gap): e.g. *Sundaram Care Product* — two rows, identical address, one holding Form 25 and the other holding Form 28. *Jayachitraa Surgitex* similarly appears 3 times at the same site with licences split across rows. Treating these as separate "manufacturers" double-counts the firm.
  - **Shared address, different firm names** (plausibly co-located manufacturers): e.g. *Medihub Sciencetec Pvt Ltd* and *SIDD Life Sciences Pvt-Ltd*, both at "Plot No-4, NH-7, MMDA Industrial Estate, Maraimalai Nagar." These are likely genuinely distinct manufacturers sharing an industrial-estate address, not a data error.
  - **Multi-site companies, not duplicates**: e.g. *Caplin Point Laboratories Limited* and *Bafna Pharmaceuticals Ltd* each appear twice with clearly different addresses (different plants) — correctly *not* an error, just a "one firm, multiple rows" reality the register doesn't structurally separate from the true duplicates above.
- **Operational takeaway for the regulator:** a simple row count or `name` count is not a reliable count of distinct manufacturers. `name` alone is already off by 14 (533 unique names across 547 rows), and the fuzzy `near_duplicate_flag` catches a further, larger set (36 rows) that plain exact-match dedup would miss due to punctuation and address-text variation. Before using this register to answer "how many manufacturers are licensed in Tamil Nadu," the ~21 flagged clusters should be manually adjudicated into "same firm" vs. "co-located but distinct" vs. "same firm, multiple plants" — this is a register/data-entry hygiene issue in the source system, not something the cleaning pipeline can resolve automatically without human judgment.

## 5. Other data-quality notes relevant to interpretation

- 9 date cells across Form 25/28 (issue or expiry) were unparseable in the source (truncated years, invalid days, Excel month-year corruption) and are now null — but in every one of these 9 cases the **licence number is still present**, i.e., the firm's licence status is known even though a decision date is not. These firms should not be treated as "no licence" or silently dropped from expiry analysis; they simply need the source register checked manually for the true date.
- 2 Form 28 cells contain a second embedded CLAA (loan licence) cross-reference; the primary date was kept and only the cross-reference is flagged — not expected to materially change any of the aggregate figures above.
- Licence-number fields are free-form (bare digits, "TN########", "###/YYYY" suffixes) and were correctly *not* treated as a clean categorical/numeric field anywhere in this analysis.

---

## Bottom line for the regulator

- Immediate renewal-chase priority: the **44 firms with both Form 25 and Form 28 expired**, plus the **6 firms with an explicit "Cancelled" annotation** on a licence number — these are the clearest "currently without a valid licence" cases.
- Next-tier priority by volume: the 280-firm **Form-25-only segment**, which has both the largest headcount and the highest expiry rate (28.9%).
- Treat all expiry-based counts as a **floor**, not an exact figure, given the proxy "as of" date.
- Before reporting a headline "number of licensed manufacturers in Tamil Nadu," resolve the ~21 near-duplicate clusters — the honest range is "547 register rows, representing somewhat fewer than 547 distinct manufacturers, with several clusters needing manual adjudication."
