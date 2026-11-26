from __future__ import annotations

import json
from datetime import UTC, datetime, time, timedelta

import pytest

from user_model import (
    EnergyReport,
    StudentProfile,
    StudentSchedule,
    apply_checkin_correction,
    estimate_baseline_energy,
)
from user_model.models import SCHEMA_VERSION
from user_model.onboarding import main, parse_sleep_hours, parse_wake_time, run_onboarding

DAY = datetime(2026, 10, 27, tzinfo=UTC)


def full_profile() -> StudentProfile:
    schedule = StudentSchedule(
        student_id="s1",
        events=[
            {"kind": "sleep", "start": DAY - timedelta(hours=8), "end": DAY, "title": "sleep"},
            {"kind": "class", "start": "2026-10-27T10:00:00", "end": "2026-10-27T11:15:00"},
            {"kind": "deadline", "start": DAY + timedelta(days=2), "title": "PS3"},
            {"kind": "study", "start": "not a time", "session_id": "x"},
        ],
    )
    p = StudentProfile(student_id="s1", sleep_hours=6.5, schedule=schedule)
    p.record_energy(apply_checkin_correction(estimate_baseline_energy(p), "pretty tired"))
    p.record_energy(EnergyReport("s1", datetime(2026, 10, 27, 9, 0), 0.4, "baseline"))
    return p


# --- serialization ---------------------------------------------------------


def test_profile_round_trips_through_json():
    p = full_profile()
    restored = StudentProfile.from_dict(json.loads(json.dumps(p.to_dict())))
    assert restored.to_dict() == p.to_dict()
    assert restored.energy_history == p.energy_history
    # Readable event times come back as datetimes (ISO strings in, datetimes out);
    # an unreadable one is kept as written.
    events = restored.schedule.events
    assert events[0] == p.schedule.events[0]
    assert events[1]["start"] == datetime(2026, 10, 27, 10, 0)
    assert events[3]["start"] == "not a time"


def test_to_dict_is_plain_json_with_a_version():
    d = full_profile().to_dict()
    assert d["schema_version"] == SCHEMA_VERSION
    json.dumps(d)  # no datetimes left anywhere
    assert d["schedule"]["events"][0]["end"] == DAY.isoformat()


def test_naive_timestamps_stay_naive():
    r = EnergyReport("s1", datetime(2026, 10, 27, 9, 0), 0.5, "baseline")
    assert EnergyReport.from_dict(r.to_dict()).timestamp.tzinfo is None


def test_round_trip_keeps_behaviour():
    p = full_profile()
    restored = StudentProfile.from_dict(p.to_dict())
    assert restored.cold_start == p.cold_start
    assert restored.schedule.last_sleep_before(DAY) == p.schedule.last_sleep_before(DAY)
    assert restored.schedule.upcoming_deadlines(DAY) == p.schedule.upcoming_deadlines(DAY)


def test_minimal_dict_gets_new_profile_defaults():
    assert StudentProfile.from_dict({"student_id": "s2"}) == StudentProfile(student_id="s2")


def test_other_schema_version_is_rejected():
    with pytest.raises(ValueError, match="schema_version"):
        StudentProfile.from_dict({"student_id": "s1", "schema_version": SCHEMA_VERSION + 1})


@pytest.mark.parametrize(
    "bad",
    [
        {"timestamp": "yesterday"},
        {"energy_level": 1.5},
        {"source": "guess"},
    ],
)
def test_invalid_stored_report_is_rejected(bad):
    good = EnergyReport("s1", DAY, 0.5, "baseline").to_dict()
    with pytest.raises(ValueError):
        EnergyReport.from_dict({**good, **bad})


# --- onboarding input parsing -------------------------------------------------


@pytest.mark.parametrize(
    ("text", "hours"), [("7", 7.0), (" 7.5 ", 7.5), ("8h", 8.0), ("6 hours", 6.0), ("0", 0.0)]
)
def test_parse_sleep_hours(text, hours):
    assert parse_sleep_hours(text) == hours


@pytest.mark.parametrize("text", ["", "seven", "-1", "17", "7.5.1"])
def test_parse_sleep_hours_rejects(text):
    with pytest.raises(ValueError):
        parse_sleep_hours(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("7", time(7, 0)),
        ("7:30", time(7, 30)),
        ("7:30am", time(7, 30)),
        ("7:30 PM", time(19, 30)),
        ("12am", time(0, 0)),
        ("12 p.m.", time(12, 0)),
        ("19:00", time(19, 0)),
        ("0:15", time(0, 15)),
    ],
)
def test_parse_wake_time(text, expected):
    assert parse_wake_time(text) == expected


@pytest.mark.parametrize("text", ["", "noon", "7m", "24:00", "7:60", "13pm", "0am", "730"])
def test_parse_wake_time_rejects(text):
    with pytest.raises(ValueError):
        parse_wake_time(text)


# --- onboarding flow ------------------------------------------------------------


def scripted(*answers):
    it = iter(answers)
    return lambda _question: next(it)


def test_onboarding_applies_answers_and_reasks_on_bad_input():
    said = []
    p = StudentProfile(student_id="s1")
    now = DAY + timedelta(hours=14)
    run_onboarding(p, ask=scripted("lots", "7.5", "9ish", "9:00am"), say=said.append, now=now)

    assert p.sleep_hours == 7.5
    sleep = p.schedule.last_sleep_before(now)
    assert sleep["end"] == DAY + timedelta(hours=9)
    assert sleep["end"] - sleep["start"] == timedelta(hours=7.5)
    assert "Please enter a number of hours, like 7 or 7.5." in said
    assert "Please enter a time like 7:30, 7:30am or 19:00." in said


def test_cli_saves_a_loadable_profile(tmp_path, monkeypatch, capsys):
    answers = iter(["8", "7:30"])
    monkeypatch.setattr("builtins.input", lambda _q: next(answers))
    out = tmp_path / "profiles" / "s9.json"

    assert main(["--student-id", "s9", "--out", str(out)]) == 0
    p = StudentProfile.from_dict(json.loads(out.read_text(encoding="utf-8")))
    assert p.student_id == "s9" and p.sleep_hours == 8 and p.cold_start
    assert "estimated energy" in capsys.readouterr().out


def test_cli_refuses_to_overwrite(tmp_path):
    out = tmp_path / "s1.json"
    out.write_text("{}", encoding="utf-8")
    assert main(["--student-id", "s1", "--out", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "{}"


def test_cli_cancel_saves_nothing(tmp_path, monkeypatch):
    def eof(_q):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    out = tmp_path / "s1.json"
    assert main(["--student-id", "s1", "--out", str(out)]) == 1
    assert not out.exists()
