"""Data model stubs for the User Model component (owner: Shivani).

These are intentionally minimal placeholders so other modules can import
and type against something stable while the real fields get fleshed out.
Replace freely -- just try to keep the public names (StudentProfile,
EnergyReport, StudentSchedule) stable so Domain Model / Negotiation don't
all need to change in lockstep.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StudentSchedule:
    """A student's known commitments. Placeholder shape."""

    student_id: str
    events: list[dict] = field(default_factory=list)  # TODO: real Event type


@dataclass
class EnergyReport:
    """A point-in-time energy estimate for a student.

    `source` distinguishes a sleep-based baseline from a check-in-corrected
    value, per the Q1 hybrid design.
    """

    student_id: str
    timestamp: datetime
    energy_level: float  # TODO: agree on scale, e.g. 0.0-1.0 or 1-5
    source: str  # "baseline" | "checkin_corrected"


@dataclass
class StudentProfile:
    """Everything the User Model tracks about one student."""

    student_id: str
    sleep_hours: float | None = None
    schedule: StudentSchedule | None = None
    cold_start: bool = True  # True until enough real sessions exist (Q2)
    energy_history: list[EnergyReport] = field(default_factory=list)
