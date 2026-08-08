# Case Studies — Benchmark Suite

Five datasets, deliberately chosen to differ along the axes that break data
pipelines: scale, column count, domain, defect density, and — in one case —
the absence of defects.

Every run in this directory was produced by the **same agent specification**
with no per-dataset tuning. The runs are unattended: no human answered a
question mid-run, and every judgment call is written into the run's own report.

## Datasets

| Case study | Rows | Cols | Size | Domain | Role in the suite |
|---|---:|---:|---:|---|---|
| `healthcare/` | 58,164 | 19 | 9.4 MB | Hospital admissions | Highest defect density; source of the collision incident |
| `housing/` | 50,000 | 46 | 24.5 MB | Real-estate listings | Widest schema; signed-coordinate trap |
| `logistics/` | 30,102 | 35 | 8.9 MB | Supply chain | Cross-column temporal logic |
| `telecom/` | 3,333 | 11 | 126 KB | Subscriber churn | **Control case** — already clean |
| `sales/` | 312 | 11 | 33 KB | E-commerce orders | Extraction-layer defects: BOM, header drift |
| **Total** | **141,911** | **122** | **~43 MB** | | |

## Why a control case matters

`telecom/` is included precisely because it is clean. A cleaning pipeline that
always reports changes is indistinguishable — from its output alone — from one
that fabricates them. The control case is the run where "we found almost
nothing, and here is the evidence that we looked" is the correct and expected
result.

Any pipeline can show a large number on a dirty dataset. Showing a *small* one
on a clean dataset is the harder claim, and the one that makes the others
credible.

## Why the widest schema matters

`housing/` carries 46 columns including `latitude` and `longitude`. Negative
values there are **legitimate geography**, not sign errors — the same defect
class that, applied blindly as `abs()`, would silently relocate every property
in the southern and western hemispheres. It is the clearest illustration of why
impossible-value handling is decided per column rather than globally.

## Provenance

Raw inputs are **not committed** — they are large, they are not the deliverable,
and their integrity is verifiable from the checksums below. Each case-study
directory ships its reports, its change log, and the numbered scripts needed to
reproduce the run.

| Case study | Source file | SHA-256 (first 16) |
|---|---|---|
| healthcare | `healthcare_dataset_dirty_export.csv` | `1a076a045791222e` |
| housing | `house_50k_sample.csv` | `0c677488077cafee` |
| logistics | `logistics_supply_chain_dataset_v3.csv` | `0b8dcdc1d2e22d40` |
| telecom | `telecom_churn.csv` | `9ba8203038355a2a` |
| sales | `messy_sales.csv` | `79f672119c134d5d` |

The healthcare and sales datasets are synthetic with **deliberately injected and
counted** defects, which is what makes recall measurable rather than asserted —
a defect the pipeline misses is a defect somebody can point at.

## What each directory contains

```
case_studies/<name>/
├── RUN_SUMMARY.md          # headline numbers, verifiable against the artifacts
├── 01_business_brief.yaml  # the data contract, written before profiling
├── change_log.csv          # row-level audit trail — every changed cell
├── validation_report.*     # each check by name, with its result
├── insights_report.md      # Stage 9 analysis
├── cleaned_data.csv        # cleaned output
├── viz_ready.csv           # filtered, chart-ready output
└── NN_*.py                 # numbered scripts — the run reproduces from this folder alone
```

Scripts are kept rather than deleted so that any number in any report can be
re-derived by someone who does not trust the report.

### What is committed in full, and what is sampled

| File | Committed | Why |
|---|---|---|
| `change_log.csv` | **In full**, always | It is the evidence. A sampled audit trail proves nothing. |
| All reports, briefs, scripts | **In full** | Small, and they carry the reasoning. |
| `cleaned_data.csv` / `viz_ready.csv` | Full for `sales` and `telecom`; **1,000-row sample** for `healthcare`, `housing`, `logistics` | Those three run 17–29 MB each. The full output is reproducible from the numbered scripts, so shipping ~140 MB of regenerable CSV would only slow down every clone. |

The sampled files are named `*_sample_1000.csv`. To regenerate the full output,
run the numbered scripts in the case-study directory.

## Reproducing a run

Each script resolves its own paths from its location on disk — there are no
arguments, no environment variables, and no absolute paths to edit. Drop the
source CSV in `input/` and run the scripts in filename order:

```bash
# 1. Place the source CSV at case_studies/<name>/input/
#    (filenames are listed in the Provenance table above)
mkdir -p case_studies/telecom/input
cp /path/to/telecom_churn.csv case_studies/telecom/input/

# 2. Run the numbered scripts in order — from any working directory
for s in case_studies/telecom/*.py; do python "$s" || break; done

# 3. Verify the run is complete and the contract was honoured
python check_run_complete.py case_studies/telecom
```

Script names differ per case study because each run wrote the stages its own
dataset needed — sorting by filename is always the correct order. Windows
PowerShell equivalent for step 2:

```powershell
Get-ChildItem case_studies\telecom\*.py | Sort-Object Name | ForEach-Object { python $_.FullName }
```

`check_run_complete.py` exits non-zero if any required artifact is missing, if
the business brief uses blanket imputation keys, or if the change log lacks the
fields needed to reconstruct the original data.
