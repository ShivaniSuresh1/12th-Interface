"""Check-in cadence (Q6). Owner: Soumyadip.

Check-ins happen at session boundaries only, capped per day -- not
proactive pushes throughout the day, and not only-when-the-app-is-opened.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MAX_CHECKINS_PER_DAY = 6  # TODO: tune / make configurable per student


@dataclass
class CheckinWindow:
    """Placeholder for a session-boundary event the student is at."""

    student_id: str
    boundary_type: str  # "start" | "end" | "break"
    timestamp: datetime


def is_session_boundary(now: datetime, schedule: object) -> bool:
    """Return True if `now` lines up with a session start/end/break.

    TODO: implement real logic against the student's schedule (from
    user_model.StudentSchedule). Placeholder always returns False so this
    is safe to import before the real schedule shape is finalized.
    """
    return False
