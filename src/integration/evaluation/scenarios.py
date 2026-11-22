"""Evaluation scenarios (owner: Harshini).

A scenario is one moment in a student's day: how they slept, what's on
their schedule, an optional check-in answer, and an optional disruption.
The harness runs it through StudySessionPlanner and shows the participant
the result.

PLACEHOLDER_SCENARIOS below are stand-ins so the harness can be built and
tested now. Replace them with the team's real scenarios in Phase 2:

- Shivani:   sleep (sleep_start / wake) and check-in answer
- Vyshnavi:  the study sessions' tasks (title + task_type) and any survey answers
- Soumyadip: the disruption trigger, e.g. "fatigue", "meeting_ran_late:20", "missed_session"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

# All placeholder scenarios happen on the same (arbitrary) Monday.
DAY = datetime(2026, 11, 23)  # noqa: DTZ001 -- naive = student local time, as in user_model


def at(hour: int, minute: int = 0, day_offset: int = 0) -> datetime:
    """A naive local time on DAY (or a day before/after it)."""
    return (DAY + timedelta(days=day_offset)).replace(hour=hour, minute=minute)


@dataclass
class Scenario:
    scenario_id: str
    story: str  # what the participant reads, in second person
    now: datetime  # the planner's clock is frozen here
    sleep_start: datetime
    wake: datetime
    events: list[dict] = field(default_factory=list)  # user_model `Event` dicts, minus sleep
    checkin: str | None = None  # passed to handle_checkin(), e.g. "pretty tired"
    disruption: str | None = None  # passed to handle_disruption(), e.g. "fatigue"
    survey: dict[str, str] | None = None  # energy bucket -> TaskType value

    @property
    def sleep_hours(self) -> float:
        return (self.wake - self.sleep_start).total_seconds() / 3600

    def schedule_events(self) -> list[dict]:
        """Events plus last night's sleep, in the shape user_model expects."""
        sleep = {"kind": "sleep", "start": self.sleep_start, "end": self.wake}
        return [sleep, *self.events]


def _study(session_id: str, title: str, task_type: str, start: datetime, end: datetime) -> dict:
    return {
        "kind": "study",
        "session_id": session_id,
        "title": title,
        "task_type": task_type,
        "start": start,
        "end": end,
    }


PLACEHOLDER_SCENARIOS: list[Scenario] = [
    Scenario(
        scenario_id="p1_rested_morning",
        story=(
            "It's 10:00 AM. You slept about 8 hours last night and have a free "
            "morning before a problem set session."
        ),
        now=at(10),
        sleep_start=at(23, 30, day_offset=-1),
        wake=at(7, 30),
        events=[_study("s1", "Algorithms problem set", "problem_set", at(10), at(11, 30))],
    ),
    Scenario(
        scenario_id="p2_short_sleep_tired",
        story=(
            "It's 2:00 PM. You only slept about 5 hours. When the app asked how you "
            'feel, you answered "pretty tired".'
        ),
        now=at(14),
        sleep_start=at(2, 30),
        wake=at(7, 30),
        checkin="pretty tired",
        events=[_study("s1", "Biology reading", "reading", at(14), at(15))],
    ),
    Scenario(
        scenario_id="p3_fatigue_midsession",
        story=(
            "It's 3:00 PM, partway through a long problem set session. You slept about "
            '6 hours. You tell the app "I\'m tired".'
        ),
        now=at(15),
        sleep_start=at(1, 30),
        wake=at(7, 30),
        checkin="tired",
        disruption="fatigue",
        events=[_study("s1", "Linear algebra problem set", "problem_set", at(14, 30), at(16))],
    ),
    Scenario(
        scenario_id="p4_meeting_ran_late",
        story=(
            "It's 4:20 PM. Your group meeting was supposed to end at 4:00 but ran 20 "
            "minutes late, and a review session was planned for 4:00-5:00."
        ),
        now=at(16, 20),
        sleep_start=at(23, 30, day_offset=-1),
        wake=at(7),
        checkin="fine",
        disruption="meeting_ran_late:20",
        events=[
            {"kind": "meeting", "title": "Group meeting", "start": at(15), "end": at(16)},
            _study("s1", "Exam review", "review", at(16), at(17)),
            {"kind": "class", "title": "Evening lab", "start": at(18), "end": at(20)},
        ],
    ),
    Scenario(
        scenario_id="p5_missed_session",
        story=(
            "It's 1:00 PM. You missed this morning's 10-11 AM flashcard session because "
            "an errand took longer than expected."
        ),
        now=at(13),
        sleep_start=at(0),
        wake=at(8),
        disruption="missed_session",
        events=[
            _study("s1", "Spanish vocab flashcards", "memorization", at(10), at(11)),
            {"kind": "class", "title": "Lecture", "start": at(14), "end": at(15, 30)},
        ],
    ),
    Scenario(
        scenario_id="p6_evening_survey_pref",
        story=(
            "It's 8:00 PM. You slept about 7 hours. During onboarding you said that "
            "when you're tired you'd rather do problem sets than reading. You answer "
            'the check-in with "exhausted".'
        ),
        now=at(20),
        sleep_start=at(0, 30),
        wake=at(7, 30),
        checkin="exhausted",
        survey={"low": "problem_set"},
        events=[_study("s1", "Statistics homework", "problem_set", at(20), at(21))],
    ),
]
