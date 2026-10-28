"""Check-in cadence (Q6). Owner: Soumyadip.

Check-ins happen at session boundaries only, capped per day -- not
proactive pushes throughout the day, and not only-when-the-app-is-opened.

A "session boundary" is the start or end of a study session or a break,
give or take BOUNDARY_TOLERANCE. Starts/ends of other events (classes,
meetings) are not boundaries -- the student isn't in planner time then.
Disruptions that happen mid-session wait for `next_boundary(...)`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from ._schedule import align, parse_events
from .replanning import ReplanProposal

MAX_CHECKINS_PER_DAY = 6
BOUNDARY_TOLERANCE = timedelta(minutes=5)

# Answer words match what user_model.apply_checkin_correction understands.
ENERGY_QUESTION = "How's your energy right now -- tired, fine, or energized?"


@dataclass
class CheckinWindow:
    """A session-boundary event the student is at."""

    student_id: str
    boundary_type: str  # "start" | "end" | "break"
    timestamp: datetime


def _boundaries(schedule: object) -> list[tuple[datetime, str]]:
    """Every (time, boundary_type) in the schedule, in time order."""
    points = []
    for event in parse_events(schedule):
        if event.is_study:
            points.append((event.start, "start"))
            points.append((event.end, "end"))
        elif event.is_break:
            # Both edges of a break are break boundaries: the student is
            # stepping away (start) or about to resume (end).
            points.append((event.start, "break"))
            points.append((event.end, "break"))
    points.sort(key=lambda p: p[0])
    return points


def find_boundary(
    now: datetime, schedule: object, student_id: str | None = None
) -> CheckinWindow | None:
    """Return the boundary `now` falls on (within tolerance), or None.

    When two boundaries are within tolerance (a session ending right as a
    break starts), the closest one wins.
    """
    if student_id is None:
        student_id = getattr(schedule, "student_id", None) or "unknown"

    best: tuple[timedelta, datetime, str] | None = None
    for when, boundary_type in _boundaries(schedule):
        distance = abs(align(now, when) - when)
        if distance <= BOUNDARY_TOLERANCE and (best is None or distance < best[0]):
            best = (distance, when, boundary_type)

    if best is None:
        return None
    return CheckinWindow(student_id=student_id, boundary_type=best[2], timestamp=best[1])


def is_session_boundary(now: datetime, schedule: object) -> bool:
    """Return True if `now` lines up with a session start/end/break.

    `schedule` can be a user_model.StudentSchedule, a dict with "events",
    or a bare list of event dicts (see _schedule.py for the event shape).
    Anything unreadable counts as "no boundary" rather than raising.
    """
    return find_boundary(now, schedule) is not None


def next_boundary(now: datetime, schedule: object) -> datetime | None:
    """The next boundary strictly after `now` -- when a mid-session
    disruption should be raised with the student. None if there isn't one."""
    for when, _ in _boundaries(schedule):
        if when > align(now, when):
            return when
    return None


@dataclass
class CheckinLog:
    """Tracks check-ins already made so the daily cap is enforced.

    Integration should keep one of these per running planner.
    """

    max_per_day: int = MAX_CHECKINS_PER_DAY
    _by_day: dict[tuple[str, date], list[CheckinWindow]] = field(
        default_factory=lambda: defaultdict(list), init=False, repr=False
    )

    def count_on(self, student_id: str, day: date) -> int:
        return len(self._by_day[(student_id, day)])

    def remaining_today(self, student_id: str, now: datetime) -> int:
        return max(0, self.max_per_day - self.count_on(student_id, now.date()))

    def already_checked_in(self, window: CheckinWindow) -> bool:
        """True if we've checked in at this same boundary already."""
        same_day = self._by_day[(window.student_id, window.timestamp.date())]
        return any(
            abs(align(window.timestamp, prev.timestamp) - prev.timestamp) <= BOUNDARY_TOLERANCE
            for prev in same_day
        )

    def can_check_in(self, window: CheckinWindow) -> bool:
        return self.remaining_today(
            window.student_id, window.timestamp
        ) > 0 and not self.already_checked_in(window)

    def record(self, window: CheckinWindow) -> None:
        self._by_day[(window.student_id, window.timestamp.date())].append(window)


def should_check_in(
    now: datetime, schedule: object, log: CheckinLog, student_id: str | None = None
) -> CheckinWindow | None:
    """Return the window to check in at right now, or None.

    None when `now` isn't a boundary, the daily cap is used up, or this
    boundary already had its check-in. Records the check-in in `log` when it
    returns a window, so calling twice at the same boundary only fires once.
    """
    window = find_boundary(now, schedule, student_id)
    if window is None or not log.can_check_in(window):
        return None
    log.record(window)
    return window


def compose_checkin_message(window: CheckinWindow, proposal: ReplanProposal | None = None) -> str:
    """One batched message for a boundary: the energy check-in plus any
    pending replan, so the student is interrupted once, not twice (Q5 x Q6)."""
    opener = {
        "start": "Before you start:",
        "end": "Nice work wrapping that session.",
        "break": "Break time.",
    }.get(window.boundary_type, "Quick check-in.")
    if proposal is None:
        return f"{opener} {ENERGY_QUESTION}"
    return f"{opener} {ENERGY_QUESTION} Also: {proposal.message}"
