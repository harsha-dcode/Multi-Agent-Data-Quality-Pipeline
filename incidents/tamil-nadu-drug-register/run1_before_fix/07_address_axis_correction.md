# Address-axis duplicate correction

Corrects an untested Stage 1 assumption. Found by external review, not by the pipeline.

## 1. The claim, tested

The brief asserted ADDRESS is 100% unique. Testing it:

```
rows                : 549
distinct addresses  : 545
shared addresses    : 4
```

**The claim is FALSE.** The brief said 'confirmed empirically' for something that was asserted, not measured.

## 2. The address-axis check the pipeline never ran

`shared_address_flag` -> True on **8 rows** across 4 addresses.

| Verdict | source rows | firms | address |
|---|---|---|---|
| **CO-LOCATED** | 226, 470 | Maral Labs / The Madras Pharmaceuticals | 137-B, Old Mahabalipuram Road, Karapakkam, Chennai -... |
| **EXACT DUPLICATE** | 450, 520 | Sundaram Care Product / Sundaram Care Product | 202-A/8, Srivilliputtur Road, Sankarapandiapuram, Ch... |
| **SAME ENTITY** | 331, 332 | Reckitt Benckiser (India) Private Limited / Reckitt Benckiser Limited | 176, Sipcot Complex, Hosur - 635 126... |
| **SAME ENTITY** | 464, 465 | Tagros Chemicals India Private Limited (BULK), / Tagros Chemicals India Private Limited | No- A4/1, A4/2, Sipcot Industrial Complex, Pachayank... |

- **EXACT DUPLICATE** -- identical name *and* address. Violates the stated grain.
- **SAME ENTITY** -- one firm, two spellings (legal suffix, qualifier). Should be merged, but that is a human call, so it is flagged.
- **CO-LOCATED** -- genuinely different firms sharing a building. Correct as-is. An address-only dedup would have wrongly merged these, which is why this is a flag and not a deletion.

`same_entity_suspect_flag` -> True on **6 rows**.

## 3. The grain violation

Rows violating the stated `(name, address)` grain: **2**

```
 __source_row                  name form_25_licence_no form_28_licence_no form_28d_licence_no
          450 Sundaram Care Product               1125                NaN                 NaN
          520 Sundaram Care Product                NaN         TN00004714                 NaN
```

One establishment, split across two rows -- one per licence type. The grain was never `(name, address)`; for this pair it is `(name, address, licence type)`.

## 4. What it does to the numbers

| Licence | as reported | de-duplicated | delta |
|---|---:|---:|---:|
| `form_25_licence_no` | 487 | 487 | +0 |
| `form_28_licence_no` | 265 | 265 | +0 |
| `form_28d_licence_no` | 4 | 4 | +0 |

| **establishments** | 549 | 548 | -1 |

**The licence counts do not move.** The two duplicated rows hold different licence types -- Form 25 on one, Form 28 on the other -- so collapsing them removes a row without removing a licence.

What DOES move is the establishment count: **549 -> 548**, and every per-establishment percentage with it. The report's '532 of 549 establishments (96.9%)' becomes 531 of 548 (96.9%) -- the same to one decimal place.

**Stated plainly: the numerical impact here is negligible.** The defect is not the size of the error. It is that an untested assertion in Stage 1 silently shaped what Stage 4.11 looked for, and nothing downstream was built to catch that. On a different register -- one where duplicates share licence types -- the same blind spot would produce a materially wrong count.

## 5. The corrected grain statement

Replacing the false claim in `01_business_brief.yaml`:

```yaml
grain: >
  One row per registered manufacturing establishment record: a (firm name, manufacturing
  address) pair with its Form 25 / 28 / 28D licence status.

  MEASURED, not assumed: address is NEAR-unique -- 545 distinct addresses across 549 rows.
  Four addresses are shared by two rows each:
    - 1 pair is an EXACT duplicate on (name, address)  -> violates this grain; one
      establishment split across two rows, one per licence type (source rows 450, 520)
    - 2 pairs are the SAME entity under two legal spellings (Reckitt Benckiser, Tagros)
    - 1 pair is two genuinely different firms sharing a building (Maral Labs /
      The Madras Pharmaceuticals) -- correct as-is, must NOT be merged

  Consequence: any per-establishment count must be computed on de-duplicated
  (name, address) keys, not on a raw row count.
```

## 6. Root cause

The duplicate check was built on one axis only: *same name, different address* -- typo-style. The real pattern in this register is the opposite: *same address, differently-written name*, caused by legal-entity suffixes (`Ltd` vs `(India) Private Limited`), qualifiers (`(BULK)`) and trailing punctuation.

It was pointed at the wrong axis, and it was pointed there **because Stage 1 said the other axis was already unique.**

This is the pipeline's own central failure mode -- trusting a claim instead of re-deriving it -- occurring one level above where the checks look. Stage 5 verifies what Stage 4 did. Nothing verified what Stage 1 asserted.

**The generalisable fix:** every empirical claim in the brief should carry the check that produced it, and Stage 3 should re-run those checks rather than reading the conclusion.

---

## Files

- `cleaned_data.csv` -- two flag columns added: `shared_address_flag`, `same_entity_suspect_flag`. **No rows removed, no values changed.**
- `cleaned_data.pre_address_fix.csv` -- the pre-fix copy.
- `07_address_axis_correction.md` -- this report.