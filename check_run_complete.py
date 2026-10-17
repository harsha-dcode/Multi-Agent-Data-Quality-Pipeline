#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check_run_complete.py — deterministic completeness gate for a pipeline run.

The agent spec REQUIRES six artifacts. A spec requirement is an instruction, and
an instruction is something a model can skip: across seven prior runs, three
produced a business brief and four did not, and nothing detected the difference.

This script is the part that cannot be skipped. Run it after every invocation.

    python check_run_complete.py <output_dir>

Exit 0 = the run is complete and structurally sound.
Exit 1 = the run is incomplete. It is NOT a successful run, whatever it reported.

This is the "move the check out of the prompt and into the harness" fix:
the agent decides WHAT to clean; this decides whether the run counts.
"""
import os
import sys
import csv

REQUIRED = {
    "01_business_brief.yaml": 200,     # (filename, minimum plausible bytes)
    "cleaned_data.csv":       500,
    "viz_ready.csv":          500,
    "change_log.csv":         100,
    "validation_report.md":   200,
    "insights_report.md":     500,
}

# accepted alternates, because older runs used other names
#
# The *_sample_1000.csv names are not legacy: healthcare, housing and logistics
# produce 17-29 MB of cleaned output, so case_studies/README.md commits a
# 1,000-row sample for those three and keeps the full file out of git. The gate
# runs in CI against the checked-out tree, so it has to recognise the sample as
# the committed form of the artifact. It still prints which name it matched --
# a sample standing in for the full output is worth seeing, not hiding.
ALTERNATES = {
    "change_log.csv":       ["changelog.csv", "cleaning_log.csv"],
    "validation_report.md": ["validation_report.txt"],
    "cleaned_data.csv":     ["cleaned.csv", "final_dataset.csv",
                             "cleaned_data_sample_1000.csv"],
    "viz_ready.csv":        ["viz_ready_sample_1000.csv"],
}

GREEN, RED, YELLOW, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
if os.name == "nt" and not os.environ.get("WT_SESSION"):
    GREEN = RED = YELLOW = RESET = ""


def resolve(outdir, name):
    """Return the path that satisfies `name`, or None."""
    p = os.path.join(outdir, name)
    if os.path.isfile(p):
        return p
    for alt in ALTERNATES.get(name, []):
        pa = os.path.join(outdir, alt)
        if os.path.isfile(pa):
            return pa
    # one level down (some runs nest under briefs/ or 99_final/)
    for root, _dirs, files in os.walk(outdir):
        for cand in [name] + ALTERNATES.get(name, []):
            if cand in files:
                return os.path.join(root, cand)
    return None


def check_brief(path):
    """The brief must carry per-column decisions, not a blanket rule."""
    problems = []
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            b = yaml.safe_load(f)
    except ImportError:
        return ["pyyaml not installed — could not validate brief contents"]
    except Exception as e:
        return [f"brief is not valid YAML: {e}"]

    if not isinstance(b, dict):
        return ["brief did not parse to a mapping"]

    # --- the REQUIRED core. Absence of any of these causes silent data loss.
    REQUIRED_KEYS = ["dataset", "grain", "critical_columns",
                     "allowed_values", "dangerous_columns", "missing_value_strategy"]
    for key in REQUIRED_KEYS:
        if key not in b:
            problems.append(f"brief is missing REQUIRED key: {key}")

    # dangerous_columns: {} is a valid, meaningful answer ("guard ran, nothing tripped").
    # dangerous_columns absent is not — it is indistinguishable from never checking.
    # That distinction is handled above; no emptiness check here, by design.

    # --- optional keys: report as advisory only, never fail the run
    OPTIONAL_KEYS = ["dataset_type", "business_goal", "column_types",
                     "not_critical", "business_rules", "assumptions", "risks"]
    absent = [k for k in OPTIONAL_KEYS if k not in b]
    if absent:
        print(f"  {YELLOW}NOTE{RESET}       brief omits optional keys "
              f"({len(absent)}/{len(OPTIONAL_KEYS)}): {', '.join(absent)}")
        print(f"             not a failure — an omitted key is an honest "
              f"'not established'.")

    mvs = b.get("missing_value_strategy")
    if isinstance(mvs, dict):
        # a blanket rule looks like {categoricals: mode, numerics: median}
        blanket = {"categoricals", "numerics", "categorical", "numeric", "all"}
        hits = blanket & set(map(str.lower, map(str, mvs.keys())))
        if hits:
            problems.append(
                f"missing_value_strategy uses BLANKET keys {sorted(hits)} — "
                "must be per column (this is the defect that fabricated 6,126 cells)")
        if len(mvs) < 2:
            problems.append("missing_value_strategy has fewer than 2 columns — looks unfilled")
    elif mvs is not None:
        problems.append("missing_value_strategy is not a mapping")

    return problems


def check_changelog(path):
    problems = []
    try:
        with open(path, encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            header = next(r, [])
            n = sum(1 for _ in r)
    except Exception as e:
        return [f"changelog unreadable: {e}"]
    low = [h.strip().lower() for h in header]
    for need in ["column", "change_type", "original_value"]:
        if not any(need in h for h in low):
            problems.append(f"changelog has no '{need}' column — cannot reconstruct originals")
    if n == 0:
        problems.append("changelog has zero entries")
    return problems


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    outdir = sys.argv[1]
    if not os.path.isdir(outdir):
        print(f"{RED}not a directory: {outdir}{RESET}")
        return 2

    print(f"\nchecking: {os.path.abspath(outdir)}\n")
    print(f"  {'artifact':26s} {'status':10s} {'size':>10s}   note")
    print("  " + "-" * 72)

    failures = []
    for name, min_bytes in REQUIRED.items():
        path = resolve(outdir, name)
        if path is None:
            print(f"  {name:26s} {RED}MISSING{RESET}    {'-':>10s}   required artifact absent")
            failures.append(f"{name} missing")
            continue
        size = os.path.getsize(path)
        note = ""
        if os.path.basename(path) != name:
            note = f"matched alternate '{os.path.basename(path)}'"
        if size < min_bytes:
            print(f"  {name:26s} {RED}TOO SMALL{RESET}  {size:>10,}   under {min_bytes} bytes — likely a stub")
            failures.append(f"{name} too small ({size} bytes)")
        else:
            print(f"  {name:26s} {GREEN}OK{RESET}         {size:>10,}   {note}")

    # ---- content checks on the two artifacts that carry the audit trail
    print()
    brief = resolve(outdir, "01_business_brief.yaml")
    if brief:
        for p in check_brief(brief):
            print(f"  {YELLOW}BRIEF{RESET}      {p}")
            failures.append(f"brief: {p}")

    cl = resolve(outdir, "change_log.csv")
    if cl:
        for p in check_changelog(cl):
            print(f"  {YELLOW}CHANGELOG{RESET}  {p}")
            failures.append(f"changelog: {p}")

    print("\n" + "=" * 74)
    if failures:
        print(f"{RED}RUN INCOMPLETE — {len(failures)} problem(s){RESET}")
        for f in failures:
            print(f"   - {f}")
        print("\nThis run does not count as successful, whatever the agent reported.")
        print("=" * 74)
        return 1

    print(f"{GREEN}RUN COMPLETE — all six artifacts present and structurally sound.{RESET}")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
