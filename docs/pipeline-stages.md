# Pipeline Stages Reference — `src/agent/` tool sequence

> ⚠️ **There are two different nine-step sequences in this repository. This
> document describes the one in `src/agent/`, not the one the benchmark runs used.**
>
> | | This document | The benchmark case studies |
> |---|---|---|
> | What it is | The **tool call order** of the MCP tool server in `src/agent/` | The **methodology** in `.claude/agents/data-pipeline-cleaner.md` |
> | Steps | `extract_csv` → `profile_data` → `clean_data` → `correct_dates` → `impute_data` → `profile_data` → `clean_data` → `write_report` → `finalize` | Business Understanding → Extraction → Profiling → Cleaning → Validation → Integration → Transformation → Pre-Viz → Analytics |
> | Produced the five runs in `case_studies/`? | **No** | **Yes** |
>
> Both happen to have nine steps, which is a coincidence of naming and not a
> correspondence — step 4 here is `correct_dates`, step 4 there is Cleaning.
> Do not read one as an implementation of the other.
>
> For how the published results were actually produced, see the README section
> *"How the benchmark runs were actually produced"*.

## Stage 1 — extract_csv

**File**: `src/agent/tools/extract_csv.py`
**Input**: `workspace/00_landing/input.csv`
**Output**: `workspace/00_landing/extracted.parquet`

Reads the CSV with `pandas.read_csv()`, converts to Parquet (faster for downstream stages), and returns the row count and column list. Always the first tool called.

**Why Parquet?** Parquet preserves dtypes across reads, is faster than CSV for repeated reads, and handles unicode column names cleanly.

---

## Stage 2 — profile_data

**File**: `src/agent/tools/profile.py`
**Input**: `workspace/00_landing/extracted.parquet`
**Output**: `workspace/10_profiled/profile.json` (also returned as text to Claude)

Generates a column-level JSON profile:

```json
{
  "row_count": 988,
  "column_count": 14,
  "duplicate_row_count": 8,
  "columns": {
    "order_date": {
      "dtype": "object",
      "null_count": 0,
      "null_pct": 0.0,
      "unique": 365,
      "top_values": {"15/03/2024": 3, "2024-01-01": 2}
    },
    "total_revenue": {
      "dtype": "float64",
      "null_count": 23,
      "null_pct": 2.33,
      "min": 240.5,
      "q25": 1200.0,
      "median": 3500.0,
      "q75": 8900.0,
      "max": 450000.0,
      "iqr_outlier_count": 10,
      "iqr_lower_bound": -8550.0,
      "iqr_upper_bound": 18650.0
    }
  }
}
```

Claude reads this and decides every downstream cleaning operation based on it.

---

## Stage 3 — clean_data (pass 1)

**File**: `src/agent/tools/clean.py`
**Input**: `workspace/00_landing/extracted.parquet` (first call) or `workspace/20_cleaned/cleaned.parquet`
**Output**: `workspace/20_cleaned/cleaned.parquet` + `workspace/20_cleaned/cleaning_log.txt`

Applies a list of operations in order. Claude decides which operations based on the profile. Standard pass-1 operations:

| Order | Operation | Why |
|---|---|---|
| 1 | `rename` | snake_case column names |
| 2 | `drop_duplicates` | remove exact duplicate rows |
| 3 | `nfkc_normalize` | unicode normalization on all text columns |
| 4 | `normalize_string` | lowercase + strip on categoricals |
| 5 | `fill_nulls` (value=null) | replace sentinel strings with NaN |
| 6 | `cast_dtype` (datetime) | parse date strings |
| 7 | `normalize_string` + `cast_dtype` (float) | strip currency symbols from numerics |
| 8 | `cap_outliers_iqr` | cap IQR outliers where profile shows extreme signals |

**All 20+ supported operations:**

- `drop_duplicates` — exact row deduplication
- `drop_nulls` — drop rows where specified columns are null
- `fill_nulls` — fill with value/mean/median/mode
- `cap_outliers_iqr` — clip values at IQR bounds (k=1.5 default)
- `cast_dtype` — cast to datetime/int/float/string
- `normalize_string` — strip + lowercase
- `rename` — rename columns by mapping dict
- `nfkc_normalize` — unicode NFKC normalization + whitespace collapse
- `clean_names` — strip honorifics, fix dot-separators, title-case
- `validate_emails` — RFC-compliant email validation + flag column
- `normalize_phones` — strip +91/91 country code, keep 10 digits
- `fix_region` — canonicalize to East/North/South/West/North-East
- `fix_product` — canonicalize to Alpha/Beta/Delta/Gamma
- `fix_channel` — canonicalize to Online/Wholesale/Retail/B2B/B2C
- `flag_negatives` — add boolean flag column for negative values

---

## Stage 4 — correct_dates

**File**: `src/agent/tools/correct_dates.py`
**Input/Output**: `workspace/20_cleaned/cleaned.parquet` (in-place)

Two-phase processing:

**Pre-parse phase** (if column is still string dtype):
- Snaps impossible date strings before casting
- Feb 29 in non-leap year → Feb 28
- Day 31 in 30-day month → Day 30
- Month > 12 but day ≤ 12 → swap day/month (MM/DD/YYYY mixed into DD/MM/YYYY data)
- Then casts to datetime

**Post-parse phase** (always runs):
- Flags future dates (> 1 day in the future)
- Flags far-past dates (year < median_year − 10)
- Flags far-future dates (year > median_year + 5)
- Writes flags to `date_flag` column as pipe-separated strings

---

## Stage 5 — impute_data

**File**: `src/agent/tools/impute.py`
**Input/Output**: `workspace/20_cleaned/cleaned.parquet` (in-place)

Four passes in order:

**Pass 0 — Decimal-typo outlier correction:**
Detects values > 100× column median. Tries divisors [10, 100, 1000]. Validates corrected value against the formula (revenue = units × price) and against the column median. Accepts the smallest divisor that produces a consistent result.

**Pass A — Formula derivation:**
When exactly one of {revenue, units, price} is null, derives it from the other two. Also flags `revenue_mismatch=True` where all three are present but stored revenue differs from units×price by >5%.

**Pass B — Pattern derivation:**
- `customer_name` from `first.last@domain` email → `First Last`
- `customer_email` from `Firstname Lastname` when dominant domain (>80%) can be identified

**Pass C — Statistical fallback:**
- Categorical columns → mode
- Numeric columns → median
- Skips rows with `negative_flag=True` or `revenue_mismatch=True`

**Pass D — Drop damaged rows:**
Removes rows where ≥ 3 critical columns are still null after all passes.

---

## Stage 6 — profile_data (pass 2)

Same as Stage 2, but run on the cleaned Parquet. Claude checks:
- Critical column null rates dropped below 2%
- No new anomalies introduced by cleaning
- Distributions look reasonable

---

## Stage 7 — clean_data (pass 2, optional)

Only invoked if profile pass 2 shows residual issues. Typically just targeted `drop_nulls` or `fill_nulls` for columns that imputation couldn't resolve.

---

## Stage 8 — write_report

**File**: `src/agent/tools/report.py`
**Output**: `workspace/99_final/report.md`

Claude writes a full markdown report covering:
- Brief summary of the dataset
- Every cleaning decision with justification
- Imputation counts by pass
- Date corrections and flags
- Findings relevant to the brief
- Caveats and what a human should verify

The report is the narrative deliverable. The dataset is the data deliverable.

---

## Stage 9 — finalize

**File**: `src/agent/tools/finalize.py`
**Input**: `workspace/20_cleaned/cleaned.parquet`
**Output**: `workspace/99_final/final_dataset.csv` + `workspace/99_final/final_dataset.parquet`

Converts the cleaned Parquet to CSV (for BI tools) and re-saves as Parquet (for downstream Python). Both files are identical in content; only the format differs.
