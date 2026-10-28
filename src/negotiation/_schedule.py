"""Lenient reader for schedule events. Internal to negotiation.

`user_model.StudentSchedule.events` is still `list[dict]` with no agreed
shape, so this accepts what's most likely and skips anything it can't read
instead of crashing. Recognized event keys:

    {
        "start": datetime | ISO-8601 str,   # required
        "end": datetime | ISO-8601 str,     # required, after start
        "kind": "study" | "break" | <anything else, e.g. "class", "meeting">,
        "session_id": str,                  # optional
        "title": str,                       # optional, used in narration
        "task_type": str,                   # optional, a domain_model TaskType value
    }

An event with no "kind" is treated as a study session.
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


def parse_events(schedule: object) -> list[Event]:
    """Return the readable events in `schedule`, sorted by start time."""
    events = []
    for raw in raw_events(schedule):
        if not isinstance(raw, dict):
            continue
        start = _to_datetime(raw.get("start"))
        end = _to_datetime(raw.get("end"))
        if start is None or end is None or end <= start:
            continue
        if (start.tzinfo is None) != (end.tzinfo is None):
            continue
        events.append(
            Event(
                start=start,
                end=end,
                kind=str(raw.get("kind") or "study").lower(),
                session_id=raw.get("session_id"),
                title=raw.get("title"),
                task_type=raw.get("task_type"),
            )
        )
    try:
        events.sort(key=lambda e: e.start)
    except TypeError:
        # Mix of naive and aware events -- can't order them reliably.
        return []
    return events


def align(now: datetime, other: datetime) -> datetime:
    """Return `now` with the same naive/aware-ness as `other`, so they compare."""
    if (now.tzinfo is None) == (other.tzinfo is None):
        return now
    if other.tzinfo is None:
        return now.astimezone().replace(tzinfo=None)
    return now.astimezone(other.tzinfo)
