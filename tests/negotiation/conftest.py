from datetime import datetime
from types import SimpleNamespace

import pytest

DAY = datetime(2026, 10, 28)


def at(hour: int, minute: int = 0) -> datetime:
    return DAY.replace(hour=hour, minute=minute)


@pytest.fixture
def events():
    """A typical afternoon: class, problem set, break, reading, meeting."""
    return [
        {"start": at(9), "end": at(10), "kind": "class", "title": "CSCE 634"},
        {
            "start": at(14),
            "end": at(15),
            "kind": "study",
            "session_id": "s1",
            "title": "Linear algebra problem set",
            "task_type": "problem_set",
        },
        {"start": at(15), "end": at(15, 10), "kind": "break"},
        {
            "start": at(15, 10),
            "end": at(16),
            "kind": "study",
            "session_id": "s2",
            "title": "Bio reading",
            "task_type": "reading",
        },
        {"start": at(17), "end": at(18), "kind": "meeting", "title": "Group meeting"},
    ]


@pytest.fixture
def schedule(events):
    return SimpleNamespace(student_id="stu-1", events=events)


def make_profile(schedule=None, energy=None, student_id="stu-1"):
    history = [] if energy is None else [SimpleNamespace(energy_level=energy)]
    return SimpleNamespace(student_id=student_id, schedule=schedule, energy_history=history)


@pytest.fixture
def freeze_now(monkeypatch):
    """Pin replanning's idea of "now" to a given time."""
    from negotiation import replanning

    def _freeze(when: datetime):
        monkeypatch.setattr(replanning, "_now", lambda reference=None: when)

    return _freeze
