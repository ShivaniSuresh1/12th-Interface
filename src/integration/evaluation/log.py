"""Per-scenario logging for the evaluation harness (Phase 1, step 3).

One CSV per participant in eval_logs/ (gitignored: it's participant
data). Each row is written and flushed the moment a scenario is answered,
so a crash or an early quit never loses earlier answers.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Self

LOG_DIR = Path("eval_logs")

FIELDS = [
    "participant",
    "position",  # 1-based order this participant saw the scenario in
    "scenario_id",
    "condition",  # "explanation" | "plain"
    "decided_on",  # "recommendation" | "proposal"
    "proposal_action",  # move | shorten | defer | ask | "" (no disruption)
    "energy_level",
    "recommended_task_type",
    "decision",  # accept | edit | reject
    "edit_note",  # free text, only when decision == edit
    "trust",  # 1-7: how much they trust the planner's suggestion
    "confidence",  # 1-7: how confident they are in their own decision
    "decision_time_s",  # seconds from scenario shown to a/e/r answered
    "timestamp",  # wall-clock time the row was written (ISO 8601)
]


def log_path(participant: int, log_dir: Path = LOG_DIR) -> Path:
    return log_dir / f"participant_{participant:02d}.csv"


class SessionLog:
    """Append-only CSV for one participant. Refuses to overwrite an old session."""

    def __init__(self, participant: int, log_dir: Path = LOG_DIR) -> None:
        self.path = log_path(participant, log_dir)
        if self.path.exists():
            raise FileExistsError(
                f"{self.path} already exists. Use a new participant number, or move "
                "the old file away if this really is a re-run."
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=FIELDS)
        self._writer.writeheader()
        self._file.flush()

    def write(self, row: dict) -> None:
        missing = set(FIELDS) - set(row)
        if missing:
            raise ValueError(f"log row is missing {sorted(missing)}")
        self._writer.writerow({k: row[k] for k in FIELDS})
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
