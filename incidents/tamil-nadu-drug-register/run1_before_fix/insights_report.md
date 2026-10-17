# Tamil Nadu Drug Manufacturer Licence Register — Insights Report

**Source:** `drug_manlist_1_0.csv` (549 raw rows, Windows-1252) → `cleaned_data.csv` (549 rows) → `viz_ready.csv` (548 rows, analysed here)
**Run date used for all expiry/active computation:** 2026-09-22
**Grain:** one row = one registered manufacturing establishment (name + address); a company may operate several establishments, each its own row.

---

## 1. Headline

Every single licence in this register — all 754 held Form 25 / Form 28 / Form 28D licence
instances, across 548 establishments — is either **expired or administratively cancelled as of
2026-09-22; zero are currently active**. But the honest reading of that fact is not "96.9% of
Tamil Nadu drug manufacturers are non-compliant" — it is that **the latest expiry date anywhere
in this register is 2022-12-29, 3.7 years before the run date**. No renewal, reissue, or new
licence action of any kind is recorded after that date, for any of the 548 establishments. That
pattern — a hard ceiling on the data, not a gradual decline — is the signature of a **stale,
unmaintained source extract**, not of a regulatory collapse. The regulator's first action should
not be "inspect 531 firms"; it should be **confirm with the licensing authority whether this
register has actually been updated since December 2022 before treating any expiry count in this
report as an actionable compliance list** (§3.1, §4). Once that is confirmed, the underlying
per-firm expiry data is well-formed and usable for a worklist — the recommendations below assume
that confirmation step happens first.

---

## 2. Recommendations

**R1 — Do not issue an inspection/renewal-chase worklist from this extract until the register's
currency is verified with the licensing authority.**
- **Why:** The maximum expiry date across all 754 held licences (Form 25, 28, 28D combined) is
  2022-12-29 (§3.1). Zero establishments show any licence action — issue, renewal, or expiry —
  after that date, out of 548. If the register were live and firms were genuinely renewing on
  schedule, we would expect some post-2022 expiry dates given licence terms as short as 5 years
  (§3.2); we see none. A single hard ceiling across an entire 548-row, 754-licence-instance table
  is far more consistent with "this table was not updated after ~Dec 2022" than with "every
  manufacturer in Tamil Nadu simultaneously stopped renewing."
- **Who:** The Tamil Nadu Drug Control Administration's records/IT owner for this register (the
  team that produced `drug_manlist_1_0.csv`).
- **Cost/risk:** Cost is one confirmation email/call plus, ideally, pulling a fresher extract.
  Risk of skipping this step: field inspectors are dispatched to 531 firms based on a number that
  may already be known to the department to be an artifact of extract age, wasting inspector time
  and firm goodwill, and the report's credibility is damaged the first time an inspected firm
  produces a valid 2024 or 2025 renewal certificate that never made it into this table.
- **Falsified if:** The licensing authority confirms the extract is current (i.e., truly no
  establishment in Tamil Nadu has renewed any of these three licence types since Dec 2022), or a
  fresher pull of the same source shows post-2022 expiry dates. Either would mean the register is
  live and R1 can be dropped in favour of acting directly on §3.1's numbers.

**R2 — Once currency is confirmed (or a fresher extract is obtained), prioritise the 5
establishments with a licence marked "Cancelled" ahead of the 526 merely "expired" ones.**
- **Why:** `form_25_licence_no_cancelled_flag` (4 establishments) and
  `form_28_licence_no_cancelled_flag` (2 establishments, 1 overlapping) mark a licence explicitly
  revoked by the issuing authority in the source register, independent of expiry_date — this is
  a stricter and more deliberate non-active status than a licence that simply lapsed
  (§3.1, §5). The 5 establishments are G-K- Labs (S-No 131), G-T- Raj Tex (S-No 133), Orchid
  Health care (A Division of Orchid Chemicals…) (S-No 276), SDS Ramcides Crop Science Pvt. Ltd
  (S-No 367), and SICGIL India private Limited (S-No 387).
- **Who:** Field inspection team / licensing officer who triages the worklist.
- **Cost/risk:** Negligible — this is a re-sort of an existing list, not new work. Risk of
  ignoring it: a revoked manufacturer is treated with the same low urgency as one that simply
  missed a renewal deadline.
- **Falsified if:** The department's own records show these 5 licences were reinstated after the
  register was cut, or that "Cancelled" in the source text meant something less severe than
  revocation (e.g., voluntary surrender pending renewal) — worth a one-line confirmation from the
  authority, since the source text is a free-text annotation, not a controlled status code.

**R3 — Route the 16 establishments with a held licence but no usable expiry date to a distinct
"verify by phone/paper file" queue, not into either the expired or active bucket.**
- **Why:** These 16 establishments (S-Nos 17, 30, 87, 120, 384, 462, 463, 511, 512, 526, 527, 528,
  529, 546, 547, 549 — full list in §3.1) hold a Form 25 and/or Form 28 licence number but the
  expiry date is either unparseable in the source (8 establishments; see
  `form_25_expiry_date_unparseable_flag` / `form_28_expiry_date_unparseable_flag`) or was simply
  never recorded even though the licence number and issue date are present (8 establishments —
  a residual gap not covered by any existing flag, found by inspecting held rows with a null
  expiry date that were not flagged unparseable). Neither the "expired" nor "active" derived
  column can be computed for them; folding them into either bucket silently would misstate the
  worklist.
- **Who:** Records team that maintains the register (to backfill or re-key from the paper file);
  field team to confirm status directly for firms in this queue.
- **Cost/risk:** Low cost (one lookup per firm against a paper/legacy file). Risk of skipping:
  16 establishments effectively disappear from the compliance count — neither flagged as overdue
  nor confirmed compliant.
- **Falsified if:** The department's paper/legacy file has the missing expiry dates on record
  (i.e., this is a purely digital-transcription gap, not a genuine source gap) — in which case the
  fix is a one-time backfill, not a process change.

**R4 — Investigate "Kalyan Oxygen Pvt. Ltd" (S-No 185) as a data-quality exception, not a
compliance case.**
- **Why:** It is the only establishment (1 of 548) with all three licence-number fields null —
  it holds none of Form 25, Form 28, or Form 28D per this register. Every other establishment
  holds at least one licence type.
- **Who:** Records team — confirm whether this is a genuine omission (the firm should hold a
  licence and it wasn't captured) or the firm is registered on this list for an unrelated reason
  (e.g., an industrial-gas manufacturer captured by a different regulatory trigger, not a Form 25/
  28/28D-holding drug manufacturer).
- **Cost/risk:** Trivial — one record lookup. Risk of ignoring: either a genuinely unlicensed
  manufacturer is missed entirely (compliance risk), or the establishment count used elsewhere in
  this report is off by one (analytical risk).
- **Falsified if:** The firm is confirmed to be validly listed for a non-Form-25/28/28D reason
  (e.g., a different licence category not captured in this schema).

**R5 — Fix the intake process so that "expiry date" and "issue date" are never left blank when a
licence number is present — do not add a corrective default.**
- **Why:** 8 establishments have a licence number and issue date on file but a genuinely blank
  (not garbled, not unparseable) expiry date (§3.1, R3). Separately, the `*_expiry_date_
  unparseable_flag` fields (2 + 6 = 8 rows) show the source cell had content that could not be
  parsed as a date at all (a compound two-date field or an Excel-corrupted fragment per the
  Stage-1 brief) — a different failure mode from a blank cell, and both point at the same
  upstream weakness: nothing in the intake form enforces that an expiry date is captured and
  captured as a real date whenever a licence number is entered.
- **Who:** Whoever owns the data-entry form/system used to originally register these licences.
- **Cost/risk:** Requires a form validation rule (mandatory, date-typed expiry field); no
  retroactive data risk since we are not proposing to backfill or guess values, only to prevent
  recurrence (per the register's own "never guess a value into existence" rule already applied by
  this pipeline).
- **Falsified if:** These blanks/unparseable cells originate from a legacy paper-to-digital
  migration rather than the current intake form — in which case the fix is a migration QA step,
  not a form-validation rule, and should be redirected there.

**R6 — Do not chase a geographic pattern in expiry status; none is supported by this data.**
- **Why:** A chi-square test of district (top 10 districts by establishment count, n=447) against
  `any_licence_expired` gives χ²=5.48, df=9, **p=0.79**, Cramér's V=0.13 (small effect) — no
  association (§3.3). Note this test has very limited power: with 96.9% of establishments overall
  flagged as having at least one expired licence, there is almost no variance left for geography
  to explain — a true small district-level effect could exist and still be undetectable at this
  base rate. Do not commission district-targeted inspection sweeps on the assumption that expiry
  clusters geographically; it does not, at least not detectably here.
- **Who:** Whoever would otherwise plan a district-level inspection campaign.
- **Cost/risk:** None — this is a recommendation not to spend effort on a geographic cut, saving
  planning time.
- **Falsified if:** A larger or fresher dataset (ideally one with genuine variance in expiry
  status, e.g. after R1 is resolved and true "active" licences appear) shows a significant
  district effect.

---

## 3. Business findings

### 3.1 Core operational finding — licence status by type (the regulator's worklist numbers)

Denominator: 548 establishments (see §5 for the 1 row excluded before this file, and the 2
near-duplicate pairs not deduplicated).

| Licence type | Held | Expired | Active | Cancelled (subset of Expired) | Status-unknown (held, no usable expiry date) |
|---|---|---|---|---|---|
| Form 25 | 486 | 477 (98.1% of held) | **0** | 4 | 9 |
| Form 28 | 264 | 253 (95.8% of held) | **0** | 2 | 11 |
| Form 28D | 4 | 3 (75.0% of held) | **0** | 0 | 1 |

Notes on this table:
- **"Cancelled" is a subset of "Expired," not additive.** All 4 cancelled Form 25 licences and
  both cancelled Form 28 licences also carry an expiry date in the past, so they are already
  counted inside the "Expired" column. They are called out separately because cancellation is a
  deliberate revocation, a stricter status than "allowed to lapse" — see R2.
- **"Status-unknown" is not "active."** It is a held licence for which no valid expiry date could
  be established — either the date field was unparseable in the source (form_25: 2 rows,
  form_28: 6 rows — 2 rows in each case actually carry both an unparseable issue date and an
  unparseable expiry date on the same row) or the field was simply blank despite the licence
  number and issue date being present (form_25: 7 rows, form_28: 5 rows, form_28D: 1 row — this
  latter sub-bucket is not covered by any existing pipeline flag; it was found by inspecting held
  rows with a null expiry date that were not already flagged unparseable). These 21 licence-level
  instances collapse to **16 unique establishments** (some hold more than one affected licence
  type) — see R3.
- **Active = 0 for every licence type.** Not one of the 754 held licence instances in this
  register has an expiry date on or after 2026-09-22. See §4 for why this is very unlikely to
  mean "zero compliant manufacturers in Tamil Nadu" and much more likely to mean "this extract
  predates any 2023–2026 renewal activity."

**Establishment-level roll-up** (one row per establishment, worst-status-wins):

| Status | Establishments | % of 548 |
|---|---|---|
| Expired (≥1 licence, none cancelled) | 526 | 96.0% |
| Cancelled (≥1 licence explicitly revoked) | 5 | 0.9% |
| Status-unknown only (no expired/cancelled licence, but ≥1 held licence has no usable expiry date) | 16 | 2.9% |
| No licence of any type on file | 1 | 0.2% |

531 of 548 (96.9%) have at least one expired-or-cancelled licence — this matches the pipeline's
own `any_licence_expired` column (531 True / 17 False), and the 17 "False" establishments split
into the 16 status-unknown firms above plus the 1 firm holding no licence at all.

### 3.2 Time pattern in expiry — is the 31-Dec clustering a real renewal cycle or an artifact?

Licence duration (issue_date → expiry_date) for the 476 Form 25 licences with both dates parsed
clusters tightly at round numbers: **5 years (210 licences, 44%), 10 years (91, 19%), 15 years
(65, 14%)**, with a long tail out to 20–25 years. Form 28 shows the same pattern (5 yr: 111/255 =
44%, 10 yr: 54/255 = 21%, 15 yr: 40/255 = 16%). **This is a genuine regulatory renewal cadence**
— Tamil Nadu drug licences are evidently issued/renewed in fixed 5-year blocks — not a data
artifact.

The 31-December expiry clustering named in the brief is a *different* phenomenon from the 5-year
cycle, and does look like an administrative convention rather than a real per-firm renewal date.
97 of 486 held Form 25 licences (20.0%) and 45 of 264 held Form 28 licences (17.0%) expire on
31 December of some year (dominated by 2017-12-31: 43 Form-25 / 23 Form-28 firms, and
2021-12-31: 35 Form-25 / 17 Form-28 firms). But the **licence duration for this 31-Dec subgroup
is not 5/10/15 years like the rest of the register — it averages 26.6 years (Form 25) / 25.2
years (Form 28), with individual values up to 64 years**, which is not a plausible licence term.
The likely explanation: for these older licences, `issue_date` reflects the establishment's
*original* registration date, while the 31-Dec `expiry_date` is a later, batch-assigned
administrative renewal deadline (e.g., all licences pending as of a department-wide review were
given a uniform calendar-year-end expiry) — not the date of an actual multi-decade licence term.
**Practical implication: do not use `expiry_date − issue_date` as "licence duration" for the
31-Dec subgroup — it will overstate typical licence terms by roughly 5x.** This explanation is a
plausible mechanism, not confirmed against the department's licensing rules; flagged for human
validation (an inspector or department analyst can confirm whether a Dec-2017/Dec-2021 batch
renewal event occurred).

### 3.3 Geography — tested, no effect found (null result)

Extracting district names from the free-text `address` field (495/548 rows, 90.3%, yield a
recognisable district or city token) and cross-tabulating the top 10 districts by establishment
count against `any_licence_expired` gives **χ²=5.48, df=9, p=0.79, Cramér's V=0.13** — not
significant, small effect. **No evidence that expiry status clusters by district.** Caveat: at a
96.9% overall expiry rate there is very little outcome variance for any predictor to explain, so
this null should be read as "no detectable effect at this base rate," not as strong evidence of
true geographic uniformity. Top districts by establishment count: Chennai (141), Chatrapatti (54),
Kancheepuram (36), Virudhunagar (26), Coimbatore (21), Madurai (19).

### 3.4 Licence-number format (old "NNN/YYYY" vs new "TNNNNNNNNN") vs expiry status — null result

Form 25 licence numbers split into 43 old-format ("NNN/YYYY"), 319 new-format ("TN..."), 124
"other" (a mix of bare numeric IDs, e.g. Form 28's "20", and free-text annotations), and 62 null
(no Form 25 held or corrupted). Cross-tabulating format against a 3-level status
(expired / other-not-expired / status-unknown) gives **χ²=4.80, df=4, p=0.31** — no significant
association. This is another case where the 98% expiry base rate leaves almost no room for format
to predict anything (310/319 new-format and all 43/43 old-format Form 25 licences are expired).
**Null result: the licensing scheme transition does not, by itself, predict which firms are
overdue** — unsurprising once you note that nearly every firm is overdue regardless of format.

### 3.5 Multi-plant companies

12 company names appear more than once across establishments (e.g., Jayachitraa Surgitex ×3,
Premier Enterprises ×3, Bafna Pharmaceuticals Ltd ×2, Caplin Point Laboratories Limited ×2, and
8 others ×2), consistent with the Stage-1 brief's grain decision (address, not name, is the
unique key — address is 100% unique across all 548 rows). No further statistical claim is made
about this group; it is reported because it affects how "531 establishments non-compliant" should
be read by anyone who thinks in terms of parent companies rather than physical sites (a company
appearing 3 times with 3 different plant addresses is 3 worklist items, not 1).

---

## 4. Operational findings — what the pipeline's own damage log says

- **The register has a hard expiry ceiling at 2022-12-29**, across all three licence types and
  all 548 establishments — no licence action of any kind (new issue, renewal) appears after that
  date. Combined with 0/754 active licences, this is the single most important fact in this
  report and is the basis for R1: treat this as a stale-extract signal, verify currency before
  acting on the raw expiry counts.
- **1 row was excluded from `viz_ready.csv`** ("Byby Health Care," original S-No 75): both its
  Form 25 and Form 28 `expiry_date` preceded `issue_date` by exactly one day — a physically
  impossible value, correctly flagged rather than corrected (no reliable way to infer the true
  dates) and correctly excluded from the chart-ready file while remaining in `cleaned_data.csv`
  for audit. This establishment is **not** in any count in this report; if a full worklist is
  produced downstream, it should be re-added as a 549th "manual review — dates physically
  inconsistent" item, not silently dropped.
- **5 licence-number fields show suspected Excel auto-date-conversion corruption**
  ("Dec-57", "Mar-63", "Jun-99", "Dec-53", "Jun-60"/"Mar-59") across 5 establishments (Central
  Prison, Intermed, Pharm Products Private Limited, Ramaraju Surgicals Cotton Mills Ltd, Raptakos
  Brett & Co Ltd). The true licence numbers for these are unrecoverable from this source; their
  issue/expiry dates are intact and usable, but any downstream system that tries to look up these
  firms by licence number will fail. This points at a **spreadsheet-based system-of-record where
  a licence-number column was at some point typed or opened without text formatting**, letting
  Excel silently reinterpret alphanumeric IDs as dates — a schema/tooling fix (force the column to
  text type at the source), not a one-time cleanup.
- **2 near-duplicate name+address pairs (4 rows)** were flagged, not deduplicated: "Sundaram Care
  Product" appears twice at an identical address, once holding only a Form 25 licence and once
  holding only a different Form 28 licence — a plausible clean split (one register entry per
  licence type for the same site) and reasonably treated as one establishment holding two
  licences. "Jayachitraa Surgitex" also appears twice at a near-identical address, but **both
  rows hold a Form 28 licence with two different licence numbers and different expiry dates**
  (TN00004595 vs TN00004827, both unknown/2022-12-29 respectively) — this looks less like a clean
  split and more like either two genuinely separate Form 28 registrations at one site or a
  duplicate register entry. **This report treats all 4 rows as-is (2 establishments' worth of
  data spread across 4 rows, not deduplicated)** for the worklist in §3.1, since collapsing them
  without confirming which licence number is current would risk dropping a live licence action
  item. Flagged for human review before any per-establishment (as opposed to per-row) count is
  finalized elsewhere.
- **`address_encoding_artifact_flag`** (335 of 548 rows, 61.1%) and **`name_encoding_artifact_flag`**
  (7 rows) mark a cosmetic period-to-hyphen substitution already investigated by the pipeline and
  left uncorrected. This does not affect any count in this report and is mentioned only because
  it touches the majority of address text and would need to be accounted for if anyone later does
  further text mining (e.g., a more precise district/pincode extraction than §3.3's regex).
- **Kalyan Oxygen Pvt. Ltd (S-No 185)** holds none of the three licence types — the only such row
  in the register (see R4).
- **Two historical licence-number formats coexist** (old "NNN/YYYY", newer "TNNNNNNNNN") reflecting
  a genuine scheme transition, not a data defect (§3.4).

---

## 5. What we cannot say

- **We cannot say what fraction of Tamil Nadu drug manufacturers are actually non-compliant
  today.** The 0%-active / 98%-expired numbers in §3.1 are a function of a register that appears
  frozen at end-2022 (§4); they are not evidence about the state of the industry in 2026. Answering
  the real compliance question requires a fresher extract or a live query against the licensing
  authority's current system.
- **We cannot confirm the mechanism behind the 31-Dec batch-expiry pattern (§3.2).** The
  "administrative batch renewal deadline" explanation is plausible and consistent with the
  anomalously long apparent licence durations, but it has not been checked against the
  department's actual licensing rules or historical renewal-cycle announcements. This needs a
  domain expert or department record, not more analysis of this file.
- **We cannot confirm whether the 8 "genuinely blank expiry date" rows (§3.1, R3) reflect a
  source-system gap or a paper record that was never digitized.** Both point at different fixes
  (form validation vs. migration backfill) and only the records team can distinguish them.
- **We cannot say whether the two Jayachitraa Surgitex rows (§4) represent one establishment with
  two Form 28 licences or two separate registrations of the same site** — this needs a human
  check against the physical licence certificates, not a data-cleaning decision.
- **We do not have a "true establishment count" independent of the address field.** The grain
  decision (address is the unique key) is reasonable and stated in the Stage-1 brief, but two
  near-identical addresses (§4) show the boundary is not perfectly crisp; a small number of
  worklist items could collapse or split depending on how a human resolves them.
- **We have no data on inspection outcomes, penalties, or actual manufacturing activity** — this
  register only tells us what licences are on file and when they say they expire, not whether an
  establishment is operating, dormant, or already closed. A worklist built from this file should
  be treated as a starting point for verification, not a finished compliance judgment.
