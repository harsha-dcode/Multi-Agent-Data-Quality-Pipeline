# -*- coding: utf-8 -*-
"""
Stage 4: DATA CLEANING (full pipeline, sub-steps 4.0 - 4.11)
Reads the raw CSV, produces:
  - 03_intermediate_cleaned.csv (post-Stage-4, pre-transform; internal working file)
  - change_log.csv (canonical fixed-name deliverable) + change_log.csv (alias, user asked by this name)
  - 03_flag_registry.json (flag column -> meaning, for Stage 8/9 and V13)
  - 03_stage4_report.txt (human-readable summary with real counts)
All decisions trace back to 01_business_brief.yaml (business_rules BR1-BR6, dangerous_columns,
missing_value_strategy) and to the measured evidence in 02_*, 02b_*, 02c_* reports.
"""

from pathlib import Path as _Path
_HERE = _Path(__file__).resolve().parent

import pandas as pd
import numpy as np
import re
import json
import unicodedata
from datetime import date
from rapidfuzz import fuzz, process as rf_process, utils as rf_utils
import os

IN = str(_HERE / "input" / "healthcare_dataset_dirty_export.csv")
OUT_DIR = str(_HERE)

CHANGE_LOG = []  # list of dicts: STAGE, COLUMN, SOURCE_ROW, CHANGE_TYPE, ORIGINAL_VALUE, NEW_VALUE, REASON
FLAG_REGISTRY = {}  # flag_col -> meaning

def log(stage, column, source_row, change_type, orig, new, reason):
    CHANGE_LOG.append({
        "STAGE": stage, "COLUMN": column, "SOURCE_ROW": source_row,
        "CHANGE_TYPE": change_type, "ORIGINAL_VALUE": orig, "NEW_VALUE": new, "REASON": reason
    })

def register_flag(colname, meaning):
    FLAG_REGISTRY[colname] = meaning

report = []
def rprint(*args):
    s = " ".join(str(a) for a in args)
    print(s)
    report.append(s)

# =====================================================================================
# LOAD + __source_row (4.0)
# =====================================================================================
df = pd.read_csv(IN, encoding="utf-8", low_memory=False, dtype=str)
RAW_ROWS = len(df)
df.insert(0, "__source_row", range(len(df)))
rprint(f"Loaded raw file: {RAW_ROWS} rows, {len(df.columns)-1} data columns (+__source_row)")

# =====================================================================================
# 4.1 HEADER NORMALIZATION
# =====================================================================================
def to_snake(h):
    h = h.strip()
    h = re.sub(r"[ \-\./]+", "_", h)
    h = re.sub(r"[^0-9a-zA-Z_]", "", h)
    h = re.sub(r"_+", "_", h).strip("_")
    return h.lower()

orig_cols = [c for c in df.columns if c != "__source_row"]
rename_map = {}
seen = {}
for c in orig_cols:
    new = to_snake(c)
    if new in seen:
        seen[new] += 1
        new = f"{new}_{seen[new]}"
    else:
        seen[new] = 1
    rename_map[c] = new

df = df.rename(columns=rename_map)
for orig, new in rename_map.items():
    log("Stage4.1", new, "ALL", "HEADER_RENAME", orig, new, "snake_case normalization of raw header")
rprint("4.1 Header normalization:", rename_map)

COLS = list(rename_map.values())
# handy references
C_NAME, C_AGE, C_GENDER, C_BLOOD, C_COND, C_DOA, C_DOC, C_HOSP, C_INS, C_BILL, C_ROOM, \
C_ATYPE, C_DDATE, C_MED, C_TR, C_LOS, C_AYEAR, C_AMONTH, C_AYM = (
    "name","age","gender","blood_type","medical_condition","date_of_admission","doctor",
    "hospital","insurance_provider","billing_amount","room_number","admission_type",
    "discharge_date","medication","test_results","length_of_stay",
    "admission_year","admission_month","admission_yearmonth"
)

# =====================================================================================
# 4.2 NULL STANDARDIZATION (match on stripped+casefolded value; gate ambiguous tokens per column)
# =====================================================================================
UNAMBIGUOUS = {'', ' ', '?', 'null', 'none', 'tbd', 'undefined', '#n/a', '#value!', '#ref!', 'n/a'}
# 'na' is ambiguous per spec -> gated. Domain-specific tokens found in profiling (02_stage3):
DOMAIN_TOKENS = {'not available', 'missing', 'pending', 'see invoice'}
DASH_TOKEN = {'--', '-'}  # '-' alone is ambiguous (spec); '--' behaves as an unambiguous separator token in this data

def strip_cf(s):
    return str(s).strip().casefold()

def null_standardize(col, canonical_set, extra_domain_tokens=None, always_null_extra=None):
    """canonical_set: set of allowed category strings (casefolded) for the GATE.
       None means non-categorical (numeric/date) -> gate always says NO (nothing in that set)."""
    nulled = 0
    retained = 0
    s = df[col]
    mask_notnull = s.notna()
    vals = s[mask_notnull]
    keys = vals.map(strip_cf)

    tokens_to_null = set(UNAMBIGUOUS)
    if always_null_extra:
        tokens_to_null |= always_null_extra

    ambiguous_candidates = {'na', '-', '--', 'unknown'} | (extra_domain_tokens or set())
    for tok in ambiguous_candidates:
        # GATE: could tok be a member of this column's canonical set?
        in_domain = canonical_set is not None and tok in canonical_set
        if in_domain:
            continue  # retained as real value, not touched here
        else:
            tokens_to_null.add(tok)

    hit_mask = keys.isin(tokens_to_null)
    hit_idx = vals[hit_mask].index
    for idx in hit_idx:
        row = df.loc[idx, "__source_row"]
        orig = df.loc[idx, col]
        tok = strip_cf(orig)
        reason = (f"null disguise (unambiguous set)" if tok in UNAMBIGUOUS else
                  f"GATE=NO: '{tok}' is not a member of {col}'s canonical/domain value set -> nulled")
        log("Stage4.2", col, row, "NULL_STANDARDIZED", orig, "", reason)
        nulled += 1
    df.loc[hit_idx, col] = np.nan

    # retained ambiguous tokens actually present but judged real (only relevant if canonical_set had them)
    for tok in ambiguous_candidates:
        if canonical_set is not None and tok in canonical_set:
            present_mask = keys == tok
            present_idx = vals[present_mask].index
            for idx in present_idx:
                row = df.loc[idx, "__source_row"]
                orig = df.loc[idx, col]
                log("Stage4.2", col, row, "NULL_DISGUISE_RETAINED", orig, orig,
                    f"GATE=YES: '{tok}' is a legitimate member of {col}'s canonical set - retained, not nulled")
                retained += 1
    return nulled, retained

before_nulls = {c: int(df[c].isna().sum()) for c in COLS if c != "__source_row"}

CANON_SETS = {
    C_GENDER: {"male", "female"},
    C_BLOOD: {"a+","a-","b+","b-","ab+","ab-","o+","o-"},
    C_COND: {"diabetes","arthritis","cancer","asthma","hypertension","obesity"},
    C_ATYPE: {"elective","emergency","urgent"},
    C_INS: {"cigna","unitedhealthcare","medicare","blue cross","aetna"},
    C_TR: {"normal","abnormal","inconclusive"},
    C_MED: {"ibuprofen","lipitor","penicillin","paracetamol","aspirin"},
}
DOMAIN_EXTRA = {
    C_AGE: {'not available','missing','pending','see invoice'},
    C_GENDER: {'not available','missing'},
    C_BLOOD: {'not available','missing'},
    C_INS: {'not available','missing'},
    C_BILL: {'not available','missing','pending','see invoice'},
    C_ROOM: {'not available','missing','pending'},
    C_ATYPE: {'not available','missing'},
    C_DDATE: set(),
    C_DOA: set(),
    C_MED: {'not available','missing'},
    C_TR: {'not available','missing'},
    C_LOS: set(),
}

rprint("\n4.2 NULL STANDARDIZATION (gate results per column):")
null_std_summary = {}
for col in [C_NAME, C_AGE, C_GENDER, C_BLOOD, C_COND, C_DOA, C_DOC, C_HOSP, C_INS, C_BILL,
            C_ROOM, C_ATYPE, C_DDATE, C_MED, C_TR, C_LOS, C_AYEAR, C_AMONTH, C_AYM]:
    canon = CANON_SETS.get(col)  # None for non-categorical
    extra = DOMAIN_EXTRA.get(col, set())
    n, r = null_standardize(col, canon, extra_domain_tokens=extra)
    null_std_summary[col] = (n, r)
    rprint(f"  {col}: nulled={n} retained_as_real={r}")

after_nulls = {c: int(df[c].isna().sum()) for c in COLS if c != "__source_row"}
rprint("\n4.2 VERIFY: null rate before -> after (per column):")
for c in COLS:
    if c == "__source_row": continue
    b = before_nulls.get(c, 0); a = after_nulls.get(c, 0)
    rprint(f"  {c}: {b} ({100*b/RAW_ROWS:.2f}%) -> {a} ({100*a/RAW_ROWS:.2f}%)")

# ---- billing_amount sentinel 999999 (numeric placeholder, not a string disguise) ----
# Handled later in numeric cleaning (needs numeric parse first). Logged there.

# =====================================================================================
# 4.3 STRING NORMALIZATION (strip, collapse internal spaces, NFC normalize)
# =====================================================================================
def normalize_string_col(col, preserve_case=True):
    s = df[col]
    changed = 0
    for idx in s[s.notna()].index:
        orig = s.loc[idx]
        new = unicodedata.normalize("NFC", str(orig))
        new = new.strip()
        new = re.sub(r"\s+", " ", new)
        if new != orig:
            row = df.loc[idx, "__source_row"]
            log("Stage4.3", col, row, "STRING_NORMALIZED", orig, new,
                "strip whitespace / collapse internal spaces / NFC normalize")
            df.loc[idx, col] = new
            changed += 1
    return changed

rprint("\n4.3 STRING NORMALIZATION:")
for col in [C_NAME, C_GENDER, C_BLOOD, C_COND, C_DOC, C_HOSP, C_INS, C_ATYPE, C_MED, C_TR]:
    n = normalize_string_col(col)
    rprint(f"  {col}: {n} values whitespace/NFC-normalized")

# =====================================================================================
# 4.3b COLUMN-VALUE SWAP CORRECTION (business_rules BR5) - must run BEFORE typo correction
# so each column only contains its own domain vocabulary going into fuzzy matching.
# =====================================================================================
def swap_correct(colA, colB, setA_words, setB_words, label):
    """If colA holds a word that belongs to colB's vocabulary AND colB holds a word that
    belongs to colA's vocabulary (symmetric evidence), exchange them."""
    sA = df[colA].astype(str).str.strip().str.casefold()
    sB = df[colB].astype(str).str.strip().str.casefold()
    a_is_b = df[colA].notna() & sA.isin(setB_words)
    b_is_a = df[colB].notna() & sB.isin(setA_words)
    both = a_is_b & b_is_a
    idxs = df[both].index
    for idx in idxs:
        row = df.loc[idx, "__source_row"]
        origA, origB = df.loc[idx, colA], df.loc[idx, colB]
        log("Stage4.3b", colA, row, "COLUMN_VALUE_SWAP_CORRECTED", origA, origB,
            f"symmetric swap with {colB} (BR5): {colA} held a {colB}-domain value and vice versa; exchanged")
        log("Stage4.3b", colB, row, "COLUMN_VALUE_SWAP_CORRECTED", origB, origA,
            f"symmetric swap with {colA} (BR5): {colB} held a {colA}-domain value and vice versa; exchanged")
        df.loc[idx, colA], df.loc[idx, colB] = origB, origA
    flagcol = f"{label}_swap_corrected_flag"
    df[flagcol] = False
    df.loc[idxs, flagcol] = True
    register_flag(flagcol, f"True if {colA}/{colB} values were swapped in source and mechanically exchanged back (BR5)")
    return len(idxs)

n_swap1 = swap_correct(C_BLOOD, C_GENDER, CANON_SETS[C_BLOOD], CANON_SETS[C_GENDER], "blood_gender")
n_swap2 = swap_correct(C_TR, C_MED, CANON_SETS[C_TR], CANON_SETS[C_MED], "test_results_medication")
rprint(f"\n4.3b COLUMN-VALUE SWAP CORRECTION: blood_type<->gender swapped rows={n_swap1}, test_results<->medication swapped rows={n_swap2}")

# =====================================================================================
# 4.4 CATEGORICAL TYPO CORRECTION (fuzzy matching, with mandatory collision guard result applied)
# =====================================================================================
DANGEROUS_COLS = {C_BLOOD}  # measured in stage3c_collision_guard.py - only blood_type collides

def alnum_key(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

def classify_value(val, canon_list, dangerous):
    """Returns (new_value, change_type_or_None, reason, score_or_None)."""
    if pd.isna(val):
        return val, None, None, None
    v = str(val).strip()
    vcf = v.casefold()
    canon_cf = {c.casefold(): c for c in canon_list}
    # Tier 1: exact case-fold match
    if vcf in canon_cf:
        target = canon_cf[vcf]
        if target == v:
            return v, None, None, None  # already canonical, no change
        return target, "STRING_NORMALIZED", "case-fold exact match to canonical form", 100
    if dangerous:
        return v, "UNKNOWN_CATEGORY_FLAGGED", f"no exact match in dangerous (fuzzy-disabled) column; value retained, flagged for review", None
    # Tier 2: alnum-only exact match (catches whitespace/punctuation-only diffs, e.g. 'United Healthcare')
    vkey = alnum_key(v)
    canon_alnum = {alnum_key(c): c for c in canon_list}
    if vkey in canon_alnum:
        return canon_alnum[vkey], "TYPO_CORRECTED", "exact match after removing non-alphanumeric characters (whitespace/punctuation-only difference)", 100
    # Tier 3: fuzzy match, punctuation-preserving processor + non-restripping scorer
    match = rf_process.extractOne(
        v, canon_list,
        processor=lambda x: str(x).strip().lower(),
        scorer=fuzz.token_sort_ratio,
    )
    if match is None:
        return v, "UNKNOWN_CATEGORY_FLAGGED", "no fuzzy candidate found; retained, flagged", None
    cand, score, _ = match
    if score >= 85:
        return cand, "TYPO_CORRECTED", f"fuzzy match (token_sort_ratio={score:.1f}) >= 85 threshold, auto-corrected", score
    elif score >= 70:
        return cand, "TYPO_CORRECTED", f"WARNING: fuzzy match (token_sort_ratio={score:.1f}) in 70-84 review band, corrected with review flag", score
    else:
        return v, "UNKNOWN_CATEGORY_FLAGGED", f"fuzzy match score {score:.1f} < 70 threshold; retained as UNKNOWN CATEGORY, not auto-corrected", score

rprint("\n4.4 CATEGORICAL TYPO CORRECTION (per column):")
CATEGORICAL_COLS = [C_GENDER, C_BLOOD, C_COND, C_ATYPE, C_INS, C_TR, C_MED]
typo_summary = {}

CANON_DISPLAY = {
    C_GENDER: ["Male", "Female"],
    C_BLOOD: ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
    C_COND: ["Diabetes", "Arthritis", "Cancer", "Asthma", "Hypertension", "Obesity"],
    C_ATYPE: ["Elective", "Emergency", "Urgent"],
    C_INS: ["Cigna", "UnitedHealthcare", "Medicare", "Blue Cross", "Aetna"],
    C_TR: ["Normal", "Abnormal", "Inconclusive"],
    C_MED: ["Ibuprofen", "Lipitor", "Penicillin", "Paracetamol", "Aspirin"],
}

for col in CATEGORICAL_COLS:
    canon_list = CANON_DISPLAY[col]
    dangerous = col in DANGEROUS_COLS
    unresolved_flag = f"{col}_unresolved_category_flag"
    df[unresolved_flag] = False
    register_flag(unresolved_flag, f"True if {col} value could not be confidently matched to a canonical value (dangerous-column exact-miss, or fuzzy score < 70)")

    unique_vals = df.loc[df[col].notna(), col].unique()
    vmap = {}
    for uv in unique_vals:
        vmap[uv] = classify_value(uv, canon_list, dangerous)

    n_normalized = n_typo = n_unresolved = 0
    idxs = df[df[col].notna()].index
    for idx in idxs:
        val = df.loc[idx, col]
        new_val, ctype, reason, score = vmap[val]
        row = df.loc[idx, "__source_row"]
        if ctype == "STRING_NORMALIZED":
            log("Stage4.4", col, row, "STRING_NORMALIZED", val, new_val, reason)
            df.loc[idx, col] = new_val
            n_normalized += 1
        elif ctype == "TYPO_CORRECTED":
            log("Stage4.4", col, row, "TYPO_CORRECTED", val, new_val, reason)
            df.loc[idx, col] = new_val
            n_typo += 1
        elif ctype == "UNKNOWN_CATEGORY_FLAGGED":
            log("Stage4.4", col, row, "UNKNOWN_CATEGORY_FLAGGED", val, val, reason)
            df.loc[idx, unresolved_flag] = True
            n_unresolved += 1
    typo_summary[col] = (n_normalized, n_typo, n_unresolved)
    rprint(f"  {col}: case_normalized={n_normalized} typo_corrected={n_typo} unresolved_flagged={n_unresolved} (dangerous={dangerous})")

# ---- MANDATORY VERIFICATION: post-clean value_counts + missing_canon check for every categorical col ----
rprint("\n4.4 VERIFICATION (post-fuzzy value_counts + missing-canon check) - required, not optional:")
verify_lines = []
for col in CATEGORICAL_COLS:
    canon_list = CANON_DISPLAY[col]
    vc = df[col].value_counts(dropna=True)
    missing_canon = [c for c in canon_list if c not in vc.index]
    verify_lines.append(f"--- {col} ---")
    verify_lines.append(vc.to_string())
    verify_lines.append(f"missing_canon (canonical values that DISAPPEARED after cleaning): {missing_canon}")
    rprint(f"  {col}: missing_canon={missing_canon}  (empty list = PASS, no canonical value vanished)")
with open(os.path.join(OUT_DIR, "03_fuzzy_verification_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(verify_lines))

# =====================================================================================
# 4.5 DATE PARSING AND STANDARDIZATION (date_of_admission, discharge_date)
# Business context = US (all 5 insurers are US insurers) -> documented assumption A3 used
# ONLY for genuinely ambiguous slash-dates where both MM/DD and DD/MM are calendar-valid.
# =====================================================================================
import calendar


MONTH_NAME_RE = re.compile(r"[A-Za-z]{3,}")

def try_parse_date(raw):
    """Returns (parsed_ts_or_None, format_label, ambiguous_bool, unparseable_bool)."""
    if pd.isna(raw):
        return None, None, False, False
    s = str(raw).strip()
    # ISO
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return pd.Timestamp(year=y, month=mo, day=d), "ISO_YYYY-MM-DD", False, False
        except (ValueError, OverflowError):
            return None, None, False, True  # e.g. 0000-00-00
    # Named month (contains letters) -> use dateutil, unambiguous by construction
    if MONTH_NAME_RE.search(s):
        try:
            ts = pd.Timestamp(pd.to_datetime(s, errors="raise"))
            return ts, "NAMED_MONTH", False, False
        except Exception:
            return None, None, False, True
    # Slash pattern D/D/YYYY
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        def valid(mo, d, y):
            if mo < 1 or mo > 12 or d < 1:
                return False
            try:
                last = calendar.monthrange(y, mo)[1]
            except Exception:
                return False
            return d <= last
        mmdd_valid = valid(a, b, y)   # a=month, b=day
        ddmm_valid = valid(b, a, y)   # b=month, a=day
        if mmdd_valid and not ddmm_valid:
            return pd.Timestamp(year=y, month=a, day=b), "SLASH_MM/DD/YYYY_unambiguous", False, False
        if ddmm_valid and not mmdd_valid:
            return pd.Timestamp(year=y, month=b, day=a), "SLASH_DD/MM/YYYY_unambiguous", False, False
        if mmdd_valid and ddmm_valid:
            # genuinely ambiguous -> resolve via documented business-context assumption (US = MM/DD/YYYY)
            return pd.Timestamp(year=y, month=a, day=b), "SLASH_AMBIGUOUS_resolved_MM/DD/YYYY_via_US_assumption", True, False
        return None, None, False, True
    # Dash numeric pattern D-D-YYYY (not named month, already excluded above)
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        def valid2(mo, d, y):
            if mo < 1 or mo > 12 or d < 1:
                return False
            try:
                last = calendar.monthrange(y, mo)[1]
            except Exception:
                return False
            return d <= last
        mmdd_valid = valid2(a, b, y)
        ddmm_valid = valid2(b, a, y)
        if mmdd_valid and not ddmm_valid:
            return pd.Timestamp(year=y, month=a, day=b), "DASH_MM-DD-YYYY_unambiguous", False, False
        if ddmm_valid and not mmdd_valid:
            return pd.Timestamp(year=y, month=b, day=a), "DASH_DD-MM-YYYY_unambiguous", False, False
        if mmdd_valid and ddmm_valid:
            return pd.Timestamp(year=y, month=a, day=b), "DASH_AMBIGUOUS_resolved_MM-DD-YYYY_via_US_assumption", True, False
        return None, None, False, True
    return None, None, False, True

def parse_date_col(col):
    unparse_flag = f"{col}_unparseable_flag"
    ambig_flag = f"{col}_ambiguous_date_flag"
    df[unparse_flag] = False
    df[ambig_flag] = False
    register_flag(unparse_flag, f"True if {col} raw value could not be parsed as any known date format (garbage/invalid, e.g. 0000-00-00, 31/31/2021)")
    register_flag(ambig_flag, f"True if {col} was a slash/dash date where both MM/DD and DD/MM readings were calendar-valid, resolved via documented US business-context assumption (brief A3)")

    n_iso = n_named = n_slash_unamb = n_dash_unamb = n_ambig = n_unparse = 0
    new_col = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    for idx in df[df[col].notna()].index:
        raw = df.loc[idx, col]
        ts, fmt, ambiguous, unparseable = try_parse_date(raw)
        row = df.loc[idx, "__source_row"]
        if unparseable:
            log("Stage4.5", col, row, "DATE_PARSED", raw, "", "UNPARSEABLE - genuinely invalid date pattern (e.g. 0000-00-00 or day/month both >31); left null, flagged, not guessed")
            df.loc[idx, unparse_flag] = True
            n_unparse += 1
            continue
        new_col.loc[idx] = ts
        iso_str = ts.strftime("%Y-%m-%d")
        if ambiguous:
            log("Stage4.5", col, row, "DATE_PARSED", raw, iso_str, f"format={fmt}; AMBIGUOUS slash/dash date, both interpretations calendar-valid, resolved via business-context assumption (US insurers -> MM/DD/YYYY), flagged for visibility")
            df.loc[idx, ambig_flag] = True
            n_ambig += 1
        else:
            log("Stage4.5", col, row, "DATE_PARSED", raw, iso_str, f"format={fmt}")
            if fmt == "ISO_YYYY-MM-DD": n_iso += 1
            elif fmt == "NAMED_MONTH": n_named += 1
            elif "SLASH" in fmt: n_slash_unamb += 1
            elif "DASH" in fmt: n_dash_unamb += 1
    df[col] = new_col
    return dict(iso=n_iso, named=n_named, slash_unamb=n_slash_unamb, dash_unamb=n_dash_unamb, ambiguous=n_ambig, unparseable=n_unparse)

rprint("\n4.5 DATE PARSING:")
doa_stats = parse_date_col(C_DOA)
rprint(f"  date_of_admission: {doa_stats}")
ddate_stats = parse_date_col(C_DDATE)
rprint(f"  discharge_date: {ddate_stats}")

# physically impossible: discharge before admission -> flag only (Stage 8 will filter)
both_present = df[C_DOA].notna() & df[C_DDATE].notna()
impossible = both_present & (df[C_DDATE] < df[C_DOA])
df["discharge_before_admission_flag"] = False
df.loc[impossible, "discharge_before_admission_flag"] = True
register_flag("discharge_before_admission_flag", "True if discharge_date < date_of_admission (physically impossible) - both dates present and parsed")
for idx in df[impossible].index:
    row = df.loc[idx, "__source_row"]
    log("Stage4.5", "discharge_date", row, "OUTLIER_FLAGGED", str(df.loc[idx, C_DDATE]), str(df.loc[idx, C_DDATE]),
        f"physically impossible: discharge_date < date_of_admission ({df.loc[idx, C_DOA]}) - flagged, NOT auto-swapped")
rprint(f"  discharge_before_admission_flag: {int(impossible.sum())} rows flagged (physically impossible, not corrected)")

# =====================================================================================
# 4.6 NUMERIC CLEANING: age, room_number, billing_amount, length_of_stay
# =====================================================================================

# ---- AGE ----
rprint("\n4.6 NUMERIC CLEANING: age")
n_yrs_stripped = n_wordnum_left_null = 0
for idx in df[df[C_AGE].notna()].index:
    v = str(df.loc[idx, C_AGE]).strip()
    row = df.loc[idx, "__source_row"]
    m = re.match(r"^(-?\d+)\s*yrs?\.?$", v, flags=re.IGNORECASE)
    if m:
        newv = m.group(1)
        log("Stage4.6", C_AGE, row, "NUMERIC_CLEANED", v, newv, "stripped unit suffix 'yrs'")
        df.loc[idx, C_AGE] = newv
        n_yrs_stripped += 1
    elif not re.fullmatch(r"-?\d+(\.\d+)?", v):
        log("Stage4.6", C_AGE, row, "NUMERIC_CLEANED", v, "", "unparseable word-number (e.g. 'thirty') - cannot guess numeric value, left null")
        df.loc[idx, C_AGE] = np.nan
        n_wordnum_left_null += 1
rprint(f"  yrs-suffix stripped: {n_yrs_stripped}  word-number left null: {n_wordnum_left_null}")
df[C_AGE] = pd.to_numeric(df[C_AGE], errors="coerce")

# ---- ROOM NUMBER ----
rprint("4.6 NUMERIC CLEANING: room_number")
n_room_prefix = n_room_quote = 0
for idx in df[df[C_ROOM].notna()].index:
    v = str(df.loc[idx, C_ROOM]).strip()
    row = df.loc[idx, "__source_row"]
    orig = v
    changed = False
    m = re.match(r"^Room\s+(\d+)$", v, flags=re.IGNORECASE)
    if m:
        v = m.group(1)
        n_room_prefix += 1
        changed = True
    if v.startswith("'"):
        v = v.lstrip("'")
        n_room_quote += 1
        changed = True
    if changed:
        log("Stage4.6", C_ROOM, row, "NUMERIC_CLEANED", orig, v, "stripped 'Room ' prefix and/or leading quote character")
        df.loc[idx, C_ROOM] = v
rprint(f"  'Room ' prefix stripped: {n_room_prefix}  leading-quote stripped: {n_room_quote}")
df[C_ROOM] = pd.to_numeric(df[C_ROOM], errors="coerce")

# ---- BILLING AMOUNT ----
rprint("4.6 NUMERIC CLEANING: billing_amount (locale survey: 374 rows w/ comma, 57220 w/ dot, 177 w/ both "
       "-> comma always thousands-separator position, dot always decimal position = US locale, applied uniformly)")
n_currency_stripped = n_dupsuffix_stripped = n_comma_stripped = n_sentinel = 0
CURRENCY_CHARS = r"[\$€£¥₹₩]"
for idx in df[df[C_BILL].notna()].index:
    v = str(df.loc[idx, C_BILL]).strip()
    row = df.loc[idx, "__source_row"]
    orig = v
    changed = False
    if re.search(CURRENCY_CHARS, v):
        v = re.sub(CURRENCY_CHARS, "", v).strip()
        n_currency_stripped += 1
        changed = True
    m = re.fullmatch(r"(\d+\.\d+)\.00", v)
    if m:
        v = m.group(1)
        n_dupsuffix_stripped += 1
        changed = True
    if "," in v:
        v = v.replace(",", "")
        n_comma_stripped += 1
        changed = True
    if changed:
        log("Stage4.6", C_BILL, row, "NUMERIC_CLEANED", orig, v,
            "currency symbol / duplicate '.NN.00' suffix / thousands comma stripped (US locale: comma=thousands, dot=decimal)")
        df.loc[idx, C_BILL] = v
df[C_BILL] = pd.to_numeric(df[C_BILL], errors="coerce")
rprint(f"  currency symbols stripped: {n_currency_stripped}  duplicate-suffix (.NN.00) stripped: {n_dupsuffix_stripped}  thousands-comma stripped: {n_comma_stripped}")

# sentinel 999999 -> null (numeric placeholder, not a real charge)
sentinel_mask = df[C_BILL].notna() & (df[C_BILL].round(2) == 999999.0)
df["billing_amount_sentinel_flag"] = False
df.loc[sentinel_mask, "billing_amount_sentinel_flag"] = True
register_flag("billing_amount_sentinel_flag", "True if billing_amount was the exact placeholder sentinel 999999 - treated as missing, not a real charge")
for idx in df[sentinel_mask].index:
    row = df.loc[idx, "__source_row"]
    log("Stage4.6", C_BILL, row, "NULL_STANDARDIZED", "999999", "", "numeric sentinel placeholder (exact-value 999999, out of range vs column distribution) - not a real charge, treated as missing")
n_sentinel = int(sentinel_mask.sum())
df.loc[sentinel_mask, C_BILL] = np.nan
rprint(f"  999999 sentinel nulled: {n_sentinel}")

# ---- LENGTH OF STAY ----
rprint("4.6 NUMERIC CLEANING: length_of_stay (cast to numeric)")
df[C_LOS] = pd.to_numeric(df[C_LOS], errors="coerce")

# =====================================================================================
# 4.9 IMPOSSIBLE NEGATIVE VALUE HANDLING - decided PER COLUMN per business brief BR1/BR2/BR3.
# No blanket abs(). age & length_of_stay: unambiguous sign-flip errors -> corrected.
# billing_amount: possible legitimate refund/credit -> flagged only, NEVER corrected.
# =====================================================================================
def handle_negative(col, correct, br_id, br_text):
    vals = df[col]
    neg_mask = vals.notna() & (vals < 0)
    flagcol = f"{col}_sign_flag"
    df[flagcol] = False
    df.loc[neg_mask, flagcol] = True
    register_flag(flagcol, f"True if {col} was negative in source ({'corrected via abs()' if correct else 'NOT corrected - flagged only'}) - {br_id}")
    for idx in df[neg_mask].index:
        row = df.loc[idx, "__source_row"]
        orig = df.loc[idx, col]
        if correct:
            newv = abs(orig)
            log("Stage4.9", col, row, "NEGATIVE_CORRECTED", orig, newv, f"{br_id}: {br_text}")
            df.loc[idx, col] = newv
        else:
            log("Stage4.9", col, row, "NEGATIVE_FLAGGED", orig, orig, f"{br_id}: {br_text}")
    return int(neg_mask.sum())

rprint("\n4.9 IMPOSSIBLE NEGATIVE VALUE HANDLING (per-column decision, no blanket abs()):")
n_age_neg = handle_negative(C_AGE, True, "BR1",
    "age cannot legitimately be negative under any interpretation - unambiguous sign-flip data-entry error, abs() applied")
rprint(f"  age: {n_age_neg} negative values found -> CORRECTED (abs()) per BR1")

n_bill_neg = handle_negative(C_BILL, False, "BR2",
    "a negative billing_amount may be a legitimate refund/credit/adjustment - sign-flipping would erase real information; flagged for review, NOT corrected")
rprint(f"  billing_amount: {n_bill_neg} negative values found -> FLAGGED ONLY, left as-is per BR2")

n_los_neg = handle_negative(C_LOS, True, "BR3",
    "length_of_stay is a duration and cannot be legitimately negative (no 'credit' interpretation exists unlike billing) - abs() applied")
rprint(f"  length_of_stay: {n_los_neg} negative values found -> CORRECTED (abs()) per BR3")

# room_number: domain floor is 101 in this hospital (observed min=101 after cleaning); check for negatives defensively
n_room_neg = handle_negative(C_ROOM, False, "N/A",
    "room_number negatives not expected/observed in this dataset; flagged only if found, never corrected (no basis to guess the intended room)")
rprint(f"  room_number: {n_room_neg} negative values found (flag-only policy, none expected)")

# age domain outlier (>110) - flagged, NOT corrected (kept for Stage 8 as a statistical oddity)
age_outlier_mask = df[C_AGE].notna() & (df[C_AGE] > 110)
df["age_domain_outlier_flag"] = False
df.loc[age_outlier_mask, "age_domain_outlier_flag"] = True
register_flag("age_domain_outlier_flag", "True if age > 110 - implausible but not a generic 10x-median statistical outlier (median~52, so 10x rule would not catch this); domain-specific ceiling, flagged not corrected")
for idx in df[age_outlier_mask].index:
    row = df.loc[idx, "__source_row"]
    v = df.loc[idx, C_AGE]
    log("Stage4.9", C_AGE, row, "OUTLIER_FLAGGED", v, v, "age > 110 - implausible but not impossible; domain-outlier flag, not corrected")
rprint(f"  age domain outlier (>110): {int(age_outlier_mask.sum())} rows flagged, not corrected")

# =====================================================================================
# 4.10 OUTLIER INVESTIGATION (decimal-typo detection). Screen at 10x median (below the
# smallest repairable error) per spec, test divisors 10/100/1000 in ascending order.
# =====================================================================================
def outlier_screen(col, exclude_mask=None):
    typo_flag = f"{col}_decimal_typo_flag"
    outlier_flag = f"{col}_outlier_flag"
    df[typo_flag] = False
    df[outlier_flag] = False
    register_flag(typo_flag, f"True if {col} was corrected as a likely decimal-typo (value/10 or value/100 landed in the plausible band around the column median)")
    register_flag(outlier_flag, f"True if {col} was flagged as a statistical outlier (>10x median, no divisor restored plausibility) or a d=1000 candidate (flagged, not corrected - more likely a unit mismatch)")

    valid_mask = df[col].notna()
    if exclude_mask is not None:
        valid_mask = valid_mask & (~exclude_mask)
    vals = df.loc[valid_mask, col]
    median = vals.median()
    before_median, before_min, before_max = vals.median(), vals.min(), vals.max()
    before_q1, before_q3 = vals.quantile(0.25), vals.quantile(0.75)
    before_iqr = before_q3 - before_q1

    if median <= 0:
        rprint(f"  {col}: median <= 0 ({median}) - ratio-to-median screen skipped (documented, per spec); no decimal-typo screening performed for this column")
        return

    candidates_idx = vals[vals > 10 * median].index
    n_candidates = len(candidates_idx)
    n_corrected_d10 = n_corrected_d100 = n_flagged_d1000 = n_stat_outlier = 0
    corrections = []  # (idx, divisor) to apply after sanity-rate check
    for idx in candidates_idx:
        v = df.loc[idx, col]
        found_d = None
        for d in (10, 100, 1000):
            ratio = v / d
            if 0.5 * median <= ratio <= 2 * median:
                found_d = d
                break
        if found_d in (10, 100):
            corrections.append((idx, found_d))
        elif found_d == 1000:
            n_flagged_d1000 += 1
        else:
            n_stat_outlier += 1

    # sanity-check repair rate before applying any correction
    repair_rate = len(corrections) / len(vals) if len(vals) else 0
    if repair_rate > 0.01:
        rprint(f"  {col}: {len(corrections)}/{len(vals)} ({100*repair_rate:.2f}%) would be 'corrected' as decimal typos - "
               f"EXCEEDS 1% sanity threshold. NOT auto-correcting; reporting as a scale/unit issue instead. All candidates flagged as outliers only.")
        for idx, d in corrections:
            row = df.loc[idx, "__source_row"]
            v = df.loc[idx, col]
            log("Stage4.10", col, row, "OUTLIER_FLAGGED", v, v, f"candidate decimal-typo (would-be /={d}) but column-wide repair rate {100*repair_rate:.2f}% exceeds 1% sanity threshold - treated as scale/unit issue, NOT corrected")
            df.loc[idx, outlier_flag] = True
        for idx in candidates_idx:
            if idx not in [c[0] for c in corrections]:
                row = df.loc[idx, "__source_row"]
                v = df.loc[idx, col]
                log("Stage4.10", col, row, "OUTLIER_FLAGGED", v, v, "statistical outlier (>10x median, no divisor restored plausibility) - flagged, not corrected; may be genuinely large/valid")
                df.loc[idx, outlier_flag] = True
    else:
        for idx, d in corrections:
            row = df.loc[idx, "__source_row"]
            v = df.loc[idx, col]
            newv = v / d
            log("Stage4.10", col, row, "OUTLIER_DECIMAL_TYPO_CORRECTED", v, newv, f"value > 10x median ({median:.2f}); value/{d} = {newv:.2f} lands in plausible band [0.5x,2x] median - corrected")
            df.loc[idx, col] = newv
            df.loc[idx, typo_flag] = True
            if d == 10: n_corrected_d10 += 1
            else: n_corrected_d100 += 1
        for idx in df[outlier_flag].index:
            pass
        for idx in candidates_idx:
            if idx not in [c[0] for c in corrections]:
                row = df.loc[idx, "__source_row"]
                v = df.loc[idx, col]
                if v / 1000 >= 0.5*median and v/1000 <= 2*median:
                    log("Stage4.10", col, row, "OUTLIER_FLAGGED", v, v, f"WARNING: value/1000 lands in plausible band but d=1000 is more likely a unit mismatch (e.g. grams vs kg) than a typo - flagged, NOT silently divided")
                else:
                    log("Stage4.10", col, row, "OUTLIER_FLAGGED", v, v, "statistical outlier (>10x median, no divisor restored plausibility) - flagged, not corrected; may be genuinely large/valid")
                df.loc[idx, outlier_flag] = True

    after_vals = df.loc[valid_mask, col]
    after_median, after_min, after_max = after_vals.median(), after_vals.min(), after_vals.max()
    rprint(f"  {col}: candidates(>10x median)={n_candidates} corrected_d10={n_corrected_d10} corrected_d100={n_corrected_d100} "
           f"flagged_d1000_or_statistical={n_candidates-len(corrections)}")
    rprint(f"    VERIFY median/min/max before -> after: median {before_median:.2f}->{after_median:.2f}  min {before_min:.2f}->{after_min:.2f}  max {before_max:.2f}->{after_max:.2f}")

rprint("\n4.10 OUTLIER INVESTIGATION (decimal-typo detection, screened at 10x median):")
outlier_screen(C_BILL, exclude_mask=(df[f"{C_BILL}_sign_flag"] if f"{C_BILL}_sign_flag" in df.columns else None))
outlier_screen(C_AGE)
outlier_screen(C_ROOM)
outlier_screen(C_LOS)

# =====================================================================================
# LOS QA cross-check vs (discharge_date - date_of_admission), flag mismatch only, never overwrite
# =====================================================================================
qa_mask = (df[C_DOA].notna() & df[C_DDATE].notna() & df[C_LOS].notna() &
           (~df[f"{C_DOA}_unparseable_flag"]) & (~df[f"{C_DDATE}_unparseable_flag"]))
recomputed = (df[C_DDATE] - df[C_DOA]).dt.days
mismatch_mask = qa_mask & (recomputed != df[C_LOS])
df["length_of_stay_qa_mismatch_flag"] = False
df.loc[mismatch_mask, "length_of_stay_qa_mismatch_flag"] = True
register_flag("length_of_stay_qa_mismatch_flag", "True if cleaned length_of_stay disagrees with (discharge_date - date_of_admission) recomputed from cleaned dates - QA flag only, source length_of_stay value is NOT overwritten")
for idx in df[mismatch_mask].index:
    row = df.loc[idx, "__source_row"]
    log("Stage4.10", C_LOS, row, "OUTLIER_FLAGGED", df.loc[idx, C_LOS], df.loc[idx, C_LOS],
        f"QA cross-check mismatch: recomputed (discharge_date-date_of_admission)={recomputed.loc[idx]} days vs source length_of_stay={df.loc[idx, C_LOS]} - flagged, source value NOT overwritten")
rprint(f"\nLOS QA cross-check: {int(qa_mask.sum())} rows checkable, {int(mismatch_mask.sum())} mismatches flagged (source value preserved)")

# =====================================================================================
# 4.11 DUPLICATE REMOVAL
# =====================================================================================
rprint("\n4.11 DUPLICATE REMOVAL:")
dup_cols = [c for c in df.columns if c != "__source_row"]
exact_dup_mask = df.duplicated(subset=dup_cols, keep="first")
n_exact_dup = int(exact_dup_mask.sum())
dup_rows_removed = df.loc[exact_dup_mask, "__source_row"].tolist()
for idx in df[exact_dup_mask].index:
    row = df.loc[idx, "__source_row"]
    log("Stage4.11", "ALL", row, "DUPLICATE_REMOVED", "", "", "exact full-row duplicate (all columns identical, excluding __source_row) - kept first occurrence, removed this one")
rows_before_dedup = len(df)
df = df[~exact_dup_mask].copy()
rprint(f"  exact duplicates removed: {n_exact_dup}  (rows: {rows_before_dedup} -> {len(df)})")

# near-duplicate flag on composite key (name, date_of_admission, doctor, hospital) - flag only, no ID exists
composite_key = df[C_NAME].astype(str) + "||" + df[C_DOA].astype(str) + "||" + df[C_DOC].astype(str) + "||" + df[C_HOSP].astype(str)
dup_key_counts = composite_key.value_counts()
colliding_keys = dup_key_counts[dup_key_counts > 1].index
near_dup_mask = composite_key.isin(colliding_keys)
df["near_duplicate_composite_key_flag"] = near_dup_mask.values
register_flag("near_duplicate_composite_key_flag", "True if (name, date_of_admission, doctor, hospital) collides with another row - no true unique ID exists in source (brief A2), so this is FLAGGED for review only, never auto-removed")
n_near_dup = int(near_dup_mask.sum())
for idx in df[near_dup_mask].index:
    row = df.loc[idx, "__source_row"]
    log("Stage4.11", "ALL", row, "NEAR_DUPLICATE_FLAGGED", "", "", "composite key (name,date_of_admission,doctor,hospital) collides with >=1 other row - flagged for review, NOT auto-removed (no true unique ID exists to confirm true duplication)")
rprint(f"  near-duplicate composite-key collisions flagged (not removed): {n_near_dup} rows across {len(colliding_keys)} colliding key-groups")

# =====================================================================================
# WRITE OUTPUTS: intermediate cleaned csv, changelog (canonical + user-requested alias), flag registry, report
# =====================================================================================
change_log_df = pd.DataFrame(CHANGE_LOG, columns=["STAGE","COLUMN","SOURCE_ROW","CHANGE_TYPE","ORIGINAL_VALUE","NEW_VALUE","REASON"])
change_log_df.to_csv(os.path.join(OUT_DIR, "change_log.csv"), index=False, encoding="utf-8")
change_log_df.to_csv(os.path.join(OUT_DIR, "change_log.csv"), index=False, encoding="utf-8")
rprint(f"\nchange_log.csv / change_log.csv written: {len(change_log_df)} change-log rows")

df.to_csv(os.path.join(OUT_DIR, "03_intermediate_cleaned.csv"), index=False, encoding="utf-8")
rprint(f"03_intermediate_cleaned.csv written: {df.shape}")

with open(os.path.join(OUT_DIR, "03_flag_registry.json"), "w", encoding="utf-8") as f:
    json.dump(FLAG_REGISTRY, f, indent=2)
rprint(f"03_flag_registry.json written: {len(FLAG_REGISTRY)} flags registered")
for k, v in FLAG_REGISTRY.items():
    rprint(f"  FLAG {k}: {v}")

rprint(f"\n=== STAGE 4 SUMMARY ===")
rprint(f"raw rows: {RAW_ROWS}  post-Stage4 rows (after exact-dup removal): {len(df)}  exact duplicates removed: {n_exact_dup}")
rprint(f"total change-log entries: {len(change_log_df)}")

with open(os.path.join(OUT_DIR, "03_stage4_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(report))
print("\n=== stage4_clean.py COMPLETE ===")
print("Final shape:", df.shape)
print("Change log rows:", len(change_log_df))
