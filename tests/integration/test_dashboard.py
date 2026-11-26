"""Dashboard API (Phase 3, step 8): UI words -> planner calls, schedule kept in sync."""

from datetime import datetime, time, timedelta, timezone

import pytest

from domain_model import TaskType
from integration.dashboard import DISRUPTIONS, FEELINGS, DashboardSession, energy_label
from integration.evaluation.simulate import frozen_clock
from integration.storage import ProfileStore, student_id_for

CST = timezone(timedelta(hours=-6))
NOW = datetime(2026, 11, 25, 14, 0, tzinfo=CST)  # a Wednesday afternoon


@pytest.fixture
def session():
    with frozen_clock(NOW):
        yield DashboardSession(student_id="t", sleep_hours=7.5, clock=lambda: NOW)


def test_plan_comes_from_the_real_modules(session):
    plan = session.plan()
    assert 0 <= plan["energy_pct"] <= 100
    assert plan["energy_label"] == energy_label(plan["energy_level"])
    assert plan["task_label"] == TaskType(plan["task_type"]).label
    assert plan["why"].startswith("because")
    assert "sleep" in plan["energy_source"]


def test_less_sleep_means_less_energy(session):
    rested = session.plan()["energy_level"]
    session.set_sleep(4)
    assert session.plan()["energy_level"] < rested
    assert sum(e["kind"] == "sleep" for e in session.events) == 1


@pytest.mark.parametrize("feeling", list(FEELINGS))
def test_checkin_corrects_energy(session, feeling):
    session.checkin(feeling)
    plan = session.plan()
    assert "check-in" in plan["energy_source"]
    assert session.last_feeling == feeling
    assert len(session.checkin_history()) == 1


def test_tired_checkin_lowers_energy(session):
    before = session.plan()["energy_level"]
    session.checkin("Tired")
    assert session.plan()["energy_level"] < before


def test_demo_schedule_has_past_current_and_upcoming_sessions(session):
    statuses = {item["status"] for item in session.schedule_items()}
    assert {"Missed", "Upcoming"} <= statuses
    assert all(item["duration"].endswith(" min") for item in session.schedule_items())


def test_add_and_complete_a_session(session):
    sid = session.add_session("Database assignment", NOW + timedelta(hours=5), 30, TaskType.PROBLEM_SET)
    session.mark_completed(sid)
    item = next(i for i in session.schedule_items() if i["session_id"] == sid)
    assert item["status"] == "Completed"
    assert item["task_type"] == TaskType.PROBLEM_SET.label


def test_starting_a_task_is_learned(session):
    level = session.plan()["energy_level"]
    for _ in range(6):
        session.start_task(TaskType.MEMORIZATION.value)
    task, why = session.plan()["task_type"], session.plan()["why"]
    assert task == TaskType.MEMORIZATION.value, (level, why)
    assert session.active_task == TaskType.MEMORIZATION.value


def test_accepting_a_replan_updates_the_schedule(session):
    proposal = session.disrupt("Meeting ran late")
    change = proposal.proposed_change
    assert change["action"] in {"move", "shorten", "defer"}

    def slot(sid):
        item = next(i for i in session.schedule_items() if i["session_id"] == sid)
        return item["time"], item["duration"]

    before = slot(change["session_id"])
    message = session.respond(proposal, "accept")
    assert "updated" in message
    assert slot(change["session_id"]) != before


def test_rejecting_keeps_the_schedule(session):
    proposal = session.disrupt("I am feeling tired")
    before = session.schedule_items()
    assert "original plan" in session.respond(proposal, "reject")
    assert session.schedule_items() == before


def test_something_else_gets_the_interactive_ask_flow(session):
    proposal = session.disrupt("Something else came up")
    assert session.is_ask(proposal)
    nxt = session._next_open_session()
    message = session.answer_ask(proposal, "honestly I'm wiped, 20 minutes max")
    assert "20 minutes" in message
    assert nxt["end"] - nxt["start"] == timedelta(minutes=20)


def test_never_mind_changes_nothing(session):
    proposal = session.disrupt("Something else came up")
    before = session.schedule_items()
    session.answer_ask(proposal, "never mind")
    assert session.schedule_items() == before


def test_every_ui_disruption_gets_a_proposal(session):
    for choice in DISRUPTIONS:
        proposal = session.disrupt(choice)
        assert proposal.message
        assert proposal.proposed_change["action"] in {"move", "shorten", "defer", "ask"}


def test_energy_curve_covers_the_day(session):
    curve = session.energy_curve()
    assert len(curve) == 15
    assert all(0 <= pct <= 100 for _t, pct in curve)


# -- onboarding + saving (Phase 3, step 9) ----------------------------------------

def _new_student(**prefs):
    with frozen_clock(NOW):
        return DashboardSession.onboard(
            student_id="priya",
            name="Priya",
            typical_sleep_hours=6.0,
            typical_wake_time=time(8, 0),
            task_preferences={"low": None, "medium": None, "high": None, **prefs},
            clock=lambda: NOW,
        )


def test_onboarding_uses_both_surveys():
    s = _new_student(low=TaskType.MEMORIZATION)
    assert s.name == "Priya"
    assert s.planner.profile.sleep_hours == 6.0
    sleep = [e for e in s.events if e["kind"] == "sleep"]
    assert len(sleep) == 1 and sleep[0]["end"].hour == 8
    lines = s.starting_suggestions()
    assert len(lines) == 3
    assert "memorization" in lines[0] and "you said" in lines[0]
    assert s.schedule_items()  # gets a sample day to try things on


def test_no_preference_keeps_the_default_rule():
    lines = _new_student().starting_suggestions()
    assert all("default" in line for line in lines)


def test_save_and_load_round_trip(tmp_path):
    s = _new_student(high=TaskType.READING)
    with frozen_clock(NOW):
        s.checkin("Tired")
        s.start_task(TaskType.REVIEW.value)
        first = s.schedule_items()[0]["session_id"]
        s.mark_completed(first)
        before = s.plan()

        store = ProfileStore(tmp_path)
        store.save(s)
        assert store.students() == [("priya", "Priya")]
        loaded = store.load("priya", clock=lambda: NOW)
        after = loaded.plan()

    assert loaded.name == "Priya"
    assert after["energy_pct"] == before["energy_pct"]
    assert after["task_type"] == before["task_type"] and after["why"] == before["why"]
    assert loaded.schedule_items() == s.schedule_items()
    assert loaded.active_task == TaskType.REVIEW.value
    assert loaded.last_feeling == "Tired"
    assert len(loaded.checkin_history()) == 1


def test_a_new_day_gets_a_fresh_sample_schedule(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(_new_student())
    tomorrow = NOW + timedelta(days=1)
    with frozen_clock(tomorrow):
        loaded = store.load("priya", clock=lambda: tomorrow)
        items = loaded.schedule_items()
    assert items and {i["status"] for i in items} <= {"Missed", "Upcoming", "In progress", "Done"}
    assert loaded.planner.task_mapping.to_dict() == _new_student().planner.task_mapping.to_dict()


def test_student_ids_from_names():
    assert student_id_for("Priya S.") == "priya-s"
    with pytest.raises(ValueError):
        student_id_for("  !! ")


def test_unreadable_profile_files_are_skipped(tmp_path):
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    assert ProfileStore(tmp_path).students() == []
