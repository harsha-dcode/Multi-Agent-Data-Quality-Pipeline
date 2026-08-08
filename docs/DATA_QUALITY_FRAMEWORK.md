# Data Quality Framework

How this pipeline decides what to change, what it refuses to change, and how it
proves — after the fact — that it did not corrupt the data.

The organising principle:

> **A step reporting success is not evidence that it worked.**
> Every operation that rewrites values is followed by a check on the resulting
> *distribution*, not on the operation's own return code.

This document describes the four control layers that implement that principle.

---

## Layer 0 — The data contract (`01_business_brief.yaml`)

Nothing runs until a machine-readable contract exists for the dataset. It is a
**mandatory artifact**, not an optional planning step: the run gate fails a run
whose brief is missing, and the contract is written *before* profiling so it
cannot be quietly reverse-engineered from whatever the data happens to contain.

### Required keys

| Key | Purpose | Failure it prevents |
|---|---|---|
| `dataset` | Identity and source of the file | Silent input swap between runs |
| `grain` | What exactly one row represents | Aggregation over the wrong unit; double counting |
| `critical_columns` | Columns whose loss invalidates the deliverable | Filtering away the analysis key |
| `allowed_values` | Closed code sets, looked up — never inferred | Canonical values invented from frequency |
| `dangerous_columns` | Columns unsafe for automated correction | Fuzzy matching a closed code set |
| `missing_value_strategy` | Imputation policy, **per column** | Blanket imputation fabricating values |

### Why `missing_value_strategy` is per column

This is the single most load-bearing rule in the framework, and it exists
because of a measured failure. A blanket policy of the form:

```yaml
missing_value_strategy:      # ← REJECTED by the run gate
  categoricals: mode
  numerics: median
```

is what authorised **6,126 fabricated cells** in an earlier run of this
pipeline. A blanket rule cannot distinguish a column where "unknown" is a
recoverable nuisance from one where a guessed value is a clinical or financial
assertion. So the schema forbids the shortcut and requires a decision per
column:

```yaml
missing_value_strategy:
  admission_date:  never_impute      # a guessed date reorders the timeline
  billing_amount:  never_impute      # a revenue factor; a guess is a fabricated number
  blood_type:      never_impute      # closed code set; mode-fill skews the distribution
  insurance_plan:  literal_unknown   # "Unknown" is a real, reportable category
```

`never_impute` is the default posture for **identifiers, revenue factors, and
closed code sets**. Nulls in those columns survive to the output and are
reported as nulls — an honest gap beats a plausible invention.

The gate (`check_run_complete.py`) detects blanket keys explicitly and fails
the run with the reason attached.

### Empty is a valid answer; absent is not

`dangerous_columns: {}` means *"the guard ran and nothing tripped."*
`dangerous_columns` missing entirely means *"nobody checked"* — and those two
states are indistinguishable to a downstream reader unless the schema forces
the distinction. The gate treats absence as a failure and emptiness as a pass.
That asymmetry is deliberate.

---

## Layer 1 — Guardrails that refuse to act

Guardrails run **before** a transformation and can veto it.

### The fuzzy-matching collision guard

The defect that shaped this project: fuzzy string matching silently rewrote
**28,736 blood-type values**, and the cleaning log recorded it as a success —
*"typos corrected."*

**Mechanism.** Fuzzy-matching libraries preprocess strings before scoring, and
the default preprocessor strips non-alphanumeric characters. `A+` and `A-` both
reduce to `a`, and therefore score **100 against each other**. At an 85%
auto-correct threshold every negative blood type was snapped onto its positive
counterpart. From the log's point of view, the corruption *was* the correction.

**The guard** — run against the canonical list before any fuzzy pass:

```python
from thefuzz import utils

def canonicals_collide(canonical_list):
    """True => two canonical values are indistinguishable after preprocessing."""
    keys = [utils.full_process(str(c)) for c in canonical_list]
    return len(set(keys)) < len(keys)
```

If it returns `True`, the column is **not** fuzzy matched. It falls back to
exact, case-insensitive matching, and the refusal is written into the report
rather than being silently handled.

**A subtlety worth knowing:** passing a punctuation-preserving `processor=` is
*not* sufficient. `token_sort_ratio` re-strips internally via its own
`full_process=True` default, so the scorer must be bound with
`full_process=False` as well. A guard that looks correct and isn't is worse
than no guard.

### Closed code sets are looked up, not derived

The second guard is a rule rather than code:

> For a closed code set — blood types, ISO country codes, seller grades, sizes,
> shipment statuses — the canonical list is **a fact you look up**, not a
> statistic you derive from the data.

Inferring canonicals by frequency picks `A+` over `A-` on a coin-flip margin
and then rewrites the loser out of existence. Where a genuine tie exists — one
dataset here has region counts of 250/250/249/232, with the top two *exactly*
tied — mode-based imputation is not merely risky, it is a coin flip promoted to
a data value. The brief marks such columns `never_impute` and the pipeline
honours it.

### Impossible values are decided per column, never by `abs()`

Applying `abs()` to negative numbers is the archetypal plausible-looking fix
that destroys meaning. A negative `length_of_stay` is a data error. A negative
`billing_amount` may be **a refund** — a real, correct, business-meaningful
value. Blanket sign correction converts refunds into charges and moves revenue
totals in the wrong direction.

Each column carrying impossible values gets its own written decision, its own
change reason, and its own line in the change log.

---

## Layer 2 — Verification after the fact

Guardrails prevent known failures. Verification catches unknown ones.

### Post-transformation distribution checks

After **any** operation that rewrites values, the pipeline re-derives the
distribution and compares it to the pre-operation state. Two checks run on
every categorical column:

```python
# 1. Did any canonical value disappear entirely?
missing_canon = [c for c in canon if c not in df[col].values]

# 2. Did any category's share move more than tolerance?
drift = (post_share - pre_share).abs().max()
```

A canonical value that *vanishes* is the signature of a bad fuzzy snap, and no
"N corrections applied" log line can reveal it. This check is what originally
caught the blood-type corruption — not the log.

### Why the check belongs on every write path, not just fuzzy matching

Re-auditing this pipeline's own healthcare run found the same class of failure
arriving through a **second door**: mode-imputation filled 639 nulls with `A+`,
moving its share from 12.59% to 13.47% against a uniform expectation of 12.50%.
The fuzzy path was guarded. The imputation path was not. Same corruption, a
different entry point, and the log again reported success.

The generalisation — now applied pipeline-wide — is that distribution checks
attach to *value-writing steps*, not to *specific algorithms*.

### Filter vs keep

Stage 8 decides which rows survive into the visualization-ready dataset. The
rule is narrow on purpose:

- **Filter** only what is *physically impossible* — a discharge before its
  admission, a delivery before its dispatch, a null in a column the chart is
  keyed to.
- **Keep** everything that is merely a *statistical* oddity — age > 110,
  unresolved fuzzy candidates, cross-check mismatches, near-duplicate keys
  without an identifier to confirm them.

This produces a small, per-column-defensible drop rate instead of a blanket
outlier scrub. "We removed the outliers" is not a defensible sentence in a
review; "we removed 41 rows whose discharge preceded admission, listed here" is.

---

## Layer 3 — The deterministic run gate

Guards and checks live partly in an agent specification, and an agent can skip
an instruction. `check_run_complete.py` is the backstop that cannot be talked
out of anything: plain Python, no model in the loop, exit code 1 on failure.

It enforces:

1. **Artifact completeness** — all six required artifacts exist and exceed a
   minimum plausible size (a 40-byte "report" is a missing report).
2. **Contract validity** — the brief parses, carries all six required keys, and
   does not use blanket `missing_value_strategy` keys.
3. **Audit-trail integrity** — the change log has `column`, `change_type` and
   `original_value` fields and a non-zero row count. Without `original_value`
   the log cannot reconstruct the input, which makes it a summary, not an audit
   trail.

Optional keys are reported as advisory and never fail a run: an omitted
optional key is an honest *"not established"*, and punishing honesty trains the
wrong behaviour.

### Why a separate gate at all

The pipeline uses a language model to decide *which* operations run. That
selection is **not deterministic across runs** — in an earlier comparison, the
logistics dataset received all 12 validation checks while the healthcare
dataset received 5, from the same agent and the same specification.

Determinism in the executor does not buy determinism in the deliverable. The
gate is the mechanism that turns "the agent was asked to do this" into "the run
does not pass unless it did."

---

## The audit trail

Every cell change is logged at row level:

| Field | Meaning |
|---|---|
| `__source_row` | 0-indexed position among the source data rows (header excluded), assigned at extraction |
| `column` | Column changed |
| `change_type` | Operation class (`NULL_STANDARDISED`, `DATE_PARSED`, `NEGATIVE_CORRECTED`, …) |
| `original_value` | Verbatim original text |
| `new_value` | Value written |
| `reason` | Why the change was authorised |

The binding requirement is **reconstruction**: the original dataset must be
recoverable from the cleaned dataset plus the change log. A log that records
*"6,126 nulls imputed"* satisfies a metric and fails the requirement.

`__source_row` is assigned at extraction, before deduplication and reordering,
because it can only be assigned truthfully there. Added later, it is a guess.

### The extraction rule that makes the audit trail possible

Data is loaded with **no inference at all**:

```python
pd.read_csv(path, dtype=str, keep_default_na=False)
```

Loading with pandas defaults converts *some* disguised nulls (`N/A`, `null`,
`None`, `#N/A`) to `NaN` while leaving others (`tbd`, `-`, `?`, `unknown`) as
literal strings. On one 1,265-row benchmark file that split 730 disguised nulls
into **414 destroyed and 316 surviving** — the same concept in two incompatible
representations, and 414 change-log entries that can never be written because
the original text no longer exists.

The audit trail therefore breaks at *load time*, before any cleaning happens,
and nothing downstream can repair it. Every conversion is instead performed
deliberately in the cleaning stage, where it is logged.

---

## Summary of controls

| Control | Type | Prevents |
|---|---|---|
| Business brief required | Contract | Undocumented, unreviewable cleaning decisions |
| Per-column `missing_value_strategy` | Contract | Blanket imputation fabricating values |
| `never_impute` on IDs / revenue / code sets | Contract | Guessed values in load-bearing columns |
| Collision guard | Guardrail | Fuzzy matching collapsing a closed code set |
| Canonicals looked up, not derived | Guardrail | Coin-flip canonical selection |
| Per-column impossible-value decisions | Guardrail | `abs()` converting refunds into charges |
| `dtype=str, keep_default_na=False` | Guardrail | Evidence destroyed at load time |
| Missing-canonical check | Verification | Bad fuzzy snaps invisible to logs |
| Distribution drift check | Verification | Imputation skewing category shares |
| Physical-impossibility-only filtering | Verification | Indefensible blanket outlier removal |
| `check_run_complete.py` | Gate | An agent skipping any of the above |
