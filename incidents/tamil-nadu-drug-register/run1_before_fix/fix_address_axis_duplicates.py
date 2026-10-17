#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fix_address_axis_duplicates.py -- correct a Stage 1 assumption that was never tested.

THE DEFECT
----------
01_business_brief.yaml line 8 asserted:

    "Confirmed empirically: ADDRESS is 100% unique across all 549 rows"

It is not. There are 545 distinct addresses across 549 rows: 4 addresses are
shared by 2 establishments each.

Because the brief asserted uniqueness, the 4.11 duplicate check was built on a
single axis -- "same name, slightly different address" (typo-style). It never
looked at the opposite and more common real-world pattern: "same address,
differently-written name" (legal-entity suffixes, qualifiers, trailing commas).

CONSEQUENCE
-----------
One pair -- Sundaram Care Product, rows 450 and 520 -- has an IDENTICAL name and
address. That violates the stated grain of (name, address) outright, and it is
one establishment recorded twice, once per licence type.

MEASURED IMPACT: the licence COUNTS are unaffected (+0 on all three), because the
two rows hold different licence types and do not overlap. The ESTABLISHMENT count
is inflated by one: 549 -> 548. Any per-establishment percentage shifts slightly.

WHAT THIS SCRIPT DOES
---------------------
1. Tests the uniqueness claim instead of asserting it.
2. Adds an ADDRESS-AXIS duplicate flag alongside the existing name-axis one.
3. Classifies each shared-address pair: same entity, or genuinely co-located.
4. Recomputes the licence counts on a de-duplicated establishment basis and
   reports the delta.
5. Writes a correction report. Changes NOTHING destructively -- flags only,
   per the same rule the rest of the pipeline follows.

Output: 07_address_axis_correction.md
        cleaned_data.csv  (two flag columns added, no rows removed, no values changed)
"""
import re
import shutil
import pandas as pd
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLEANED = HERE / "cleaned_data.csv"
REPORT = HERE / "07_address_axis_correction.md"

out = []


def w(s=""):
    out.append(str(s))
    print(s)


df = pd.read_csv(CLEANED, low_memory=False)
n = len(df)

w("# Address-axis duplicate correction")
w()
w("Corrects an untested Stage 1 assumption. Found by external review, not by the pipeline.")
w()

# ---------------------------------------------------------------- 1. test the claim
w("## 1. The claim, tested")
w()
w("The brief asserted ADDRESS is 100% unique. Testing it:")
w()
w("```")
w(f"rows                : {n}")
w(f"distinct addresses  : {df['address'].nunique()}")
w(f"shared addresses    : {n - df['address'].nunique()}")
w("```")
w()
verdict = "FALSE" if df["address"].nunique() < n else "true"
w(f"**The claim is {verdict}.** The brief said 'confirmed empirically' for something that was "
  f"asserted, not measured.")
w()

# ---------------------------------------------------------------- 2. the address axis
w("## 2. The address-axis check the pipeline never ran")
w()

addr_dup = df.duplicated("address", keep=False)
df["shared_address_flag"] = addr_dup
w(f"`shared_address_flag` -> True on **{int(addr_dup.sum())} rows** across "
  f"{df.loc[addr_dup, 'address'].nunique()} addresses.")
w()


def norm_name(s):
    """Strip legal-entity noise so two spellings of one firm compare equal."""
    s = str(s).lower()
    s = re.sub(r"\(.*?\)", " ", s)                       # (india), (bulk)
    s = re.sub(r"\b(private|pvt|limited|ltd|company|co|inc|llp)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


df["_nname"] = df["name"].map(norm_name)

rows = []
for addr, g in df[addr_dup].groupby("address"):
    names = list(g["name"])
    nnames = set(g["_nname"])
    if len(nnames) == 1:
        kind = "SAME ENTITY" if len(set(names)) > 1 else "EXACT DUPLICATE"
    else:
        kind = "CO-LOCATED"
    rows.append((kind, list(g["__source_row"]), names, addr))

w("| Verdict | source rows | firms | address |")
w("|---|---|---|---|")
for kind, srs, names, addr in sorted(rows):
    w(f"| **{kind}** | {', '.join(map(str, srs))} | {' / '.join(names)} | {addr[:52]}... |")
w()
w("- **EXACT DUPLICATE** -- identical name *and* address. Violates the stated grain.")
w("- **SAME ENTITY** -- one firm, two spellings (legal suffix, qualifier). Should be merged, "
  "but that is a human call, so it is flagged.")
w("- **CO-LOCATED** -- genuinely different firms sharing a building. Correct as-is. An "
  "address-only dedup would have wrongly merged these, which is why this is a flag and not "
  "a deletion.")
w()

same_entity = {sr for kind, srs, _, _ in rows if kind in ("SAME ENTITY", "EXACT DUPLICATE")
               for sr in srs}
df["same_entity_suspect_flag"] = df["__source_row"].isin(same_entity)
w(f"`same_entity_suspect_flag` -> True on **{int(df['same_entity_suspect_flag'].sum())} rows**.")
w()

# ---------------------------------------------------------------- 3. grain violation
w("## 3. The grain violation")
w()
grain_dup = df.duplicated(subset=["name", "address"], keep=False)
w(f"Rows violating the stated `(name, address)` grain: **{int(grain_dup.sum())}**")
w()
if grain_dup.any():
    cols = [c for c in ["__source_row", "name", "form_25_licence_no", "form_28_licence_no",
                        "form_28d_licence_no"] if c in df.columns]
    w("```")
    w(df[grain_dup][cols].to_string(index=False))
    w("```")
    w()
    w("One establishment, split across two rows -- one per licence type. The grain was never "
      "`(name, address)`; for this pair it is `(name, address, licence type)`.")
w()

# ---------------------------------------------------------------- 4. the count impact
w("## 4. What it does to the numbers")
w()

lic_cols = [c for c in df.columns if c.endswith("_licence_no")]
before = {}
for c in lic_cols:
    before[c] = int(df[c].notna().sum())

# collapse exact-grain duplicates: one establishment, licences unioned
dedup = df.copy()
key = dedup["name"].str.strip() + "||" + dedup["address"].str.strip()
agg = {c: (lambda s: s.notna().any()) for c in lic_cols}
collapsed = dedup.groupby(key).agg(agg)

w("| Licence | as reported | de-duplicated | delta |")
w("|---|---:|---:|---:|")
for c in lic_cols:
    a, b = before[c], int(collapsed[c].sum())
    w(f"| `{c}` | {a} | {b} | {b - a:+d} |")
w()
w(f"| **establishments** | {n} | {len(collapsed)} | {len(collapsed) - n:+d} |")
w()
w("**The licence counts do not move.** The two duplicated rows hold different licence "
  "types -- Form 25 on one, Form 28 on the other -- so collapsing them removes a row "
  "without removing a licence.")
w()
w(f"What DOES move is the establishment count: **{n} -> {len(collapsed)}**, and every "
  f"per-establishment percentage with it. The report's '532 of 549 establishments "
  f"(96.9%)' becomes 531 of 548 (96.9%) -- the same to one decimal place.")
w()
w("**Stated plainly: the numerical impact here is negligible.** The defect is not the size "
  "of the error. It is that an untested assertion in Stage 1 silently shaped what Stage "
  "4.11 looked for, and nothing downstream was built to catch that. On a different "
  "register -- one where duplicates share licence types -- the same blind spot would "
  "produce a materially wrong count.")
w()

# ---------------------------------------------------------------- 5. corrected grain
w("## 5. The corrected grain statement")
w()
w("Replacing the false claim in `01_business_brief.yaml`:")
w()
w("```yaml")
w("grain: >")
w("  One row per registered manufacturing establishment record: a (firm name, manufacturing")
w("  address) pair with its Form 25 / 28 / 28D licence status.")
w("")
w("  MEASURED, not assumed: address is NEAR-unique -- 545 distinct addresses across 549 rows.")
w("  Four addresses are shared by two rows each:")
w("    - 1 pair is an EXACT duplicate on (name, address)  -> violates this grain; one")
w("      establishment split across two rows, one per licence type (source rows 450, 520)")
w("    - 2 pairs are the SAME entity under two legal spellings (Reckitt Benckiser, Tagros)")
w("    - 1 pair is two genuinely different firms sharing a building (Maral Labs /")
w("      The Madras Pharmaceuticals) -- correct as-is, must NOT be merged")
w("")
w("  Consequence: any per-establishment count must be computed on de-duplicated")
w("  (name, address) keys, not on a raw row count.")
w("```")
w()

# ---------------------------------------------------------------- 6. root cause
w("## 6. Root cause")
w()
w("The duplicate check was built on one axis only: *same name, different address* -- "
  "typo-style. The real pattern in this register is the opposite: *same address, "
  "differently-written name*, caused by legal-entity suffixes (`Ltd` vs `(India) Private "
  "Limited`), qualifiers (`(BULK)`) and trailing punctuation.")
w()
w("It was pointed at the wrong axis, and it was pointed there **because Stage 1 said the "
  "other axis was already unique.**")
w()
w("This is the pipeline's own central failure mode -- trusting a claim instead of re-deriving "
  "it -- occurring one level above where the checks look. Stage 5 verifies what Stage 4 did. "
  "Nothing verified what Stage 1 asserted.")
w()
w("**The generalisable fix:** every empirical claim in the brief should carry the check that "
  "produced it, and Stage 3 should re-run those checks rather than reading the conclusion.")
w()

# ---------------------------------------------------------------- write
df = df.drop(columns=["_nname"])
shutil.copy(CLEANED, HERE / "cleaned_data.pre_address_fix.csv")
df.to_csv(CLEANED, index=False, encoding="utf-8")

w("---")
w()
w("## Files")
w()
w("- `cleaned_data.csv` -- two flag columns added: `shared_address_flag`, "
  "`same_entity_suspect_flag`. **No rows removed, no values changed.**")
w("- `cleaned_data.pre_address_fix.csv` -- the pre-fix copy.")
w("- `07_address_axis_correction.md` -- this report.")

REPORT.write_text("\n".join(out), encoding="utf-8")
print(f"\nwrote {REPORT}")
