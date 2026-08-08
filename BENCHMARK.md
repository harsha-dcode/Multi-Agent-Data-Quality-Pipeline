# Benchmark — independent re-run, 2026-08-08

The five case studies in [`case_studies/`](case_studies/) were produced over
several sessions. This is a **single parallel re-run of all five**, executed
end-to-end on one afternoon, to test whether the published numbers reproduce.

They mostly do. Where they don't, this file says so.

**Run window:** 15:22:29 → 16:04:51 IST, 2026-08-08 · zero human input during
the runs.

---

## What was run

Five `data-pipeline-cleaner` agents launched simultaneously, one per dataset,
each executing the full 9-stage pipeline against the same raw inputs and writing
to an isolated output directory outside this repository.

| Dataset | Rows in | Cols | Cells |
|---|---:|---:|---:|
| healthcare | 58,164 | 19 | 1,105,116 |
| housing | 50,000 | 46 | 2,300,000 |
| logistics | 30,102 | 35 | 1,053,570 |
| telecom *(control)* | 3,333 | 11 | 36,663 |
| sales | 312 | 11 | 3,432 |
| **Total** | **141,911** | | **4,498,781** |

---

## Results

| Dataset | Rows in → cleaned → viz-ready | Log entries | Value edits | Validation | Duration |
|---|---|---:|---:|---|---:|
| healthcare | 58,164 → 55,869 → 55,399 | 37,897 | 22,298 | 10 pass, 1 fail | 41.8 min |
| housing | 50,000 → 49,864 → 48,870 | 143,574 | 135,149 | 11 pass, 0 fail | 24.1 min |
| logistics | 30,102 → 30,000 → 29,354 | 86,968 | 36,210 | 11 pass, 0 fail | 27.6 min |
| telecom *(control)* | 3,333 → 3,333 → 3,333 | 630 | **0** | 11 pass, 0 fail | 24.0 min |
| sales | 312 → 281 → 266 | 2,081 | 1,505 | 12 pass, 1 fail | 14.3 min |
| **Total** | **141,911 → 139,347 → 137,222** | **271,150** | **195,162** | | |

- **Wall-clock: 42 min 22 s** (2,542 s)
- **Compute: 2 h 11 min 46 s** (7,906 s summed across the five runs)
- **Parallelism speed-up: 3.11×**
- **30 artifacts produced** — six per dataset, all present and gate-verified

Per-dataset measurements are in [`benchmarks/2026-08-08/`](benchmarks/2026-08-08/),
one JSON file per run, each written by that run from its own artifacts.

---

## What reproduced

**Four of five datasets landed on identical row counts.**

| Dataset | Published run | This run | |
|---|---|---|:--:|
| housing | 50,000 → 49,864 → 48,870 | 50,000 → 49,864 → 48,870 | ✅ |
| logistics | 30,102 → 30,000 → 29,354 | 30,102 → 30,000 → 29,354 | ✅ |
| sales | 312 → 281 → 266 | 312 → 281 → 266 | ✅ |
| telecom | 3,333 → 3,333 → 3,333 | 3,333 → 3,333 → 3,333 | ✅ |
| healthcare | 58,164 → 55,874 → 54,470 | 58,164 → 55,869 → 55,399 | ⚠️ |

Healthcare differed by **5 rows** on the cleaned output and **929** on
viz-ready — a different filtering decision at the pre-visualisation stage, not a
different cleaning result.

**Timing reproduced too.** The published figure is 2 h 18 min compute / ~37 min
wall-clock. This run: 2 h 11 min 46 s / 42 min 22 s — within roughly 5% on
compute.

**The control case held.** `telecom` again recorded **zero** data-value edits.
On a dataset that is already clean, the pipeline did nothing, twice, and logged
that it did nothing.

---

## What did not reproduce, and why

**Value-edit counts are not stable across runs, and should not be quoted as a
headline metric.**

| | Published | This run |
|---|---:|---:|
| Log entries | 220,521 | 271,150 |
| Value edits | 25,106 | 195,162 |

`housing` alone moved from 2,783 to 135,149 value edits. This is a **logging
granularity difference, not a behavioural one**: this run classified every
string/whitespace normalisation as a value edit, where the published run counted
only substantive corrections. The row-level outcomes were identical.

One run also caught and corrected its own over-logging mid-flight — the
logistics run found it was emitting a `DATE_PARSED` entry for every non-null
cell even when the ISO-format string was unchanged, fixed it, and re-ran
cleaning through validation. Final value edits fell from 186,490 to 36,210.

The stable, comparable metrics are **row counts** and **artifact counts**.
Log volume is evidence of thoroughness, not a measure of it.

---

## Caveats

Stated plainly, because they affect how much this run is worth.

| Caveat | Detail |
|---|---|
| **Not a clean-room reproduction** | The agents had read access to this repository so they could reach the input CSVs — which also left the *previously published* briefs and reports readable. Two runs reported consulting prior work before independently re-deriving their results. This validates throughput and reproducibility; it does not demonstrate solving the datasets from scratch. |
| **Operation selection still varies** | The count and choice of operations differed between runs, as documented in the main README's Known Limitations. That is the phenomenon the run gate exists to contain, and this benchmark is further evidence of it rather than a refutation. |
| **Two datasets are synthetic** | Unchanged from the published runs. |
| **Validation counts shifted slightly** | healthcare went from 12 pass / 1 fail to 10 pass / 1 fail, consistent with the varying-coverage limitation above. |

---

## Reproducing this

The published case studies remain the canonical artifacts; this run did not
modify them. To verify any published run honours its own contract:

```bash
python check_run_complete.py case_studies/healthcare
```

To re-derive any published number, execute the numbered scripts kept in that
case study's folder — they depend only on `pandas`, `numpy` and `pyyaml`.
