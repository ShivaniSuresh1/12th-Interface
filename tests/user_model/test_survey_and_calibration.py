from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import pytest

from user_model import StudentProfile, StudentSchedule, apply_sleep_survey, estimate_energy_at

DAY = datetime(2026, 10, 27, tzinfo=UTC)

# domain_model's bucket cut points (mirrored, not imported: modules stay decoupled).
LOW, HIGH = 0.33, 0.66


def level(sleep_hours: float, hour: float) -> float:
    p = StudentProfile(student_id="s1", sleep_hours=sleep_hours)
    return estimate_energy_at(p, DAY + timedelta(hours=hour)).energy_level


# --- calibration against the domain_model buckets -----------------------


@pytest.mark.parametrize("hour", [8, 10, 12, 16, 18])
def test_rested_student_is_high_during_the_day(hour):
    assert level(8, hour) >= HIGH


@pytest.mark.parametrize("hour", [10, 14, 18])
def test_six_hours_sleep_is_medium(hour):
    assert LOW <= level(6, hour) < HIGH


def test_heavy_sleep_debt_reaches_low_or_near_it():
    assert level(4, 10) < 0.4
    assert level(0, 10) < level(4, 10)  # all-nighter is worse than 4h
    assert level(0, 10) < LOW


def test_late_night_is_low_even_when_rested():
    assert level(8, 0) < LOW
    assert level(8, 2) < LOW


# --- survey -------------------------------------------------------------


def test_survey_seeds_sleep_hours_and_wake_time():
    p = StudentProfile(student_id="s1")
    now = DAY + timedelta(hours=14)
    apply_sleep_survey(p, typical_sleep_hours=7, typical_wake_time=time(10, 0), now=now)

    assert p.sleep_hours == 7
    sleep = p.schedule.last_sleep_before(now)
    assert sleep["end"] == DAY + timedelta(hours=10)
    assert sleep["end"] - sleep["start"] == timedelta(hours=7)

    # A late riser has more energy at 10pm than the default 7:30 wake gives.
    default = StudentProfile(student_id="s1", sleep_hours=7)
    at_10pm = DAY + timedelta(hours=22)
    assert estimate_energy_at(p, at_10pm).energy_level > estimate_energy_at(
        default, at_10pm
    ).energy_level


def test_survey_before_wake_time_logs_previous_night():
    p = StudentProfile(student_id="s1")
    apply_sleep_survey(p, 8, time(9, 0), now=DAY + timedelta(hours=6))
    assert p.schedule.events[0]["end"] == DAY - timedelta(days=1) + timedelta(hours=9)


def test_survey_never_overrides_real_data():
    logged = {"kind": "sleep", "start": DAY + timedelta(hours=1), "end": DAY + timedelta(hours=6)}
    p = StudentProfile(
        student_id="s1",
        sleep_hours=5,
        schedule=StudentSchedule(student_id="s1", events=[logged]),
    )
    apply_sleep_survey(p, 9, time(8, 0), now=DAY + timedelta(hours=12))
    assert p.sleep_hours == 5
    assert p.schedule.events == [logged]


@pytest.mark.parametrize("hours", [-1, 17])
def test_survey_rejects_impossible_sleep_hours(hours):
    with pytest.raises(ValueError):
        apply_sleep_survey(StudentProfile(student_id="s1"), hours, time(8, 0), now=DAY)
