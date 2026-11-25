"""Evaluation scenarios (owner: Harshini).

A scenario is one moment in a student's day: how they slept, what's on
their schedule, an optional check-in answer, and an optional disruption.
The harness runs it through StudySessionPlanner and shows the participant
the result.

PILOT_SCENARIOS are the six scenarios for the pilot. Each is built on one
of Shivani's six energy scenarios (same time, sleep and check-in, so the
same energy), with a schedule, a student and a disruption added by the
harness. Together they cover:
rested / short night / evening energy, a check-in that disagrees with the
sleep estimate, all four task types, every explanation source (default
rule, survey answer, learned choices), and every replan path (move,
shorten or defer, ask).

In every scenario that proposes a concrete change (move, shorten, defer),
the recommended task type matches the session being changed, so
participants never see the planner suggest one kind of task while
rescheduling a different one. (s4's "ask" proposes no change, so it is
exempt.) To change one, edit it here and run
`python -m integration.evaluation preview` to check both conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

# All placeholder scenarios happen on the same (arbitrary) Monday.
DAY = datetime.combine(date(2026, 11, 23), time())


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
    # Past accept/edit choices replayed into the task mapping: (energy, TaskType value).
    history: list[tuple[float, str]] | None = None
    # Which of Shivani's energy scenarios (tests/user_model/scenarios.py) this
    # scenario's time, sleep and check-in come from.
    user_model_scenario: int | None = None

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


# A student a couple of weeks in: 12 recorded choices. Same history as the
# "learned" student in tests/domain_model/pilot_recommendations.py (a test
# keeps the two in sync), so the harness shows the explanation Vyshnavi checked.
LEARNED_HISTORY: list[tuple[float, str]] = (
    [(0.2, "memorization")] * 4  # flashcards when tired
    + [(0.5, "reading")] * 4
    + [(0.5, "review")]
    + [(0.8, "problem_set")] * 3  # agrees with the default
)

LEARNED_STORY = (
    "You've used the app for about two weeks. On tired days you've usually switched "
    "to flashcards, and at medium energy you've mostly picked reading."
)


PILOT_SCENARIOS: list[Scenario] = [
    # Each scenario uses the energy inputs (time, sleep, check-in) of one of
    # Shivani's six energy scenarios (tests/user_model/scenarios.py), so the
    # energy participants see is exactly hers; a test checks this. The harness
    # adds the schedule, the student and the disruption on top.
    #
    # Order matters: assign() splits alternating items into two sets, so each set
    # gets 1 recommendation-only scenario + 2 replan proposals.
    Scenario(
        scenario_id="s1_rested_morning",
        user_model_scenario=1,  # well rested, morning
        story=(
            "It's 9:30 AM on a weekday. You slept about 8 hours (11:30 PM to 7:30 AM) and "
            "have a physics problem set planned for 9:30-11:00. You check in as "
            '"focused".'
        ),
        now=at(9, 30),
        sleep_start=at(23, 30, day_offset=-1),
        wake=at(7, 30),
        checkin="focused",
        events=[_study("s1", "Physics problem set", "problem_set", at(9, 30), at(11))],
    ),
    Scenario(
        scenario_id="s2_survey_preference",
        user_model_scenario=3,  # slept fine but says tired
        story=(
            "It's 10:30 AM. You slept about 7 hours (12:30 AM to 7:30 AM). When you set up "
            "the app, you said that on so-so days you'd rather drill flashcards than start "
            'something new. You check in as "tired". Up next: anatomy flashcards, '
            "10:30-11:30 AM."
        ),
        now=at(10, 30),
        sleep_start=at(0, 30),
        wake=at(7, 30),
        checkin="tired",
        survey={"medium": "memorization"},
        events=[_study("s1", "Anatomy flashcards", "memorization", at(10, 30), at(11, 30))],
    ),
    Scenario(
        scenario_id="s3_short_night_fatigue",
        user_model_scenario=2,  # short night, post-lunch
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
        user_model_scenario=4,  # evening, rested
        story=(
            "It's 8:00 PM. You slept about 8 hours (11:30 PM to 7:30 AM). At the start of "
            'your exam review session you told the app you feel "good", but a few minutes '
            'in you tap "I\'m tired".'
        ),
        now=at(20),
        sleep_start=at(23, 30, day_offset=-1),
        wake=at(7, 30),
        checkin="good",
        disruption="fatigue",
        events=[_study("s1", "Exam review", "review", at(20), at(21))],
    ),
    Scenario(
        scenario_id="s5_meeting_ran_late",
        user_model_scenario=5,  # no check-in, short night, afternoon
        story=(
            f"{LEARNED_STORY} It's 4:00 PM. You slept about 5 hours (2:30 AM to 7:30 AM) "
            "and haven't checked in today. Your group project meeting was supposed to end "
            "at 3:40 but ran 20 minutes late. You had a history reading session planned "
            "for 3:40-4:40, and an evening lecture at 6:00."
        ),
        now=at(16),
        sleep_start=at(2, 30),
        wake=at(7, 30),
        disruption="meeting_ran_late:20",
        history=LEARNED_HISTORY,
        events=[
            {
                "kind": "meeting",
                "title": "Group project meeting",
                "start": at(14, 40),
                "end": at(15, 40),
            },
            _study("s1", "History reading", "reading", at(15, 40), at(16, 40)),
            {"kind": "class", "title": "Evening lecture", "start": at(18), "end": at(19, 30)},
        ],
    ),
    Scenario(
        scenario_id="s6_missed_session",
        user_model_scenario=6,  # very short night, late morning
        story=(
            f"{LEARNED_STORY} It's 11:00 AM. You only slept about 4 hours (3:30 AM to "
            "7:30 AM). You missed this morning's 9:00-10:00 Spanish vocab flashcards "
            "session because an errand took longer than expected, and you have a lecture "
            'from 12:00-1:30. You check in as "exhausted".'
        ),
        now=at(11),
        sleep_start=at(3, 30),
        wake=at(7, 30),
        checkin="exhausted",
        disruption="missed_session",
        history=LEARNED_HISTORY,
        events=[
            _study("s1", "Spanish vocab flashcards", "memorization", at(9), at(10)),
            {"kind": "class", "title": "Lecture", "start": at(12), "end": at(13, 30)},
        ],
    ),
]
