"""Lenient reader for schedule events. Internal to negotiation.

Reads `user_model.StudentSchedule.events`, whose shape is agreed with User
Model (`user_model.models.Event`). Anything unreadable is skipped instead of
crashing. The keys negotiation uses:

    {
        "start": datetime | ISO-8601 str,   # required
        "end": datetime | ISO-8601 str,     # required, after start
        "kind": "study" | "break" | <anything else, e.g. "class", "meeting">,  # required
        "session_id": str,                  # optional
        "title": str,                       # optional, used in narration
        "task_type": str,                   # optional, a domain_model TaskType value
    }

Events with no "kind" are skipped. Mixed naive/aware times are fine: naive
ones are read as the student's local time, matching user_model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

STUDY_KINDS = {"study", "study_session", "session"}
BREAK_KINDS = {"break"}


@dataclass(frozen=True)
class Event:
    start: datetime
    end: datetime
    kind: str
    session_id: str | None
    title: str | None
    task_type: str | None

    @property
    def is_study(self) -> bool:
        return self.kind in STUDY_KINDS

    @property
    def is_break(self) -> bool:
        return self.kind in BREAK_KINDS

    @property
    def label(self) -> str:
        return self.title or self.session_id or "your next session"


def _to_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def raw_events(schedule: object) -> list:
    """Pull the event list out of a StudentSchedule, a dict, or a bare list."""
    if schedule is None:
        return []
    if isinstance(schedule, list):
        return schedule
    if isinstance(schedule, dict):
        return schedule.get("events") or []
    return getattr(schedule, "events", None) or []


def _local(dt: datetime) -> datetime:
    """Naive times are the student's local time (same rule as user_model)."""
    return dt.astimezone() if dt.tzinfo is None else dt


def parse_events(schedule: object) -> list[Event]:
    """Return the readable events in `schedule`, sorted by start time.

    Events with no "kind" are skipped rather than guessed at, so an untagged
    class or meeting never becomes a check-in point. If any event carries a
    timezone, naive times are read as the student's local time so the whole
    schedule compares consistently.
    """
    readable = []
    for raw in raw_events(schedule):
        if not isinstance(raw, dict) or not raw.get("kind"):
            continue
        start = _to_datetime(raw.get("start"))
        end = _to_datetime(raw.get("end"))
        if start is None or end is None:
            continue
        readable.append((raw, start, end))

    if any(dt.tzinfo is not None for _, start, end in readable for dt in (start, end)):
        readable = [(raw, _local(start), _local(end)) for raw, start, end in readable]

    events = [
        Event(
            start=start,
            end=end,
            kind=str(raw["kind"]).lower(),
            session_id=raw.get("session_id"),
            title=raw.get("title"),
            task_type=raw.get("task_type"),
        )
        for raw, start, end in readable
        if end > start
    ]
    events.sort(key=lambda e: e.start)
    return events


def align(now: datetime, other: datetime) -> datetime:
    """Return `now` with the same naive/aware-ness as `other`, so they compare."""
    if (now.tzinfo is None) == (other.tzinfo is None):
        return now
    if other.tzinfo is None:
        return now.astimezone().replace(tzinfo=None)
    return now.astimezone(other.tzinfo)
