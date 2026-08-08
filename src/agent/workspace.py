"""Workspace folder layout.

Each stage of the pipeline reads from one folder and writes to the next:

    workspace/
    ├── 00_landing/    raw extracted data (parquet)
    ├── 10_profiled/   profile.json (the agent's view of the data)
    ├── 20_cleaned/    cleaned.parquet + cleaning_log.txt
    └── 99_final/      final_dataset.csv + report.md   ← deliverables

This separation creates a clean audit trail and lets you re-run any
single stage without redoing the rest.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Workspace:
    root: Path

    @property
    def landing(self) -> Path:
        return self.root / "00_landing"

    @property
    def profiled(self) -> Path:
        return self.root / "10_profiled"

    @property
    def cleaned(self) -> Path:
        return self.root / "20_cleaned"

    @property
    def final(self) -> Path:
        return self.root / "99_final"

    def reset(self) -> None:
        """Wipe and recreate every stage directory. Each run starts fresh."""
        if self.root.exists():
            shutil.rmtree(self.root)
        for stage in (self.landing, self.profiled, self.cleaned, self.final):
            stage.mkdir(parents=True, exist_ok=True)

    def stage_input(self, source_csv: Path) -> Path:
        """Copy the user's CSV into the landing zone as input.csv."""
        source_csv = Path(source_csv)
        if not source_csv.exists():
            raise FileNotFoundError(f"Input CSV not found: {source_csv}")
        dest = self.landing / "input.csv"
        shutil.copy(source_csv, dest)
        return dest
