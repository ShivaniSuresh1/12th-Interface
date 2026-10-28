from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from user_model import (
    COLD_START_MIN_CHECKINS,
    EnergyReport,
    StudentProfile,
    StudentSchedule,
    apply_checkin_correction,
    estimate_baseline_energy,
    estimate_energy_at,
    parse_checkin_response,
)

DAY = datetime(2026, 10, 27, tzinfo=UTC)


def at(hour: float, day: datetime = DAY) -> datetime:
    return day + timedelta(hours=hour)


def level(profile: StudentProfile, hour: float) -> float:
    return estimate_energy_at(profile, at(hour)).energy_level


# --- baseline -----------------------------------------------------------


def test_baseline_is_in_range_and_marked_baseline():
    report = estimate_baseline_energy(StudentProfile(student_id="s1"))
    assert 0.0 <= report.energy_level <= 1.0
    assert report.source == "baseline"
    assert report.timestamp.tzinfo is not None


def test_sleep_debt_lowers_energy():
    rested = StudentProfile(student_id="s1", sleep_hours=8)
    short = StudentProfile(student_id="s1", sleep_hours=4)
    assert level(short, 10) < level(rested, 10)


def test_energy_falls_late_at_night():
    p = StudentProfile(student_id="s1", sleep_hours=8)
    assert level(p, 23) < level(p, 10)
    assert level(p, 3) < level(p, 23)  # still up at 3am


def test_post_lunch_dip():
    p = StudentProfile(student_id="s1", sleep_hours=8)
    assert level(p, 14) < level(p, 11)
    assert level(p, 14) < level(p, 17)


def test_sleep_event_sets_wake_time_and_sleep_hours():
    late_riser = StudentProfile(
        student_id="s1",
        schedule=StudentSchedule(
            student_id="s1",
            events=[{"kind": "sleep", "start": at(3), "end": at(11)}],
        ),
    )
    early_riser = StudentProfile(student_id="s1", sleep_hours=8)  # default 7:30 wake
    # At 10pm the late riser has been awake 3.5h less.
    assert level(late_riser, 22) > level(early_riser, 22)


def test_learned_history_pulls_baseline_toward_reports():
    p = StudentProfile(student_id="s1", sleep_hours=8)
    generic = level(p, 10)
    for d in range(10):
        p.record_energy(EnergyReport("s1", at(10, DAY - timedelta(days=d + 1)), 0.1, "checkin_corrected"))
    personalized = level(p, 10)
    assert personalized < generic
    # Today's sleep still counts for at least half.
    assert personalized >= 0.5 * generic


def test_learning_is_per_time_of_day():
    p = StudentProfile(student_id="s1", sleep_hours=8)
    generic_evening = level(p, 20)
    for d in range(10):
        p.record_energy(EnergyReport("s1", at(10, DAY - timedelta(days=d + 1)), 0.1, "checkin_corrected"))
    assert level(p, 20) == pytest.approx(generic_evening)


# --- check-in correction ------------------------------------------------


def test_tired_checkin_lowers_energy():
    baseline = EnergyReport("s1", at(10), 0.7, "baseline")
    corrected = apply_checkin_correction(baseline, "pretty tired tbh")
    assert corrected.source == "checkin_corrected"
    assert corrected.energy_level < baseline.energy_level


def test_checkin_outweighs_but_does_not_replace_baseline():
    baseline = EnergyReport("s1", at(10), 0.2, "baseline")
    corrected = apply_checkin_correction(baseline, "energized")
    assert 0.2 < corrected.energy_level < 0.9
    assert corrected.energy_level > 0.55  # closer to the self-report


def test_unparseable_checkin_returns_baseline_unchanged():
    baseline = EnergyReport("s1", at(10), 0.6, "baseline")
    assert apply_checkin_correction(baseline, "asdf") is baseline


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1", 0.0),
        ("5", 1.0),
        ("3/5", 0.5),
        ("0.4", 0.4),
        ("Tired", 0.3),
        ("not tired", 0.7),
        ("I'm feeling great!", 0.85),
        ("", None),
        ("whatever", None),
    ],
)
def test_parse_checkin_response(text, expected):
    assert parse_checkin_response(text) == (None if expected is None else pytest.approx(expected))


# --- cold start / model validation --------------------------------------


def test_cold_start_clears_after_enough_checkins():
    p = StudentProfile(student_id="s1")
    for i in range(COLD_START_MIN_CHECKINS):
        assert p.cold_start
        p.record_energy(EnergyReport("s1", at(i), 0.5, "baseline"))  # baselines don't count
        p.record_energy(EnergyReport("s1", at(i), 0.5, "checkin_corrected"))
    assert not p.cold_start


@pytest.mark.parametrize(("lvl", "src"), [(1.5, "baseline"), (-0.1, "baseline"), (0.5, "guess")])
def test_energy_report_rejects_invalid_values(lvl, src):
    with pytest.raises(ValueError):
        EnergyReport("s1", at(0), lvl, src)


def test_iso_string_times_are_accepted():
    as_str = StudentProfile(
        student_id="s1",
        schedule=StudentSchedule(
            student_id="s1",
            events=[{"kind": "sleep", "start": at(3).isoformat(), "end": at(11).isoformat()}],
        ),
    )
    as_dt = StudentProfile(
        student_id="s1",
        schedule=StudentSchedule(
            student_id="s1", events=[{"kind": "sleep", "start": at(3), "end": at(11)}]
        ),
    )
    assert level(as_str, 22) == pytest.approx(level(as_dt, 22))


def test_unreadable_or_foreign_events_are_skipped_not_crashed_on():
    sched = StudentSchedule(
        student_id="s1",
        events=[
            {"kind": "sleep", "start": "last night", "end": "this morning"},
            {"kind": "sleep", "end": at(9)},  # no start: wake time only
            {"kind": "study", "start": at(10), "end": at(11), "session_id": "a", "task_type": "reading"},
            {"kind": "deadline", "start": "2026-10-29T23:59"},
            {"start": at(12), "end": at(13)},  # no kind
            "not an event",
        ],
    )
    p = StudentProfile(student_id="s1", schedule=sched)
    assert sched.last_sleep_before(at(20))["end"] == at(9)
    assert 0.0 <= level(p, 20) <= 1.0
    assert len(sched.upcoming_deadlines(at(0))) == 1


def test_upcoming_deadlines_sorted_and_filtered():
    sched = StudentSchedule(
        student_id="s1",
        events=[
            {"kind": "deadline", "start": at(48), "title": "HW2"},
            {"kind": "deadline", "start": at(-5), "title": "HW0"},
            {"kind": "class", "start": at(9), "end": at(10)},
            {"kind": "deadline", "start": at(20), "title": "HW1"},
        ],
    )
    assert [e["title"] for e in sched.upcoming_deadlines(at(0))] == ["HW1", "HW2"]
