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
from datetime import date, datetime, time, timedelta

from domain_model import StudentTaskMapping, TaskType, recommend_task_type
from domain_model.mapping import HIGH_ENERGY, LOW_ENERGY
from domain_model.onboarding import recommendation_summary
from domain_model.taxonomy import DEFAULT_DIFFICULTY
from negotiation import ReplanProposal, confirmation_message, resolve_answer
from user_model import EnergyReport, StudentProfile, StudentSchedule
from user_model.energy_estimate import estimate_energy_at
from user_model.survey import apply_sleep_survey

from . import assistant as chat_words
from .assistant import Commitment, Placement, TodoTask, fmt_minutes, parse_message, plan_sessions
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
    name: str = ""
    email: str = ""  # set when the student has an account (email or Google)
    wake_time: time = DEFAULT_WAKE
    sample_day: bool = True  # add the sample study day for today
    planner: StudySessionPlanner = field(init=False)
    completed: set[str] = field(default_factory=set)
    deferred: list[dict] = field(default_factory=list)  # moved to tomorrow
    active_task: str | None = None  # TaskType value of the running study session
    last_feeling: str = ""
    classes: list[Commitment] = field(default_factory=list)  # weekly classes + one-off busy blocks
    todo: list[TodoTask] = field(default_factory=list)  # tasks the week planner arranges
    chat_log: list[dict] = field(default_factory=list)  # {"role": "user"|"assistant", "text"}
    chat_stage: str = "classes"  # classes -> tasks -> planned
    _next_id: int = 0

    def __post_init__(self) -> None:
        self.name = self.name or self.student_id
        self.planner = StudySessionPlanner(student_id=self.student_id)
        self.planner.profile.schedule = StudentSchedule(self.student_id, events=[])
        self.set_sleep(self.sleep_hours)
        if self.sample_day:
            self._add_demo_sessions()

    # -- onboarding (a new student's first run) -------------------------------

    @classmethod
    def onboard(
        cls,
        student_id: str,
        name: str,
        typical_sleep_hours: float,
        typical_wake_time: time,
        task_preferences: dict[str, TaskType | str | None],
        clock: Callable[[], datetime] = now_local,
        email: str = "",
    ) -> DashboardSession:
        """Combined onboarding: Shivani's sleep questions + Vyshnavi's task preferences.

        `task_preferences` maps "low" / "medium" / "high" to a TaskType, or None
        for no preference (that bucket keeps the default rule).
        """
        session = cls(
            student_id=student_id,
            sleep_hours=typical_sleep_hours,
            clock=clock,
            name=name,
            email=email,
            wake_time=typical_wake_time,
            sample_day=False,
        )
        # user_model half: seeds sleep_hours and last night's sleep event.
        profile = StudentProfile(student_id=student_id)
        apply_sleep_survey(profile, typical_sleep_hours, typical_wake_time, now=clock())
        session.planner.profile = profile
        # domain_model half: survey answers become the recommendation prior.
        answers = {b: t for b, t in task_preferences.items() if t}
        session.planner.task_mapping = StudentTaskMapping.from_survey(student_id, answers)
        session.chat_log = [{"role": "assistant", "text": chat_words.GREETING}]
        return session

    def starting_suggestions(self) -> list[str]:
        """What the planner will suggest at each energy level (shown after onboarding)."""
        return recommendation_summary(self.planner.task_mapping)

    # -- saving between runs (Phase 3, step 9) --------------------------------

    def to_dict(self) -> dict:
        """JSON-safe snapshot: teammates' profile + mapping dicts, plus dashboard state."""
        deferred = StudentSchedule(self.student_id, events=self.deferred).to_dict()["events"]
        return {
            "schema_version": 1,
            "student_id": self.student_id,
            "name": self.name,
            "email": self.email,
            "wake_time": self.wake_time.strftime("%H:%M"),
            "profile": self.planner.profile.to_dict(),
            "task_mapping": self.planner.task_mapping.to_dict(),
            "completed": sorted(self.completed),
            "deferred": deferred,
            "active_task": self.active_task,
            "last_feeling": self.last_feeling,
            "next_id": self._next_id,
            "classes": [c.to_dict() for c in self.classes],
            "todo": [t.to_dict() for t in self.todo],
            "chat_log": self.chat_log[-80:],
            "chat_stage": self.chat_stage,
        }

    @classmethod
    def from_dict(cls, data: dict, clock: Callable[[], datetime] = now_local) -> DashboardSession:
        if data.get("schema_version", 1) != 1:
            raise ValueError(f"unsupported dashboard schema_version {data.get('schema_version')}")
        profile = StudentProfile.from_dict(data["profile"])
        session = cls(
            student_id=data["student_id"],
            sleep_hours=profile.sleep_hours if profile.sleep_hours is not None else 7.5,
            clock=clock,
            name=data.get("name", ""),
            email=data.get("email", ""),
            wake_time=time.fromisoformat(data.get("wake_time", "07:30")),
            sample_day=False,
        )
        if profile.schedule is None:
            profile.schedule = StudentSchedule(profile.student_id, events=[])
        session.planner.profile = profile
        session.planner.task_mapping = StudentTaskMapping.from_dict(data["task_mapping"])
        session.completed = set(data.get("completed", []))
        session.deferred = StudentSchedule.from_dict(
            {"student_id": profile.student_id, "events": data.get("deferred", [])}
        ).events
        session.active_task = data.get("active_task")
        session.last_feeling = data.get("last_feeling", "")
        session._next_id = int(data.get("next_id", 0))
        session.classes = [Commitment.from_dict(c) for c in data.get("classes", [])]
        session.todo = [TodoTask.from_dict(t) for t in data.get("todo", [])]
        session.chat_log = list(data.get("chat_log") or [])
        session.chat_stage = data.get("chat_stage", "classes")
        if not session.chat_log:
            session.chat_log = [{"role": "assistant", "text": chat_words.GREETING}]
        session.events.sort(key=lambda e: e["start"])
        session._sync_commitments()  # a new week: classes repeat
        return session

    def has_sessions_today(self) -> bool:
        today = self.clock().date()
        return any(
            e["kind"] in ("study", "break") and e["start"].astimezone(self.clock().tzinfo).date() == today
            for e in self.events
        )

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
            if e["start"].astimezone(now.tzinfo).date() != now.date():
                continue  # earlier days stay in the profile, not on today's card list
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
        wake = datetime.combine(now.date(), self.wake_time, tzinfo=now.tzinfo)
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

    # -- the week: classes, tasks and the schedule assistant ---------------------

    def _mint(self, prefix: str) -> str:
        self._next_id += 1
        return f"{prefix}-{self._next_id}"

    def _week_start(self, d: date | None = None) -> date:
        d = d or self.clock().date()
        return d - timedelta(days=d.weekday())

    def _sync_commitments(self) -> None:
        """Turn the class list into fixed "class"/"other" events (this week + two ahead).

        Negotiation already treats these kinds as fixed commitments, so a replan
        never moves a session on top of a class.
        """
        tz = self.clock().tzinfo
        keep = [e for e in self.events if "commitment_id" not in e]
        first = self._week_start()
        for offset in range(7 + chat_words.HORIZON_DAYS + 1):
            d = first + timedelta(days=offset)
            for c in self.classes:
                if c.occurs_on(d):
                    keep.append({
                        "kind": c.kind,
                        "start": datetime.combine(d, c.start, tzinfo=tz),
                        "end": datetime.combine(d, c.end, tzinfo=tz),
                        "title": c.title,
                        "commitment_id": c.commitment_id,
                    })
        self.planner.profile.schedule.events[:] = sorted(keep, key=lambda e: e["start"])

    def add_commitment(self, commitment: Commitment) -> None:
        self.classes.append(commitment)
        self._sync_commitments()

    def add_todo(self, task: TodoTask) -> None:
        self.todo.append(task)

    def _drop_auto_sessions(self, task_id: str | None = None, future_only: bool = True) -> None:
        now = self.clock()
        self.planner.profile.schedule.events[:] = [
            e for e in self.events
            if not (
                e.get("auto")
                and (task_id is None or e.get("task_id") == task_id)
                and e.get("session_id") not in self.completed
                and (not future_only or e["start"] >= now)
            )
        ]

    def remove_item(self, name: str) -> str | None:
        """Remove the class or task whose title best matches `name`; returns its title."""
        needle = name.lower().strip(" \"'")
        pool = [(c.title, "class", c) for c in self.classes] + [(t.title, "task", t) for t in self.todo]
        matches = [x for x in pool if needle and (needle in x[0].lower() or x[0].lower() in needle)]
        if not matches:
            return None
        title, what, item = min(matches, key=lambda x: abs(len(x[0]) - len(needle)))
        if what == "class":
            self.classes.remove(item)
            self._sync_commitments()
        else:
            self.todo.remove(item)
            self._drop_auto_sessions(item.task_id)
        return title

    def _energy_on_a_typical_day(self, at: time) -> float:
        """The user model's estimate at clock time `at`, on a day with the usual sleep."""
        today = self.clock()
        moment = datetime.combine(today.date(), at, tzinfo=today.tzinfo)
        return estimate_energy_at(self.planner.profile, moment).energy_level

    def _fit_score(self, level: float, task_type: str) -> float:
        """0..1: domain model's preference at this energy, plus hard-work-at-peak."""
        scores = self.planner.task_mapping.scores(level)
        top = max(scores.values()) or 1.0
        preferred = scores[TaskType(task_type)] / top
        difficulty = DEFAULT_DIFFICULTY[TaskType(task_type)]
        ideal = 0.3 + 0.6 * (difficulty - 1) / 4  # harder work wants more energy
        closeness = 1 - min(1.0, abs(level - ideal) / 0.6)
        return 0.6 * preferred + 0.4 * closeness

    def _fits(self, level: float, task_type: str) -> bool:
        return recommend_task_type(self.planner.task_mapping, level)[0].value == task_type

    def plan_week(self) -> tuple[list[Placement], dict[str, int]]:
        """(Re)arrange every to-do into the free time around the fixed blocks."""
        self._sync_commitments()
        self._drop_auto_sessions()
        now = self.clock()
        done: dict[str, int] = {}
        for e in self.events:
            if e.get("auto") and e.get("task_id") and (
                e["session_id"] in self.completed or e["end"] <= now
            ):
                done[e["task_id"]] = done.get(e["task_id"], 0) + _minutes(e["start"], e["end"])
        busy = [
            (e["start"], e["end"]) for e in self.events
            if e["kind"] not in ("sleep", "deadline") and "end" in e and e["end"] > now
        ]
        day_start = (datetime.combine(now.date(), self.wake_time) + timedelta(minutes=30)).time()
        placed, unplaced = plan_sessions(
            self.todo, busy, now, day_start,
            self._energy_on_a_typical_day, self._fit_score, self._fits, done,
        )
        for p in placed:
            sid = self.add_session(p.title, p.start, _minutes(p.start, p.end), TaskType(p.task_type))
            event = self._event(sid)
            event.update(auto=True, task_id=p.task_id)
        self.chat_stage = "planned"
        return placed, unplaced

    def _status(self, e: dict, now: datetime) -> str:
        if e["kind"] not in ("study", "break"):
            return "Done" if e["end"] <= now else ("Now" if e["start"] <= now else "Class")
        if e.get("session_id") in self.completed:
            return "Completed"
        if e["start"] <= now < e["end"]:
            return "In progress"
        if e["end"] <= now:
            return "Missed" if e["kind"] == "study" else "Done"
        return "Upcoming"

    def day_blocks(self, d: date) -> list[dict]:
        """Everything on day `d` (classes, busy blocks, sessions, breaks), for timelines."""
        now = self.clock()
        out = []
        for e in self.events:
            if e["kind"] in ("sleep", "deadline") or "end" not in e:
                continue
            start = e["start"].astimezone(now.tzinfo)
            if start.date() != d:
                continue
            task = e.get("task_type")
            level = self._energy_on_a_typical_day(start.time()) if task else None
            out.append({
                "session_id": e.get("session_id"),
                "kind": e["kind"],
                "title": e.get("title") or e["kind"].capitalize(),
                "start": start,
                "end": e["end"].astimezone(now.tzinfo),
                "minutes": _minutes(e["start"], e["end"]),
                "task_type": task,
                "status": self._status(e, now),
                "auto": bool(e.get("auto")),
                "fits": self._fits(level, task) if task else None,
            })
        return sorted(out, key=lambda b: b["start"])

    def week(self, start: date | None = None) -> list[dict]:
        first = start or self._week_start()
        return [{"date": first + timedelta(days=i), "blocks": self.day_blocks(first + timedelta(days=i))}
                for i in range(7)]

    def insights(self) -> dict:
        """Numbers for the Insights page, all from this week's real schedule."""
        now = self.clock()
        days = self.week()
        per_day, by_type = [], {t.value: 0 for t in TaskType}
        study = fixed = done_min = done_n = missed_n = fit_min = 0
        for day in days:
            s = f = 0
            for b in day["blocks"]:
                if b["kind"] == "study":
                    s += b["minutes"]
                    by_type[b["task_type"] or TaskType.REVIEW.value] += b["minutes"]
                    if b["fits"]:
                        fit_min += b["minutes"]
                    if b["status"] == "Completed":
                        done_min += b["minutes"]
                        done_n += 1
                    elif b["status"] == "Missed":
                        missed_n += 1
                elif b["kind"] != "break":
                    f += b["minutes"]
            per_day.append({"date": day["date"], "study": s, "fixed": f})
            study += s
            fixed += f
        curve = self.energy_curve()
        windows = [(curve[i][0], (curve[i][1] + curve[i + 1][1]) / 2) for i in range(len(curve) - 1)]
        peak_label, peak_pct = max(windows, key=lambda w: w[1])
        busiest = max(per_day, key=lambda d: d["study"] + d["fixed"])
        deadlines = []
        for t in sorted(self.todo, key=lambda t: t.due):
            sessions = [e for e in self.events if e.get("task_id") == t.task_id]
            planned = sum(_minutes(e["start"], e["end"]) for e in sessions)
            finished = sum(_minutes(e["start"], e["end"]) for e in sessions
                           if e["session_id"] in self.completed)
            deadlines.append({
                "title": t.title, "task_type": t.task_type, "due": t.due,
                "days_left": (t.due - now.date()).days, "needed": t.minutes,
                "planned": planned, "done": finished,
                "status": "Done" if finished >= t.minutes else
                          "Planned" if planned >= t.minutes else
                          "Not planned yet" if not planned else "Short on time",
            })
        return {
            "week_start": days[0]["date"], "per_day": per_day, "by_type": by_type,
            "study_min": study, "fixed_min": fixed, "done_min": done_min,
            "done_n": done_n, "missed_n": missed_n,
            "fit_pct": round(100 * fit_min / study) if study else None,
            "peak_start": peak_label, "peak_pct": round(peak_pct),
            "busiest": busiest if busiest["study"] + busiest["fixed"] else None,
            "deadlines": deadlines,
        }

    # -- the chat -----------------------------------------------------------------

    def chat(self, text: str) -> str:
        """One turn with the schedule assistant. Returns (and logs) the reply."""
        text = (text or "").strip()
        if not text:
            return ""
        if not self.chat_log:
            self.chat_log.append({"role": "assistant", "text": chat_words.GREETING})
        self.chat_log.append({"role": "user", "text": text})
        reply = self._reply(text)
        self.chat_log.append({"role": "assistant", "text": reply})
        return reply

    def _list_text(self) -> str:
        lines = []
        if self.classes:
            lines.append("**Fixed each week**")
            lines += [f"- {c.title}: {c.when()}" for c in self.classes]
        if self.todo:
            lines.append("**To do**")
            lines += [f"- {t.title}: {TaskType(t.task_type).label}, {fmt_minutes(t.minutes)}, "
                      f"due {t.due:%a %b} {t.due.day}" for t in sorted(self.todo, key=lambda t: t.due)]
        return "\n".join(lines) or "Nothing yet. Send me a class or a task to start."

    def _plan_text(self, placed: list[Placement], unplaced: dict[str, int]) -> str:
        if not placed and not unplaced:
            return "Everything on your list is already done or planned. Nice."
        total = sum(_minutes(p.start, p.end) for p in placed)
        fits = sum(_minutes(p.start, p.end) for p in placed if p.fits)
        days: dict[date, list[str]] = {}
        for p in placed:
            days.setdefault(p.start.date(), []).append(
                f"{p.start:%H:%M} {p.title} ({fmt_minutes(_minutes(p.start, p.end))})")
        lines = [(f"Here's your plan: **{len(placed)} sessions, {fmt_minutes(total)}** over "
                 f"{len(days)} day{'s' if len(days) != 1 else ''}.")]
        if total:
            lines.append(f"{round(100 * fits / total)}% of that time sits where your energy suits the task "
                         "(harder work in your high-energy hours, lighter work when you dip).")
        for d, items in sorted(days.items()):
            lines.append(f"- **{d:%a %b} {d.day}**: " + " · ".join(items))
        titles = {t.task_id: t.title for t in self.todo}
        for task_id, minutes in unplaced.items():
            lines.append(f"- ⚠️ Couldn't fit {fmt_minutes(minutes)} of **{titles.get(task_id, task_id)}** "
                         "before it's due. Free up some time or give it a later date.")
        lines.append("\nOpen the **Week** tab to see it laid out. Add or remove anything and say "
                     "**plan my week** again to re-arrange.")
        return "\n".join(lines)

    def _reply(self, text: str) -> str:
        parsed = parse_message(text, self.clock().date(), self._mint)
        if parsed.intent == "command":
            return self._command(parsed.command, parsed.arg)
        if parsed.intent == "commitment":
            c = parsed.commitment
            self.add_commitment(c)
            what = "class" if c.kind == "class" else "busy block"
            nxt = ("Next class, or say **done** when that's all." if self.chat_stage == "classes"
                   else "Say **plan my week** and I'll plan around it.")
            return f"Blocked your {what} **{c.title}**: {c.when()}. {nxt}"
        if parsed.intent == "task":
            t = parsed.task
            self.add_todo(t)
            moved = ""
            if self.chat_stage == "classes":
                self.chat_stage = "tasks"
                moved = " (That sounded like a task, so I've moved on to your to-do list. You can still send classes.)"
            note = (f" I assumed {' and '.join(parsed.assumed)}; if that's off, say `remove {t.title}` "
                    "and send it again with the details.") if parsed.assumed else ""
            return (f"Added **{t.title}**: {TaskType(t.task_type).label}, {fmt_minutes(t.minutes)}, "
                    f"due {t.due:%a %b} {t.due.day}.{note}{moved} Anything else? Or say **plan my week**.")
        if parsed.intent == "needs_days":
            return (f"Which days is **{parsed.arg}**? Send it again with the days, like `MWF` or `Tue Thu`, "
                    "or a date like `tomorrow`.")
        return "I didn't catch that. Try `CSCE 634 MWF 10:20-11:10` for a class or " \
               "`stats homework due Friday 2h` for a task, or say **help**."

    def _command(self, command: str, arg: str) -> str:
        if command == "hello":
            return chat_words.GREETING if self.chat_stage == "classes" else chat_words.TASKS_PROMPT
        if command == "help":
            return chat_words.HELP
        if command == "show":
            return self._list_text()
        if command == "done" and self.chat_stage == "classes":
            self.chat_stage = "tasks"
            n = len(self.classes)
            got = f"Got it, {n} fixed block{'s' if n != 1 else ''} saved. " if n else "No classes, no problem. "
            return got + chat_words.TASKS_PROMPT
        if command in ("done", "plan"):
            if not self.todo:
                return "There's nothing to plan yet. Tell me a task first, like `stats homework due Friday 2h`."
            return self._plan_text(*self.plan_week())
        if command == "remove":
            title = self.remove_item(arg)
            return f"Removed **{title}**." if title else f"I couldn't find \"{arg}\". Say **show** to see your list."
        if command == "clear_classes":
            self.classes.clear()
            self._sync_commitments()
            return "Cleared your classes."
        if command == "clear_tasks":
            for t in self.todo:
                self._drop_auto_sessions(t.task_id)
            self.todo.clear()
            return "Cleared your to-do list."
        # reset
        self._drop_auto_sessions()
        self.classes.clear()
        self.todo.clear()
        self._sync_commitments()
        self.chat_stage = "classes"
        self.chat_log = []
        return chat_words.GREETING
