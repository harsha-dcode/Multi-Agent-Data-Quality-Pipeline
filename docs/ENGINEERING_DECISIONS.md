# Engineering Decisions

Design decisions, the alternatives rejected, and the costs accepted. Written in
the order the problems appeared, not in the order that makes the project look
tidiest.

---

## ADR-1 — Split the decision layer from the execution layer

**Decision.** A language model decides *what* to clean and *why*. Python
executes *every* transformation deterministically. No model ever writes a cell
value directly.

**Why.** Data cleaning has two genuinely different halves. Choosing whether
`length_of_stay = -3` is a sign error or a corrupted record requires context,
domain reasoning, and an ability to weigh consequences. Applying that decision
across 58,000 rows requires exactness and repeatability. Optimising one process
for both produces something bad at each.

**Consequence.** The same operation list applied to the same input reproduces
the same output, byte for byte. That guarantee is testable and it is tested.

**Where the guarantee stops — the honest part.** The model selects *which*
operations run, and that selection is **not deterministic across runs**. In one
comparison the logistics dataset received all 12 validation checks while the
healthcare dataset received 5 — same agent, same specification, different run.
Determinism in the executor does not buy determinism in the deliverable.

**What closes the gap.** Moving checks out of the prompt and into code the
agent cannot skip. `check_run_complete.py` (ADR-5) is the first instalment;
the remaining checks are named in the roadmap rather than described as done.

---

## ADR-2 — Extract with zero type inference

**Decision.** All ingestion is `pd.read_csv(path, dtype=str, keep_default_na=False)`.
Nothing is parsed, converted, or interpreted at load time.

**Alternative rejected.** Letting pandas infer dtypes and null values, which is
faster to write and what most pipelines do.

**Why it was rejected.** Default loading converts *some* disguised nulls to
`NaN` and leaves others as literal strings. Measured on a benchmark file with
730 disguised nulls across 14 spellings: **414 were destroyed, 316 survived.**
The destroyed cells lose their original text permanently, which makes the
change-log entry for each of them impossible to write.

That is not a cleaning problem that a later stage can fix. It is evidence
destruction, and it happens before the pipeline's first decision.

**Cost accepted.** Every downstream stage must convert types explicitly, and
the code is longer. In exchange, every conversion is a logged, reversible event
instead of an invisible one.

---

## ADR-3 — Assign provenance at extraction, not later

**Decision.** `__source_row` — the 0-indexed position of the record among the
source data rows, header excluded — is attached to every record at landing,
before deduplication or reordering.

Verified across the benchmark suite: for the `logistics` run, all 230 logged
`Actual_Delivery_Date` null-standardisation entries map **230/230** onto the
230 cells that are genuinely empty in the raw file. The audit trail resolves
back to the source bytes, which is the only test of a provenance column that
means anything.

**Why.** After dedup, sorting, filtering and joins, "which line of the source
file did this row come from?" is unanswerable unless the answer was recorded
while it was still trivially known. Reconstructed later, it is a guess wearing
the costume of a fact.

**Cost accepted.** One extra column carried through every stage.

---

## ADR-4 — Refuse rather than guess

**Decision.** When a transformation cannot be performed safely, the pipeline
declines it, keeps the original value, and records the refusal in the report.

**Applications.**

| Situation | Common approach | This pipeline |
|---|---|---|
| Closed code set with colliding members | Fuzzy match at 85% | Guard trips → exact matching only, refusal logged |
| Categorical with a tied mode (250/250) | Mode-impute | `never_impute`; nulls survive |
| Negative revenue figure | `abs()` | Per-column decision; refunds preserved |
| Missing identifier | Drop or fill | Kept, flagged, never invented |

**Why.** A pipeline that always produces an answer is indistinguishable from a
pipeline that produces a *correct* answer, from the output alone. Refusals are
what make the successes credible.

**Cost accepted.** The output contains more nulls than a maximally aggressive
cleaner would produce. This is the intended trade: a reported gap is cheaper
than an invented value that reaches a dashboard and gets believed.

---

## ADR-5 — A deterministic gate outside the agent

**Decision.** `check_run_complete.py` — plain Python, no model — fails a run
that is missing any required artifact, whose business brief uses blanket
imputation keys, or whose change log lacks the fields needed to reconstruct the
original data. Exit code 1, usable in CI.

**Why.** Every guard in ADR-4 lives partly in an agent specification, and a
specification is an instruction, not an enforcement mechanism. An agent can
skip an instruction, report success, and be wrong in exactly the way this
project exists to prevent.

**Design detail worth noting.** The gate distinguishes *empty* from *absent*.
`dangerous_columns: {}` means the guard ran and nothing tripped — a pass.
`dangerous_columns` missing means nobody checked — a failure. Collapsing those
two states would let a skipped check masquerade as a clean one.

Optional keys are advisory only and never fail a run, because an omitted
optional key is an honest "not established," and failing runs for honesty
trains the model to fabricate.

---

## ADR-6 — The change log must reconstruct, not summarise

**Decision.** The change log records `column`, `__source_row`, `change_type`,
`original_value`, `new_value`, `reason` — one row per changed cell. The binding
requirement is that the original dataset be recoverable from the cleaned
dataset plus the log.

**Alternative rejected.** Aggregate counts — *"6,126 nulls imputed"* — which
are cheaper to produce and satisfy most definitions of "audit log."

**Why it was rejected.** A count answers *how much changed*. Review requires
*what changed, where, from what, and on whose authority*. The first cannot be
converted into the second; the second trivially yields the first.

**Cost accepted.** Change logs get large — tens of thousands of rows on a
58,000-row dataset. Storage is cheap; an unreviewable transformation is not.

---

## ADR-7 — Track the agent specification in version control

**Decision.** `.claude/agents/data-pipeline-cleaner.md` is committed to the
repository and treated as source code, not as configuration.

**Why.** The specification *is* the decision layer. A reviewer reading only
`src/` sees the executor — the deterministic, uncontroversial half — and none
of the reasoning that determines what the executor is asked to do. Reviewing
this project without the specification means reviewing the wrong half.

It is also the file where guard rules are defined, which makes its diff history
the real changelog of the project's safety properties.

---

## Known limitations

Stated plainly, because a reviewer will find them anyway and finding them
undocumented is worse.

| Limitation | Status |
|---|---|
| Operation *selection* is non-deterministic across runs | Real. Mitigated by the run gate; not eliminated. |
| Validation-check coverage varied by run (12 vs 5) | Root cause of the gate. Checks still live partly in the prompt. |
| No database connectors — CSV ingestion only | Extractor interface exists; connectors unimplemented. |
| Single-machine, in-memory pandas | Fine to ~10M rows; no distributed execution path. |
| CI runs tests + the gate, not the full pipeline | End-to-end runs need API credentials, so CI verifies the deterministic half only. |
| Pure logic is coupled to the SDK import | `src/agent/tools/__init__.py` imports `claude_agent_sdk` at module scope, so testing `_apply_op` requires the package installed even though no API call is made. Decoupling it is on the roadmap. |
| `test_pipeline_tools.py` re-implements 8 ops inline | It is an end-to-end shape check, not a test of shipped code. `test_clean_ops.py` was added to cover the real `_apply_op` — all 15 operations — so a regression in `clean.py` fails the build. |
| Benchmark datasets are synthetic | Defects are injected and counted, which is what makes recall measurable — but synthetic defects are not field defects. |

---

## Roadmap

Ordered by how much each reduces the risk of a silent failure, not by how
impressive it sounds.

1. **Move the remaining validation checks from the specification into executor
   code.** Closes the ADR-1 gap directly.
2. **Property-based tests on the guards** — generate colliding canonical sets
   and assert the collision guard trips on all of them.
4. **Database and object-store extractors** — Postgres, SQL Server, S3.
5. **Incremental runs** keyed on `__source_row` provenance.
