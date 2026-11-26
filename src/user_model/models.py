"""Data model for the User Model component (owner: Shivani).

Field names here are frozen by docs/CONTRACTS.md -- add methods freely,
but don't add/rename/reorder dataclass fields without a team conversation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, NotRequired, TypedDict

ENERGY_SOURCES = ("baseline", "checkin_corrected")

# Version of the to_dict()/from_dict() format. Bump it if the dict shape changes,
# so stored profiles written by an older version are rejected instead of misread.
SCHEMA_VERSION = 1

# Number of check-in-corrected reports before a student leaves cold start
# (Q2). Until then, other modules should lean on default rules.
COLD_START_MIN_CHECKINS = 5


class Event(TypedDict):
    """Shape of one entry in `StudentSchedule.events` (shared with negotiation).

    `kind` is required, one of:
      "study"    -- a planned study session (negotiation checks in at its edges)
      "break"    -- a break between study sessions
      "class", "meeting", "other" -- fixed commitments, not check-in points
      "deadline" -- uses `start` as the due time; `end` may be omitted
      "sleep"    -- last night's sleep; the User Model uses its `end` as the
                    wake time and its length as sleep_hours

    `start`/`end` are datetimes or ISO-8601 strings. Naive times mean the
    student's local time. Events whose times can't be read are skipped.
    """

    kind: str
    start: datetime | str
    end: NotRequired[datetime | str]
    title: NotRequired[str]
    session_id: NotRequired[str]
    task_type: NotRequired[str]  # a domain_model TaskType value, for "study"


@dataclass
class StudentSchedule:
    """A student's known commitments (classes, meetings, deadlines, sleep)."""

    student_id: str
    events: list[dict] = field(default_factory=list)  # each is an `Event`

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe copy: datetimes inside events become ISO-8601 strings."""
        events = [
            {k: v.isoformat() if isinstance(v, datetime) else v for k, v in e.items()}
            if isinstance(e, dict)
            else e
            for e in self.events
        ]
        return {"student_id": self.student_id, "events": events}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StudentSchedule:
        """Inverse of `to_dict`. Event `start`/`end` strings become datetimes again
        (unreadable ones are kept as-is; `_readable` skips them, as before)."""
        events = []
        for e in data.get("events", []):
            if isinstance(e, dict):
                e = {**e, **{k: _from_iso(e[k]) for k in ("start", "end") if k in e}}
            events.append(e)
        return cls(student_id=data["student_id"], events=events)

    def last_sleep_before(self, at: datetime) -> dict | None:
        """Most recent "sleep" event that ended at or before `at`.

        The returned event's `start`/`end` are normalized to aware datetimes.
        """
        at = as_aware(at)
        sleeps = [e for e in self._readable("sleep", "end") if e["end"] <= at]
        return max(sleeps, key=lambda e: e["end"], default=None)

    def upcoming_deadlines(self, after: datetime) -> list[dict]:
        """Deadlines due after `after`, soonest first (times normalized)."""
        after = as_aware(after)
        due = [e for e in self._readable("deadline", "start") if e["start"] > after]
        return sorted(due, key=lambda e: e["start"])

    def _readable(self, kind: str, required: str) -> list[dict]:
        """Copies of `kind` events with their times parsed; unreadable ones dropped."""
        out = []
        for e in self.events:
            if not isinstance(e, dict) or e.get("kind") != kind:
                continue
            times = {k: parse_time(e[k]) for k in ("start", "end") if k in e}
            if times.get(required) is None or None in times.values():
                continue
            out.append({**e, **times})
        return out


@dataclass
class EnergyReport:
    """A point-in-time energy estimate for a student.

    `energy_level` is 0.0 (exhausted) .. 1.0 (fully energized). `source`
    distinguishes a sleep-based baseline from a check-in-corrected value,
    per the Q1 hybrid design.
    """

    student_id: str
    timestamp: datetime
    energy_level: float
    source: str  # "baseline" | "checkin_corrected"

    def __post_init__(self) -> None:
        if not 0.0 <= self.energy_level <= 1.0:
            raise ValueError(f"energy_level must be in [0.0, 1.0], got {self.energy_level}")
        if self.source not in ENERGY_SOURCES:
            raise ValueError(f"source must be one of {ENERGY_SOURCES}, got {self.source!r}")

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe copy (timestamp as an ISO-8601 string)."""
        return {
            "student_id": self.student_id,
            "timestamp": self.timestamp.isoformat(),
            "energy_level": self.energy_level,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnergyReport:
        """Inverse of `to_dict`. Raises ValueError on an unreadable timestamp or
        an invalid level/source, the same checks as constructing one directly."""
        raw = data["timestamp"]
        try:
            timestamp = raw if isinstance(raw, datetime) else datetime.fromisoformat(raw)
        except (TypeError, ValueError) as e:
            raise ValueError(f"unreadable timestamp: {raw!r}") from e
        return cls(
            student_id=data["student_id"],
            timestamp=timestamp,
            energy_level=float(data["energy_level"]),
            source=data["source"],
        )


@dataclass
class StudentProfile:
    """Everything the User Model tracks about one student."""

    student_id: str
    sleep_hours: float | None = None
    schedule: StudentSchedule | None = None
    cold_start: bool = True  # True until enough real check-ins exist (Q2)
    energy_history: list[EnergyReport] = field(default_factory=list)

    def checkin_reports(self) -> list[EnergyReport]:
        """History entries that carry a real self-report signal."""
        return [r for r in self.energy_history if r.source == "checkin_corrected"]

    def record_energy(self, report: EnergyReport) -> None:
        """Append a report to history and update the cold-start flag (Q2)."""
        self.energy_history.append(report)
        self.cold_start = len(self.checkin_reports()) < COLD_START_MIN_CHECKINS

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe copy of the whole profile, for storage (e.g. `json.dumps`)."""
        return {
            "schema_version": SCHEMA_VERSION,
            "student_id": self.student_id,
            "sleep_hours": self.sleep_hours,
            "schedule": self.schedule.to_dict() if self.schedule is not None else None,
            "cold_start": self.cold_start,
            "energy_history": [r.to_dict() for r in self.energy_history],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StudentProfile:
        """Inverse of `to_dict`. Missing optional keys fall back to the defaults
        of a new profile; a different `schema_version` raises ValueError."""
        version = data.get("schema_version", SCHEMA_VERSION)
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"stored profile has schema_version {version}, expected {SCHEMA_VERSION}"
            )
        schedule = data.get("schedule")
        sleep_hours = data.get("sleep_hours")
        return cls(
            student_id=data["student_id"],
            sleep_hours=float(sleep_hours) if sleep_hours is not None else None,
            schedule=StudentSchedule.from_dict(schedule) if schedule is not None else None,
            cold_start=bool(data.get("cold_start", True)),
            energy_history=[EnergyReport.from_dict(r) for r in data.get("energy_history", [])],
        )


def as_aware(dt: datetime) -> datetime:
    """Treat naive datetimes as local time so all comparisons are tz-aware."""
    return dt if dt.tzinfo is not None else dt.astimezone()


def _from_iso(value: object) -> object:
    """An ISO-8601 string as a datetime, exactly as written (a naive time stays
    naive); anything else, including an unreadable string, is returned unchanged."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def parse_time(value: object) -> datetime | None:
    """A datetime or ISO-8601 string as an aware datetime, or None if unreadable."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    return as_aware(value) if isinstance(value, datetime) else None
