"""Onboarding survey, User Model half (Q2 cold start).

Split agreed with Domain Model: sleep/schedule questions live here; the
"what do you prefer when tired / moderate / energized?" answers go to
`domain_model.StudentTaskMapping.from_survey(...)`.

The answers are written into existing contract fields (`sleep_hours` and a
"sleep" schedule event) so the frozen StudentProfile shape doesn't change.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from .models import StudentProfile, StudentSchedule, as_aware

MAX_SURVEY_SLEEP_HOURS = 16.0


def apply_sleep_survey(
    profile: StudentProfile,
    typical_sleep_hours: float,
    typical_wake_time: time,
    now: datetime | None = None,
) -> None:
    """Seed a new student's profile from their survey answers.

    Sets `sleep_hours` (unless already known) and logs last night as a
    "sleep" event ending at the typical wake time, unless a sleep event
    ending today is already logged. Real logged sleep always wins.
    """
    if not 0.0 <= typical_sleep_hours <= MAX_SURVEY_SLEEP_HOURS:
        raise ValueError(
            f"typical_sleep_hours must be in [0, {MAX_SURVEY_SLEEP_HOURS}], "
            f"got {typical_sleep_hours}"
        )
    now = as_aware(now or datetime.now())

    if profile.sleep_hours is None:
        profile.sleep_hours = typical_sleep_hours
    if profile.schedule is None:
        profile.schedule = StudentSchedule(student_id=profile.student_id)

    wake = datetime.combine(now.date(), typical_wake_time, tzinfo=now.tzinfo)
    if wake > now:  # survey taken before the usual wake time: last night ended yesterday
        wake -= timedelta(days=1)

    last = profile.schedule.last_sleep_before(now)
    if last is not None and last["end"].date() == wake.date():
        return
    profile.schedule.events.append(
        {
            "kind": "sleep",
            "start": wake - timedelta(hours=typical_sleep_hours),
            "end": wake,
            "title": "typical sleep (from survey)",
        }
    )
