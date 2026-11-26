"""Thin API between the Streamlit dashboard and StudySessionPlanner (Phase 3, step 8).

The dashboard (frontend/app.py) only talks to `DashboardSession`; it never
imports user_model / domain_model / negotiation directly. Everything here is
plain Python with no Streamlit, so it is unit-tested like the rest of
integration. No domain logic lives here either: energy, recommendations,
explanations and replans all come from the owning modules via the planner.
This file only translates between UI words ("Tired", "Meeting ran late",
"Mark completed") and planner calls, and keeps today's schedule up to date
when the student accepts a change.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from domain_model import TaskType
from domain_model.mapping import HIGH_ENERGY, LOW_ENERGY
from negotiation import ReplanProposal, confirmation_message, resolve_answer
from user_model import EnergyReport, StudentSchedule
from user_model.energy_estimate import estimate_energy_at

from .planner import StudySessionPlanner

# UI one-tap check-in -> words the user model's check-in parser understands.
FEELINGS = {"Tired": "tired", "Fine": "fine", "Energized": "energized"}

# UI disruption choices -> negotiation triggers (see negotiation/replanning.py).
DISRUPTIONS = {
    "Meeting ran late": "meeting_ran_late:20",
    "I am feeling tired": "fatigue",
    "I missed a study session": "missed_session",
    "Something else came up": "something_else",  # always gets the "ask" fallback
}

SOURCE_TEXT = {
    "baseline": "Estimated from your sleep and the time of day.",
    "checkin_corrected": "Estimated from your sleep, adjusted using your latest check-in.",
}

DEFAULT_WAKE = time(7, 30)


def now_local() -> datetime:
    return datetime.now().astimezone()


def energy_label(level: float) -> str:
    """Same cut points as domain_model's buckets, so the label matches the 'why'."""
    if level < LOW_ENERGY:
        return "Low energy"
    if level < HIGH_ENERGY:
        return "Moderate energy"
    return "High energy"


def _fmt_time(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _minutes(start: datetime, end: datetime) -> int:
    return round((end - start).total_seconds() / 60)


@dataclass
class DashboardSession:
    """One student's live dashboard session."""

    student_id: str = "demo"
    sleep_hours: float = 7.5
    clock: Callable[[], datetime] = now_local
    planner: StudySessionPlanner = field(init=False)
    completed: set[str] = field(default_factory=set)
    deferred: list[dict] = field(default_factory=list)  # moved to tomorrow
    active_task: str | None = None  # TaskType value of the running study session
    last_feeling: str = ""
    _next_id: int = 0

    def __post_init__(self) -> None:
        self.planner = StudySessionPlanner(student_id=self.student_id)
        self.planner.profile.schedule = StudentSchedule(self.student_id, events=[])
        self.set_sleep(self.sleep_hours)
        self._add_demo_sessions()

    # -- schedule ------------------------------------------------------------

    @property
    def events(self) -> list[dict]:
        return self.planner.profile.schedule.events

    def _new_id(self) -> str:
        self._next_id += 1
        return f"session-{self._next_id}"

    def _add_demo_sessions(self) -> None:
        """A sample day around the current time, so every replan path has something to act on."""
        now = self.clock().replace(second=0, microsecond=0)
        base = now - timedelta(minutes=now.minute % 15)  # round down to the quarter hour
        demo = [
            (-120, 45, "Biology reading", TaskType.READING, "study"),
            (15, 60, "Data structures problem set", TaskType.PROBLEM_SET, "study"),
            (90, 15, "Short break", None, "break"),
            (120, 45, "Exam review", TaskType.REVIEW, "study"),
            (195, 30, "Spanish vocab flashcards", TaskType.MEMORIZATION, "study"),
        ]
        for offset, minutes, title, task_type, kind in demo:
            start = base + timedelta(minutes=offset)
            self.add_session(title, start, minutes, task_type, kind=kind)

    def add_session(
        self,
        title: str,
        start: datetime,
        minutes: int,
        task_type: TaskType | None = None,
        kind: str = "study",
    ) -> str:
        session_id = self._new_id()
        event = {
            "kind": kind,
            "start": start,
            "end": start + timedelta(minutes=minutes),
            "title": title,
            "session_id": session_id,
        }
        if task_type is not None:
            event["task_type"] = TaskType(task_type).value
        self.events.append(event)
        self.events.sort(key=lambda e: e["start"])
        return session_id

    def _event(self, session_id: str) -> dict | None:
        return next((e for e in self.events if e.get("session_id") == session_id), None)

    def mark_completed(self, session_id: str) -> None:
        if self._event(session_id) is not None:
            self.completed.add(session_id)

    def schedule_items(self) -> list[dict]:
        """Today's sessions as the dashboard's schedule cards need them."""
        now = self.clock()
        items = []
        for e in self.events:
            if e["kind"] not in ("study", "break"):
                continue
            sid = e["session_id"]
            if sid in self.completed:
                status = "Completed"
            elif e["start"] <= now < e["end"]:
                status = "In progress"
            elif e["end"] <= now:
                status = "Missed" if e["kind"] == "study" else "Done"
            else:
                status = "Upcoming"
            task = e.get("task_type")
            items.append(
                {
                    "session_id": sid,
                    "time": _fmt_time(e["start"]),
                    "task": e["title"],
                    "task_type": TaskType(task).label if task else "Break",
                    "duration": f"{_minutes(e['start'], e['end'])} min",
                    "status": status,
                }
            )
        return items

    # -- sleep, energy and the recommendation -----------------------------------

    def set_sleep(self, hours: float) -> None:
        """Last night's sleep, as a 'sleep' event ending at the usual wake time."""
        self.sleep_hours = float(hours)
        now = self.clock()
        wake = datetime.combine(now.date(), DEFAULT_WAKE, tzinfo=now.tzinfo)
        if wake > now:
            wake -= timedelta(days=1)
        sleep = {
            "kind": "sleep",
            "start": wake - timedelta(hours=self.sleep_hours),
            "end": wake,
            "title": "last night's sleep",
        }
        self.planner.profile.schedule.events[:] = [
            e for e in self.events if e["kind"] != "sleep"
        ] + [sleep]
        self.events.sort(key=lambda e: e["start"])
        self.planner.profile.sleep_hours = self.sleep_hours

    def checkin(self, feeling: str) -> EnergyReport:
        """One-tap check-in ("Tired" / "Fine" / "Energized")."""
        report = self.planner.handle_checkin(FEELINGS[feeling])
        self.last_feeling = feeling
        return report

    def plan(self) -> dict:
        """Energy now + the recommended task type and its one-sentence 'why'."""
        plan = self.planner.plan_day()
        energy: EnergyReport = plan["energy"]
        task: TaskType = plan["recommended_task_type"]
        return {
            "energy_level": energy.energy_level,
            "energy_pct": round(energy.energy_level * 100),
            "energy_label": energy_label(energy.energy_level),
            "energy_source": SOURCE_TEXT.get(energy.source, ""),
            "task_type": task.value,
            "task_label": task.label,
            "why": plan["why"],
            "cold_start": self.planner.profile.cold_start,
        }

    def energy_curve(self, hours: range = range(8, 23)) -> list[tuple[str, int]]:
        """The user model's estimate for each hour today, from current sleep + history."""
        today = self.clock()
        points = []
        for hour in hours:
            at = today.replace(hour=hour, minute=0, second=0, microsecond=0)
            level = estimate_energy_at(self.planner.profile, at).energy_level
            points.append((_fmt_time(at), round(level * 100)))
        return points

    def checkin_history(self) -> list[tuple[str, int]]:
        return [
            (_fmt_time(r.timestamp), round(r.energy_level * 100))
            for r in self.planner.profile.checkin_reports()
        ]

    # -- studying (feeds learning) --------------------------------------------

    def start_task(self, task_type: str) -> None:
        """Starting a task type is a choice the domain model learns from."""
        chosen = TaskType(task_type)
        level = self.plan()["energy_level"]
        self.planner.task_mapping.record_choice(level, chosen)
        self.active_task = chosen.value

    def finish_task(self) -> str | None:
        """End the running session; marks the matching in-progress/next session done."""
        finished, self.active_task = self.active_task, None
        now = self.clock()
        for e in self.events:
            if (
                e["kind"] == "study"
                and e.get("task_type") == finished
                and e["session_id"] not in self.completed
                and e["end"] > now - timedelta(hours=1)
            ):
                self.completed.add(e["session_id"])
                break
        return finished

    # -- replanning --------------------------------------------------------------

    def disrupt(self, choice: str) -> ReplanProposal:
        """Something changed: ask negotiation for a proposal (never applied silently)."""
        return self.planner.handle_disruption(DISRUPTIONS[choice])

    @staticmethod
    def is_ask(proposal: ReplanProposal) -> bool:
        return proposal.proposed_change.get("action") == "ask"

    def respond(self, proposal: ReplanProposal, response: str) -> str:
        """Accept or reject a concrete proposal; accepted changes update the schedule."""
        resolution = self.planner.handle_resolution(proposal, response)
        if resolution.outcome == "accepted":
            self._apply_session_change(proposal.proposed_change)
            return "Done. Your schedule is updated."
        return "No problem, I'll keep your original plan."

    def answer_ask(self, proposal: ReplanProposal, answer: str) -> str:
        """The interactive 'tell me what changed' flow (negotiation #18)."""
        resolution = resolve_answer(proposal, answer)
        response = "edit" if resolution.outcome == "edited" else "reject"
        self.planner.handle_resolution(proposal, response, edited_change=resolution.edited_change)
        if resolution.outcome == "edited" and resolution.edited_change:
            self._apply_answer_change(resolution.edited_change)
        return confirmation_message(resolution)

    def _apply_session_change(self, change: dict) -> None:
        event = self._event(change.get("session_id") or "")
        if event is None or "new_start" not in change:
            return
        tz = event["start"].tzinfo
        event["start"] = datetime.fromisoformat(change["new_start"]).astimezone(tz)
        event["end"] = datetime.fromisoformat(change["new_end"]).astimezone(tz)
        self.events.sort(key=lambda e: e["start"])

    def _next_open_session(self) -> dict | None:
        now = self.clock()
        for e in self.events:
            if e["kind"] == "study" and e["end"] > now and e["session_id"] not in self.completed:
                return e
        return None

    def _apply_answer_change(self, change: dict) -> None:
        """Apply a free-text answer's change to the current/next study session."""
        event = self._next_open_session()
        action, minutes = change.get("action"), change.get("minutes")
        if event is None or action in (None, "note"):
            return
        if change.get("task_type"):
            event["task_type"] = change["task_type"]
        if action == "shorten" and minutes:
            event["end"] = event["start"] + timedelta(minutes=minutes)
        elif action == "move" and minutes:
            event["start"] += timedelta(minutes=minutes)
            event["end"] += timedelta(minutes=minutes)
        elif action == "defer":
            if change.get("when") == "tomorrow":
                self.events.remove(event)
                self.deferred.append(event)
            else:
                shift = max(timedelta(hours=1), self.clock() - event["start"] + timedelta(hours=1))
                event["start"] += shift
                event["end"] += shift
        self.events.sort(key=lambda e: e["start"])
