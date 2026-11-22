"""Evaluation scenarios (owner: Harshini).

A scenario is one moment in a student's day: how they slept, what's on
their schedule, an optional check-in answer, and an optional disruption.
The harness runs it through StudySessionPlanner and shows the participant
the result.

PILOT_SCENARIOS are the six scenarios for the pilot. Together they cover:
rested / short night / evening energy, a check-in that disagrees with the
sleep estimate, all four task types, a survey preference, and every replan
path (move, shorten or defer, ask). To change one, edit it here and run
`python -m integration.evaluation preview` to check both conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

# All placeholder scenarios happen on the same (arbitrary) Monday.
DAY = datetime(2026, 11, 23)


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


PILOT_SCENARIOS: list[Scenario] = [
    # Order matters: assign() splits alternating items into two sets, so each set
    # gets 1 recommendation-only scenario + 2 replan proposals.
    Scenario(
        scenario_id="s1_rested_morning",
        story=(
            "It's 9:30 AM on a weekday. You slept about 8 hours (11:30 PM to 7:30 AM) and "
            "have a physics problem set planned for 9:30-11:00. You haven't checked in yet."
        ),
        now=at(9, 30),
        sleep_start=at(23, 30, day_offset=-1),
        wake=at(7, 30),
        events=[_study("s1", "Physics problem set", "problem_set", at(9, 30), at(11))],
    ),
    Scenario(
        scenario_id="s2_evening_survey_preference",
        story=(
            "It's 8:00 PM. You slept about 7 hours. When you set up the app, you said that "
            "when you're tired you'd rather grind through problem sets than read. You answer "
            'the check-in with "exhausted". Up next: statistics homework, 8:00-9:00 PM.'
        ),
        now=at(20),
        sleep_start=at(0, 30),
        wake=at(7, 30),
        checkin="exhausted",
        survey={"low": "problem_set"},
        events=[_study("s1", "Statistics homework", "problem_set", at(20), at(21))],
    ),
    Scenario(
        scenario_id="s3_short_night_fatigue",
        story=(
            "It's 2:00 PM. You only slept about 5 hours (2:30 AM to 7:30 AM). You're about "
            'to start a 2:00-3:00 PM biology reading session and tell the app "I\'m '
            'exhausted, I can\'t focus".'
        ),
        now=at(14),
        sleep_start=at(2, 30),
        wake=at(7, 30),
        checkin="exhausted",
        disruption="fatigue",
        events=[
            _study("s1", "Biology reading", "reading", at(14), at(15)),
            {"kind": "class", "title": "Chemistry lab", "start": at(16), "end": at(18)},
        ],
    ),
    Scenario(
        scenario_id="s4_signals_disagree_ask",
        story=(
            "It's 4:00 PM. You slept about 8.5 hours. At the start of your exam review "
            'session you told the app you feel "good", but 10 minutes in you tap '
            '"I\'m tired".'
        ),
        now=at(16, 10),
        sleep_start=at(23, 0, day_offset=-1),
        wake=at(7, 30),
        checkin="good",
        disruption="fatigue",
        events=[_study("s1", "Exam review", "review", at(16), at(17))],
    ),
    Scenario(
        scenario_id="s5_meeting_ran_late",
        story=(
            "It's 4:20 PM. Your group project meeting was supposed to end at 4:00 but ran "
            "20 minutes late. You had a data structures problem set planned for 4:00-5:00, "
            'and an evening lecture at 6:00. You check in as "fine".'
        ),
        now=at(16, 20),
        sleep_start=at(23, 30, day_offset=-1),
        wake=at(7),
        checkin="fine",
        disruption="meeting_ran_late:20",
        events=[
            {"kind": "meeting", "title": "Group project meeting", "start": at(15), "end": at(16)},
            _study("s1", "Data structures problem set", "problem_set", at(16), at(17)),
            {"kind": "class", "title": "Evening lecture", "start": at(18), "end": at(19, 30)},
        ],
    ),
    Scenario(
        scenario_id="s6_missed_session",
        story=(
            "It's 1:00 PM. You slept about 8 hours. You missed this morning's 10:00-11:00 "
            "Spanish vocab flashcards session because an errand took longer than expected, "
            "and you have a lecture from 2:00-3:30."
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
]
