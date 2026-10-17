# Multi-Agent Data Quality Pipeline

![CI](https://img.shields.io/badge/CI-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![Tests](https://img.shields.io/badge/tests-36%2F36-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

**An agent-orchestrated data quality pipeline that treats "the cleaning step
reported success" as an unverified claim.**

A language model decides *what* to clean and *why*. Python executes every
transformation deterministically. A guardrail layer can veto a transformation
before it runs, a verification layer re-derives the result afterwards, and a
model-free gate refuses to publish a run that skipped any of it.

---

## The problem this exists to solve

Data cleaning fails silently. A pipeline that corrupts a column and a pipeline
that repairs it produce the same log line: *"1,284 values corrected."* By the
time a dashboard is wrong, the evidence needed to prove what happened has
already been overwritten.

This project is built around one such failure, measured on the `healthcare`
dataset in this repository:

> Fuzzy string matching will silently rewrite **28,736 blood-type values** on
> this 58,164-row dataset — and the cleaning log will record it as a success.

`A+` and `A-` both reduce to `a` under the default fuzzy preprocessor and
therefore score **100 against each other**. At an 85% auto-correct threshold,
every negative blood type is snapped onto its positive counterpart. From the
log's point of view, the corruption *is* the correction.

The collision guard caught it before a single value was rewritten —
[`02c_collision_guard_report.txt`](case_studies/healthcare/02c_collision_guard_report.txt)
records all four ± pairs collapsing to the same key (`A+/A-`, `B+/B-`,
`AB+/AB-`, `O+/O-`), each scoring 100. The 28,736 figure is the count of
negative blood types actually present: 7,232 `AB-`, 7,207 `B-`, 7,188 `A-`,
7,109 `O-`.

Nothing else catches it. Not a log, not a report, not a return code — only
checking the value distribution afterwards and noticing `A-` had nearly
vanished. That single fact determined the architecture of everything here.

---

## Benchmark results

Five datasets, **141,911 rows across 122 columns**, run by the **same agent
specification with no per-dataset tuning**. Every run is unattended: no human
answered a question mid-run, and every judgment call is written into the run's
own report.

| Case study | Rows in → cleaned → viz-ready | Drop rate | Log entries | Value edits | Validation | Gate |
|---|---|---:|---:|---:|---|:--:|
| [`healthcare`](case_studies/healthcare/) | 58,164 → 55,874 → 54,470 | 2.51% | 154,302 | 17,062 | 10 pass, 2 N/A, **1 fail by design** | PASS |
| [`housing`](case_studies/housing/) | 50,000 → 49,864 → 48,870 | 1.99% | 11,068 | 2,783 | 11 pass, 2 N/A, 0 fail | PASS |
| [`logistics`](case_studies/logistics/) | 30,102 → 30,000 → 29,354 | 2.15% | 53,388 | 3,617 | 11 pass, 2 N/A, 0 fail | PASS |
| [`sales`](case_studies/sales/) | 312 → 281 → 266 | 5.34% | 1,824 | 1,631 | 12 pass, **1 fail by design** | PASS |
| [`telecom`](case_studies/telecom/) *(control)* | 3,333 → 3,333 → 3,333 | 0.00% | 615 | **0 data values** | 11 pass, 2 N/A, 0 fail | PASS |
| **Total** | **141,911 rows** | | **220,521** | **25,093** | | **5/5** |

### Read the last two columns before the big numbers

**220,521 log entries, 25,093 actual value changes.** Roughly **89% of the
audit trail records what the pipeline found and deliberately did not touch** —
outliers flagged, anomalies investigated and left alone, impossible values
reported rather than "fixed."

That ratio is the deliverable. A cleaning tool is easy to judge by how much it
changes; it should be judged by whether it changed the right things and can
prove which.

**`telecom` is a control case.** It is already clean, so **zero data values
were corrected** — its 615 log entries are 602 flagged anomalies, 11 header
renames, a derived column and a reorder. A pipeline that always reports changes
is indistinguishable, from its output alone, from one that fabricates them.
Showing a small number on a clean dataset is the harder claim, and it is what
makes the other four credible.

**Two validation failures are deliberate and kept.** Check V2 requires critical
columns to be null-free. The data contract marks those columns `never_impute`.
So the honest result is a *failing check with real nulls surviving*, not a
passing check bought with invented values. A pipeline whose checks always pass
has checks that aren't load-bearing.

---

## Impact

### 1. Silent corruption prevented — measured, not projected

Each of these produces a *correct-looking* output. None is visible in a row
count, a completion message, or a green checkmark.

| Corruption prevented | Scale | Caught by |
|---|---:|---|
| Blood types collapsed `A- → A+` | **28,736 values** | Collision guard (`healthcare`) |
| Every currency merged into one | **all ₹ £ $ €** | Collision guard (`housing`) |
| `listing_price` wrongly divided by 10/100 | **370 rows** | Cross-check vs `final_sale_price` |
| `shipment_weight_kg` distribution reshaped | **6.75% of column** | Repair-rate dry-run gate (`logistics`) |
| Valid dates silently turned into `NaT` | **37 rows** | Before/after null-count assertion (`sales`) |
| Values fabricated by blanket imputation | **6,126 cells** | Per-column contract + run gate |

Cost of *not* catching the blood-type case: a clinical dataset where 28,736
patients carry the wrong blood type, and no record that it ever changed.

### 2. Upstream bugs surfaced — defects the cleaning log exposed in the *source system*

The audit trail's second job is diagnostic. Cleaning patterns are evidence
about the process that produced the data, and these came out of the
`healthcare` run:

- **Probable ingest double-write** — 9,227 of 54,470 rows (**16.94%**) share a
  full name + date + doctor + hospital key across 4,635 groups. Not plausibly
  legitimate repeat admissions; flagged for investigation of the ingest path.
- **Two column-swap bugs at the export source** — `gender ↔ blood_type` and
  `test_results ↔ medication`. The pipeline mechanically un-swapped 276 rows,
  but 27 residual rows recur *every run* until the exporter is fixed. Nobody
  types `B+` into a gender field.
- **A $2,150,403.83 reporting decision made visible** — 190 rows carry negative
  `billing_amount`. Including or excluding them moves total billing by
  **0.157%**, and the pipeline refused to `abs()` them because a negative
  charge may be a legitimate refund. Without that refusal, $2.15M would have
  silently moved in the wrong direction with no flag and no decision point.

A cleaning pipeline that only cleans hands back a tidy file. This one hands
back a tidy file *and* a list of things to fix upstream so the mess stops being
regenerated.

### 3. Time

**Measured.** All five datasets — 141,911 rows, 122 columns — profiled,
cleaned, validated, audited and analysed in **2h 18m of total compute**, or
**~37 minutes of wall-clock** running in parallel. Zero human inputs during
the runs.

**Estimated.** A conservative manual baseline of **one analyst-day per dataset**
— profiling, cleaning, validating and documenting to the same evidence standard,
including a row-level audit trail and a statistical insights report — puts the
same five deliverables at roughly **5 analyst-days (~40 hours)**.

| | Manual (estimated) | This pipeline (measured) |
|---|---|---|
| Five datasets end-to-end | ~40 hours | **~37 min wall-clock** |
| Audit trail | Rarely produced at all | 220,521 entries, reconstructable |
| Re-running after a source change | Full repeat | Re-execute numbered scripts |

Two honest caveats: the 40-hour figure is an **estimate from stated
assumptions**, not a measured control — judge it by whether the assumption is
reasonable, and adjust it if your team is faster. And the output still needs
human review; the pipeline compresses the work of *producing and evidencing* a
clean dataset, not the work of deciding whether to trust it. What it removes
entirely is the part analysts actually lose days to — re-deriving what changed,
and why, after the fact.

### 4. Reusability

The marginal cost of the sixth dataset is a business brief. The same
specification ran unmodified across healthcare, real-estate, supply-chain,
telecom and e-commerce data — **19 to 46 columns, 312 to 58,164 rows** — with
no per-dataset code.

---

## How each one was caught

Every one of these was caught by the pipeline's own guards **during the five
runs published here** — each documented in the case study where it occurred,
not reconstructed afterwards.

| Guard | Incident |
|---|---|
| **Collision guard** (`healthcare`) | `blood_type` — all four ± pairs (`A+/A-`, `B+/B-`, `AB+/AB-`, `O+/O-`) reduce to the same preprocessed key and score 100 against each other. Fuzzy refused; 28,736 negative blood types left intact. |
| **Collision guard** (`housing`) | `currency` — ₹ £ $ € all strip to the same empty key, so fuzzy matching would have merged every currency into one. Fuzzy refused; exact matching used. |
| **Cross-column check** (`housing`) | A decimal-typo repair was about to divide 370 `listing_price` rows by 10/100. Cross-checking against `final_sale_price` (421 of 427 candidates in the normal ratio band) stopped it *before* it wrote. |
| **Repair-rate dry-run gate** (`logistics`) | The >1% safety check was only *printing* a warning while still applying the fix. Restructured into dry-run-then-gate; four columns ended with repair stopped and reported, 9,310 rows flagged instead of rewritten. |
| **Null-count assertion** (`sales`) | `pd.to_datetime()` re-parsing an already-formatted mixed date column silently produced 37 `NaT`s. Caught by a before/after assertion that is now permanent. |
| **Second dedup pass** (`healthcare`) | Dropping three distrusted derived columns collapsed 34 row-pairs that had differed only in those columns — invisible until a post-transform check looked again. |

Every one of these produces a *correct-looking* output. None is visible in a row
count, a completion message, or a green checkmark.

---

## Architecture

```
                   ┌─────────────────────────────────────────┐
   Raw CSV  ──────▶│  L0  DATA CONTRACT   01_business_brief  │
                   │      per-column policy, written FIRST   │
                   └────────────────┬────────────────────────┘
                                    ▼
                   ┌─────────────────────────────────────────┐
                   │  L1  GUARDRAILS      can VETO a change  │
                   │      collision guard · closed code sets │
                   │      per-column impossible-value rules  │
                   └────────────────┬────────────────────────┘
                                    ▼
   ┌────────────────────┐   ┌───────────────────────────────┐
   │  DECISION LAYER    │──▶│  EXECUTION LAYER              │
   │  LLM: what & why   │   │  Python: deterministic apply  │
   └────────────────────┘   └───────────────┬───────────────┘
                                    ▼
                   ┌─────────────────────────────────────────┐
                   │  L2  VERIFICATION    re-derives result  │
                   │      missing-canonical · drift check    │
                   └────────────────┬────────────────────────┘
                                    ▼
                   ┌─────────────────────────────────────────┐
                   │  L3  RUN GATE        no model involved  │
                   │      check_run_complete.py — exit 1     │
                   └────────────────┬────────────────────────┘
                                    ▼
              cleaned_data.csv · viz_ready.csv · change_log.csv
              validation_report.md · insights_report.md
```

**Why the split.** Deciding whether `length_of_stay = -3` is a sign error or a
corrupt record needs context and judgment. Applying that decision across 58,000
rows needs exactness and repeatability. Optimising one process for both
produces something bad at each.

**Where the guarantee stops.** The executor is deterministic; the model's
*selection* of operations is not. In an earlier comparison one dataset received
all 12 validation checks and another received 5, from the same specification.
Determinism in the executor does not buy determinism in the deliverable — which
is precisely why L3 exists as plain Python that cannot be talked out of
anything.

📖 **[Data Quality Framework](docs/DATA_QUALITY_FRAMEWORK.md)** — the four
control layers in full
📖 **[Engineering Decisions](docs/ENGINEERING_DECISIONS.md)** — 7 ADRs, rejected
alternatives, costs accepted, known limitations

---

## The data contract

Nothing runs until a machine-readable contract exists. It is a **mandatory
artifact**, not a planning note — the gate fails a run whose brief is missing,
and it is written *before* profiling so it cannot be reverse-engineered from
whatever the data happens to contain.

```yaml
missing_value_strategy:              # per column — NEVER blanket
  admission_date:  never_impute      # a guessed date reorders the timeline
  billing_amount:  never_impute      # revenue factor; a guess is a fabricated number
  blood_type:      never_impute      # closed code set; mode-fill skews the distribution
  insurance_plan:  literal_unknown   # "Unknown" is a real, reportable category
```

A blanket rule — `{categoricals: mode, numerics: median}` — is what authorised
**6,126 fabricated cells** in an earlier run of this pipeline. The gate detects
blanket keys explicitly and fails the run with the reason attached.

The schema also distinguishes **empty from absent**: `dangerous_columns: {}`
means the guard ran and nothing tripped; a missing key means nobody checked.
Collapsing those two states would let a skipped check masquerade as a clean one.

---

## The audit trail

Every changed cell is logged at row level, with the binding requirement that
**the original dataset be reconstructable from the cleaned dataset plus the
log**. A log that says *"6,126 nulls imputed"* satisfies a metric and fails the
requirement.

| Field | Meaning |
|---|---|
| `SOURCE_ROW` | 0-indexed position in the source data rows, assigned at extraction |
| `COLUMN` / `CHANGE_TYPE` | What changed and which operation class |
| `ORIGINAL_VALUE` / `NEW_VALUE` | Verbatim before and after |
| `REASON` | Why the change was authorised |

**Verified, not asserted.** For the `logistics` run, all **230** logged
null-standardisation entries on `Actual_Delivery_Date` map **230/230** onto the
230 cells that are genuinely empty in the raw file. The audit trail resolves
back to the source bytes.

This is only possible because extraction infers nothing:

```python
pd.read_csv(path, dtype=str, keep_default_na=False)
```

Default loading converts *some* disguised nulls to `NaN` and leaves others as
strings. Measured on the `sales` file: a naive load destroys **87 of 3,432
cells (2.53%)** with no record of their original text — breaking the audit
trail at *load time*, before any cleaning happens, in a way nothing downstream
can repair.

---

## What every run produces

```
case_studies/<name>/
├── RUN_SUMMARY.md          # headline numbers, verifiable against the artifacts
├── 01_business_brief.yaml  # the data contract
├── change_log.csv          # row-level audit trail
├── validation_report.md    # each check by name, with its result
├── insights_report.md      # Stage 9 statistical analysis
├── cleaned_data.csv        # cleaned output
├── viz_ready.csv           # filtered, Power BI-ready output
└── NN_*.py                 # numbered scripts — reproducible from this folder alone
```

Scripts are kept, not deleted, so any number in any report can be re-derived by
someone who doesn't trust the report.

---

## Quickstart

```bash
git clone https://github.com/harsha-dcode/Multi-Agent-Data-Quality-Pipeline.git
cd Multi-Agent-Data-Quality-Pipeline
pip install -e .

# Run the deterministic logic tests (no API key needed)
pytest tests/ -v                      # 36 passed

# Verify a published run honours its own contract
python check_run_complete.py case_studies/healthcare
```

`check_run_complete.py` exits non-zero if any required artifact is missing, if
the business brief uses blanket imputation keys, or if the change log lacks the
fields needed to reconstruct the original data. It runs in CI against every
committed case study.

---

## Repository structure

```
.claude/agents/          # Agent specifications — the decision layer (see ADR-7)
  data-pipeline-cleaner.md   # 902 lines — drove all five benchmark runs (v1)
  analytics-expert.md        # Stage 9 analysis; produced every insights_report.md
  pipeline-orchestrator.md   # Interactive 9-stage orchestration variant
case_studies/            # 5 benchmark runs: artifacts + the scripts that made them
src/agent/               # Reusable pipeline tools, exercised by the test suite
docs/                    # Framework, ADRs, architecture, stage reference
tests/                   # 36 logic tests — no API key required
check_run_complete.py    # Model-free run gate
.github/workflows/ci.yml # Tests on 3.10/3.11/3.12 + gate on every case study
```

### How the benchmark runs were actually produced — read this before reviewing

The five case studies were produced by the **agent specification**
(`.claude/agents/data-pipeline-cleaner.md`), which writes a purpose-built,
numbered script per stage for each dataset.

**The five runs predate the current specification.** They were produced under the
8 August version. On 22 September the spec was amended after a run on a Tamil Nadu
drug register shipped a false premise: Stage 1 asserted an address column was 100%
unique, Stage 4.3 then normalised whitespace and case, and four addresses collided.
Validation returned 13/13 PASS, correctly, because every check verifies Stage 4
against Stage 1 — and Stage 1 was the thing that was wrong.

The amendment requires every empirical claim in a brief to carry the expression that
produced it, the number it returned, and the snapshot it was measured on, and requires
Stage 3 to re-run those expressions rather than read their conclusions. The five case
studies here were not run under that rule. They are being re-run one at a time; until
each one is, its brief carries no `verified_by` field and that is a real gap, not an
oversight in the write-up.

**`healthcare` has been re-run (2026-10-17) and the rule fired on it.** Its grain is a
composite over three text columns that Stage 4.3 rewrites, and the duplicate count moves
from 5,968 on raw to 6,911 after normalisation. The cleaned output is unchanged, but 676
of the 2,256 removed rows turn out to have been deleted for reasons not present in the
source file — 527 of them by whitespace collapsing alone. The removals are defensible;
the silence about them was not, and Stage 4 now reports the attribution. The same re-run
exposed two defects in the pipeline itself: Stage 5 was validating the previous run's
output against an incomplete change log, which published a false V11 failure and left
V13 checking 30 of 46 flags; and Stage 7 was writing its change-log entries twice. Both
are fixed and both are written up in
[`case_studies/healthcare/RUN_SUMMARY.md`](case_studies/healthcare/RUN_SUMMARY.md) §13. Those scripts are **kept in the
case-study folder**, so every published number is re-derivable by executing
them — they depend only on `pandas`, `numpy` and `pyyaml`.

They do **not** import `src/`. That is deliberate and worth being explicit
about rather than letting the directory layout imply otherwise:

| Component | Role | Verified by |
|---|---|---|
| `.claude/agents/…md` | The specification — decides what to clean, what to refuse, what to verify | The five runs and their reports |
| `case_studies/*/NN_*.py` | The per-run executor the specification wrote, retained for reproducibility | Re-running them reproduces the artifacts |
| `src/agent/` | Reusable tool implementations (`clean`, `impute`, `correct_dates`, `profile`, `report`) for embedding the pipeline in an SDK/MCP host | `tests/` — 36 tests, green on 3.10/3.11/3.12 |
| `check_run_complete.py` | The gate that publishes or refuses a run | Run against all five case studies in CI |

The agent specification lives in version control because **it is the decision
layer**. A reviewer reading only `src/` sees reusable machinery and none of the
reasoning that determines what gets run.

---

## Known limitations

Stated plainly, because a reviewer will find them anyway.

| Limitation | Status |
|---|---|
| Operation *selection* is non-deterministic across runs | Real. Mitigated by the run gate; not eliminated. |
| Validation coverage varied by run (12 vs 5) | Root cause of the gate. Checks still live partly in the prompt. |
| CSV ingestion only | Extractor interface exists; DB/object-store connectors unimplemented. |
| Single-machine in-memory pandas | Fine to ~10M rows; no distributed execution path. |
| CI covers tests + gate, not end-to-end runs | End-to-end needs API credentials. |
| Two benchmark datasets are synthetic | Injected, counted defects make recall *measurable* — but synthetic defects are not field defects. |

**Roadmap**, ordered by how much each reduces the risk of a silent failure:
move remaining validation checks from the specification into executor code →
property-based tests that generate colliding canonical sets → database and
object-store extractors → incremental runs keyed on `SOURCE_ROW` provenance.

---

## Tech stack

`Python 3.10+` · `pandas` · `NumPy` · `PyArrow` · `Claude Agent SDK` · `MCP` ·
`pytest` · `GitHub Actions` · `YAML data contracts` · `Power BI` (downstream)

---

## Author

**Sri Harsha Malla** — [github.com/harsha-dcode](https://github.com/harsha-dcode)

## License

MIT — see [LICENSE](LICENSE).
