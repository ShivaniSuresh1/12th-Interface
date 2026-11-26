"""Saving students between runs (Phase 3, step 9).

One JSON file per student in profiles/ (gitignored, it's personal data).
The file holds Shivani's `StudentProfile.to_dict()` and Vyshnavi's
`StudentTaskMapping.to_dict()` unchanged (both schema_version 1), plus the
dashboard's own state. JSON was picked over SQLite: one student = one small
file, nothing to install, easy to inspect, and both dicts were designed to
fit either. Swapping in SQLite later only touches this file.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .dashboard import DashboardSession, now_local

PROFILE_DIR = Path("profiles")


def student_id_for(name: str) -> str:
    """'Priya S.' -> 'priya-s'. Raises ValueError if nothing usable is left."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        raise ValueError("Please enter a name with at least one letter or number.")
    return slug


class ProfileStore:
    def __init__(self, directory: Path = PROFILE_DIR) -> None:
        self.directory = Path(directory)

    def path(self, student_id: str) -> Path:
        return self.directory / f"{student_id}.json"

    def exists(self, student_id: str) -> bool:
        return self.path(student_id).exists()

    def students(self) -> list[tuple[str, str]]:
        """(student_id, display name) for everyone saved, sorted by name."""
        found = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                found.append((data["student_id"], data.get("name") or data["student_id"]))
            except (OSError, ValueError, KeyError):
                continue  # skip unreadable files rather than crash the app
        return sorted(found, key=lambda s: s[1].lower())

    def save(self, session: DashboardSession) -> Path:
        """Write atomically (temp file + rename) so a crash never leaves half a profile."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(session.student_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(session.to_dict(), indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        return path

    def load(
        self, student_id: str, clock: Callable[[], datetime] = now_local
    ) -> DashboardSession:
        data = json.loads(self.path(student_id).read_text(encoding="utf-8"))
        return DashboardSession.from_dict(data, clock=clock)
