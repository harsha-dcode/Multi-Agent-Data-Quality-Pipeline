# Incident — Tamil Nadu drug-manufacturer register

This is not a case study. The five runs under
[`case_studies/`](../../case_studies/) are benchmark runs of the same
specification against different data. This folder is the record of a run that
shipped a false premise, how it was found, and the specification change it
caused on 22 September 2026.

I kept it because the amendment that governs every run since came out of this
failure, and a fix is worth less than the evidence that something needed
fixing.

---

## What happened

The Stage 1 brief asserted, word for word:

> `Confirmed empirically: ADDRESS is 100% unique across all 549 rows`

That measurement was correct. On the raw file, exact-string, all 549 addresses
are distinct. Then Stage 4.3 collapsed whitespace, unified en-dashes and folded
case:

| Snapshot | Distinct addresses | Shared |
|---|---:|---:|
| Raw, exact string | 549 of 549 | 0 (Stage 1 measured here) |
| After normalisation | 545 of 549 | 4 addresses, 8 rows (every later stage reads here) |

The claim was true when written and false when used.

Validation returned 13 of 13 PASS, and that was also correct. Every check
verifies Stage 4 against Stage 1. Stage 1 was the thing that was wrong, and
nothing in the pipeline verified Stage 1.

The four shared addresses were not all the same kind of problem, which is why
the pipeline flags instead of merging:

| Verdict | Rows | What it is |
|---|---|---|
| EXACT DUPLICATE | 450, 520 | One establishment split across two rows, one per licence type. Violates the stated grain |
| SAME ENTITY | 331, 332 | Reckitt Benckiser, two legal spellings |
| SAME ENTITY | 464, 465 | Tagros Chemicals, one with a `(BULK)` qualifier |
| CO-LOCATED | 226, 470 | Two genuinely different firms in one building. Correct as-is |

An address-only dedup would have wrongly merged that last pair.

## What it cost

Very little. Licence counts do not move at all, because the duplicated pair
holds different licence types, so collapsing it removes a row without removing
a licence:

| | As reported | De-duplicated |
|---|---:|---:|
| Form 25 / 28 / 28D licences | 487 / 265 / 4 | 487 / 265 / 4 |
| Establishments | 549 | 548 |

Per-establishment percentages shift in the third significant figure. "532 of
549 (96.9%)" becomes "531 of 548 (96.9%)".

The size of the error is not the problem. An untested assertion in Stage 1
silently shaped what Stage 4.11 looked for, and nothing was built to catch
that. The duplicate check hunted for the same name at different addresses. The
real pattern here is the opposite, the same address under differently-written
names, and the check was aimed the wrong way because Stage 1 said the other
axis was already unique. On a register where duplicates share a licence type,
the same blind spot produces a badly wrong count.

External review found it. The pipeline did not. I am recording that here on
purpose.

## The fix

I amended the specification on 22 September 2026. Every empirical claim in a
brief now carries the expression that produced it, the number it returned, and
which snapshot it was measured on (`measured_on: raw | post_4.3`). Stage 3
re-runs every one of those expressions and compares. It is not allowed to read
the recorded conclusion. A number that moves between snapshots gets reported as
`BRIEF_CLAIM_UNVERIFIED` and treated as HIGH RISK.

See [`.claude/agents/data-pipeline-cleaner.md`](../../.claude/agents/data-pipeline-cleaner.md),
Stage 1 and Stage 3.

I have since tested the amendment against work that was already published.
Re-running the healthcare case study under it fired the rule on a second
dataset and turned up two more bugs in the pipeline itself. That write-up is in
[`case_studies/healthcare/RUN_SUMMARY.md`](../../case_studies/healthcare/RUN_SUMMARY.md) §13.
The re-run is the evidence that the fix does something. This folder is the
evidence that something needed fixing.

---

## Layout

| Path | What it is |
|---|---|
| [`07_address_axis_correction.md`](run1_before_fix/07_address_axis_correction.md) | The incident report. Read this first |
| [`01_business_brief.pre_fix.yaml`](run1_before_fix/01_business_brief.pre_fix.yaml) | The brief carrying the false claim, unedited |
| [`01_business_brief.yaml`](run2_after_fix/01_business_brief.yaml) | The corrected brief, measured instead of asserted |
| `fix_address_axis_duplicates.py` | The check that was never run, run |
| `run1_before_fix/` | The original run. Validation: 13 pass, 0 fail. Change log: 5,429 entries |
| `run2_after_fix/` | Re-run against the corrected brief. Validation: 14 pass, 0 fail. Change log: 4,687 entries |
| `input/drug_manlist_1_0.csv` | 549 rows, 12 columns, cp1252. Committed in full so the incident is reproducible |

Two things about these artifacts that I would rather state than have you
discover:

- `run1_before_fix/cleaned_data.csv` already carries the two remediation flags
  (`shared_address_flag`, `same_entity_suspect_flag`). The genuinely pre-fix
  cleaned output was not preserved. The backup copy that the incident report
  calls `cleaned_data.pre_address_fix.csv` is byte-identical to the post-fix
  file, so I have not shipped it. The before/after that does survive intact is
  the pair of briefs.
- This run predates the amended specification, so its briefs carry no
  `verified_by` or `measured_on` fields. That is the point of the folder, not
  an omission.

Unlike the five case studies, this run has no numbered stage scripts. I ran it
interactively. You can inspect it but you cannot reproduce it end to end from
this folder. The case studies are where the method is executable.
