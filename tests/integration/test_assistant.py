"""Schedule assistant: chat -> classes + tasks -> an energy-aware week plan."""

import itertools
from datetime import date, datetime, time, timedelta, timezone

import pytest

from domain_model import TaskType
from integration.assistant import _chunks, parse_message
from integration.dashboard import DashboardSession
from integration.evaluation.simulate import frozen_clock

CST = timezone(timedelta(hours=-6))
NOW = datetime(2026, 11, 27, 9, 0, tzinfo=CST)  # a Friday morning
TODAY = NOW.date()


def _parse(text):
    ids = itertools.count(1)
    return parse_message(text, TODAY, lambda p: f"{p}-{next(ids)}")


@pytest.mark.parametrize(
    ("text", "title", "days", "start", "end", "kind"),
    [
        ("CSCE 634 MWF 10:20-11:10", "CSCE 634", [0, 2, 4], time(10, 20), time(11, 10), "class"),
        ("Distributed Systems Tue Thu 2:20pm-3:35pm", "Distributed Systems", [1, 3], time(14, 20),
         time(15, 35), "class"),
        ("CSCE 678 TTh 9:35-10:50", "CSCE 678", [1, 3], time(9, 35), time(10, 50), "class"),
        ("I have chemistry class Monday and Wednesday 9 to 10:15 am", "Chemistry", [0, 2], time(9),
         time(10, 15), "class"),
        ("Bio lab TR 11-12:15pm", "Bio lab", [1, 3], time(11), time(12, 15), "class"),
        ("work Sat 9-1", "Work", [5], time(9), time(13), "other"),
    ],
)
def test_weekly_commitments(text, title, days, start, end, kind):
    p = _parse(text)
    assert p.intent == "commitment"
    c = p.commitment
    assert (c.title, c.days, c.start, c.end, c.kind) == (title, days, start, end, kind)


def test_one_off_busy_block_on_a_date():
    c = _parse("dentist tomorrow 3-4pm").commitment
    assert (c.title, c.on, c.start, c.end) == ("Dentist", TODAY + timedelta(days=1), time(15), time(16))


def test_a_time_without_days_asks_which_days():
    assert _parse("CSCE 634 10:20-11:10").intent == "needs_days"


@pytest.mark.parametrize(
    ("text", "title", "task_type", "minutes", "due"),
    [
        ("IUI final report due Dec 3, 4 hours", "IUI final report", TaskType.PROBLEM_SET, 240, date(2026, 12, 3)),
        ("read chapter 8 by Thursday 1h", "Read chapter 8", TaskType.READING, 60, date(2026, 12, 3)),
        ("flashcards 30 min by Wed", "Flashcards", TaskType.MEMORIZATION, 30, date(2026, 12, 2)),
        ("Database assignment 2h 30m due 12/2", "Database assignment", TaskType.PROBLEM_SET, 150,
         date(2026, 12, 2)),
        ("review for midterm due tomorrow, half an hour", "Review for midterm", TaskType.REVIEW, 30,
         date(2026, 11, 28)),
    ],
)
def test_tasks(text, title, task_type, minutes, due):
    p = _parse(text)
    assert p.intent == "task" and not p.assumed
    t = p.task
    assert (t.title, t.task_type, t.minutes, t.due) == (title, task_type.value, minutes, due)


def test_missing_details_get_defaults_that_are_said_out_loud():
    p = _parse("study for the midterm")
    assert p.intent == "task" and p.task.minutes == 60 and len(p.assumed) == 2


@pytest.mark.parametrize(("text", "command"), [
    ("plan my week", "plan"), ("ok make my schedule", "plan"), ("done", "done"), ("that's all", "done"),
    ("show", "show"), ("remove stats homework", "remove"), ("start over", "reset"), ("help", "help"),
])
def test_commands(text, command):
    p = _parse(text)
    assert (p.intent, p.command) == ("command", command)


def test_long_tasks_are_split_into_sessions():
    assert _chunks(240, "problem_set") == [60, 60, 60, 60]
    assert _chunks(70, "problem_set") == [35, 35]  # evened out, no 10-minute stub
    assert sum(_chunks(95, "reading")) == 95


@pytest.fixture
def student():
    with frozen_clock(NOW):
        s = DashboardSession.onboard(
            student_id="h", name="Harshini", typical_sleep_hours=7.5, typical_wake_time=time(7, 30),
            task_preferences={"low": None, "medium": None, "high": None}, clock=lambda: NOW,
        )
        yield s


def _sessions(s):
    return [e for e in s.events if e.get("auto")]


def test_full_conversation_builds_a_week_around_classes(student):
    with frozen_clock(NOW):
        assert "Blocked" in student.chat("CSCE 634 MWF 10:20-11:10")
        assert "Blocked" in student.chat("Distributed Systems Tue Thu 2:20pm-3:35pm")
        assert "what do you need" in student.chat("done").lower()
        assert "Added" in student.chat("IUI final report due Dec 3, 4 hours")
        assert "Added" in student.chat("read chapter 8 by Thursday 1h")
        reply = student.chat("plan my week")
    assert "sessions" in reply and "⚠️" not in reply
    sessions = _sessions(student)
    assert sum((e["end"] - e["start"]).seconds // 60 for e in sessions) == 300
    fixed = [e for e in student.events if e["kind"] == "class"]
    for s in sessions:
        assert s["start"] >= NOW and s["end"].time() <= time(22)
        assert s["start"].time() >= time(8)  # wake + 30 min
        for c in fixed:  # never on top of a class, and 10 minutes clear of it
            assert s["end"] + timedelta(minutes=10) <= c["start"] or s["start"] >= c["end"] + timedelta(minutes=10)
    report = [s for s in sessions if s["title"] == "IUI final report"]
    assert all(s["start"].date() <= date(2026, 12, 3) for s in report)
    assert len({s["start"].date() for s in report}) >= 3  # spread out, not crammed into one day


def test_replanning_is_idempotent_and_keeps_finished_work(student):
    with frozen_clock(NOW):
        student.chat("stats homework due Monday 2h")
        student.chat("plan my week")
        first = sorted(_sessions(student), key=lambda e: e["start"])
        student.completed.add(first[0]["session_id"])
        student.chat("plan my week")
    again = _sessions(student)
    assert sum((e["end"] - e["start"]).seconds // 60 for e in again) == 120  # not double-booked
    assert first[0] in again


def test_too_much_work_is_flagged_not_silently_dropped(student):
    with frozen_clock(NOW):
        reply = student.chat("thesis draft due today 20 hours")
        reply = student.chat("plan my week")
    assert "Couldn't fit" in reply


def test_remove_and_show(student):
    with frozen_clock(NOW):
        student.chat("CSCE 634 MWF 10:20-11:10")
        student.chat("stats homework due Monday 2h")
        assert "CSCE 634" in student.chat("show") and "Stats homework" in student.chat("show")
        assert "Removed" in student.chat("remove csce 634")
    assert not student.classes and not [e for e in student.events if e["kind"] == "class"]


def test_replans_from_negotiation_avoid_classes(student):
    with frozen_clock(NOW):
        student.chat("CSCE 634 MWF 10:20-11:10")
        student.add_session("Problem set", NOW + timedelta(minutes=15), 60, TaskType.PROBLEM_SET)  # 9:15-10:15
        proposal = student.disrupt("Meeting ran late")
    change = proposal.proposed_change
    if "new_start" in change:
        start, end = datetime.fromisoformat(change["new_start"]), datetime.fromisoformat(change["new_end"])
        cls = next(e for e in student.events if e["kind"] == "class" and e["start"].date() == TODAY)
        assert end <= cls["start"] or start >= cls["end"]


def test_insights_come_from_the_real_week(student):
    with frozen_clock(NOW):
        student.chat("CSCE 634 MWF 10:20-11:10")
        student.chat("stats homework due Monday 2h")
        student.chat("plan my week")
        info = student.insights()
    assert info["study_min"] == 120
    assert info["fixed_min"] >= 50  # at least today's class
    assert info["deadlines"][0]["status"] == "Planned"
    assert 0 <= (info["fit_pct"] or 0) <= 100
    assert len(info["per_day"]) == 7
