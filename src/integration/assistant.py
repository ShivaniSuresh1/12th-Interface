"""Schedule assistant: a small rule-based chat that builds the student's week.

The student talks to it in plain text ("CSCE 634 MWF 10:20-11:10",
"IUI report due Thursday, 4 hours"). It understands three things:

* fixed commitments -- weekly classes, or a one-off busy block on a date;
* study tasks -- a title, how long it takes and when it's due;
* commands -- plan my week, show my list, remove X, start over, help.

`plan_sessions` then places the tasks into the free time around the
commitments, putting each task where the student's estimated energy fits
it best (the user model's energy curve, scored by the domain model's
task mapping), spreading work across days and finishing before the due
date. Nothing here imports Streamlit, and no energy or recommendation
logic lives here: both come in as functions from the owning modules.

Deliberately rule-based (no LLM): deterministic, offline, testable, and
consistent with the negotiation module's rule-based ask fallback.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta

from domain_model import TaskType

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_END = time(22, 0)  # nothing gets planned after this
LATE_HOUR = 19.5  # sessions starting later than this get a gentle penalty
GAP = timedelta(minutes=10)  # breathing room around every block
GRID = 15  # candidate start times every 15 minutes
MAX_CHUNK = {"problem_set": 60, "review": 60, "reading": 45, "memorization": 30}
MIN_CHUNK = 25
DEFAULT_TASK_MINUTES = 60
DEFAULT_DUE_DAYS = 6
HORIZON_DAYS = 14

# -- data ---------------------------------------------------------------------


@dataclass
class Commitment:
    """A class (weekly on `days`) or a one-off busy block (`on` a date)."""

    commitment_id: str
    title: str
    start: time
    end: time
    days: list[int] = field(default_factory=list)  # 0 = Monday
    on: date | None = None
    kind: str = "class"  # "class" | "other" (fixed commitments for negotiation)

    def occurs_on(self, d: date) -> bool:
        return d == self.on if self.on else d.weekday() in self.days

    def when(self) -> str:
        days = self.on.strftime("%a %b %-d") if self.on else ", ".join(DAY_NAMES[i] for i in self.days)
        return f"{days} {self.start:%H:%M}–{self.end:%H:%M}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(start=self.start.strftime("%H:%M"), end=self.end.strftime("%H:%M"),
                 on=self.on.isoformat() if self.on else None)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Commitment:
        return cls(
            commitment_id=d["commitment_id"], title=d["title"],
            start=time.fromisoformat(d["start"]), end=time.fromisoformat(d["end"]),
            days=list(d.get("days") or []), on=date.fromisoformat(d["on"]) if d.get("on") else None,
            kind=d.get("kind", "class"),
        )


@dataclass
class TodoTask:
    """Something to study: `minutes` of `task_type` work, finished by `due`."""

    task_id: str
    title: str
    task_type: str  # TaskType value
    minutes: int
    due: date

    def to_dict(self) -> dict:
        return {**asdict(self), "due": self.due.isoformat()}

    @classmethod
    def from_dict(cls, d: dict) -> TodoTask:
        return cls(d["task_id"], d["title"], TaskType(d["task_type"]).value, int(d["minutes"]),
                   date.fromisoformat(d["due"]))


@dataclass
class Parsed:
    """What one chat message means."""

    intent: str  # "commitment" | "task" | "command" | "needs_days" | "unknown"
    commitment: Commitment | None = None
    task: TodoTask | None = None
    command: str = ""
    arg: str = ""
    assumed: list[str] = field(default_factory=list)  # defaults we filled in


# -- parsing --------------------------------------------------------------------

_DAY_WORDS = {
    "mon": 0, "monday": 0, "tue": 1, "tues": 1, "tuesday": 1, "wed": 2, "weds": 2,
    "wednesday": 2, "thu": 3, "thur": 3, "thurs": 3, "thursday": 3, "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5, "sun": 6, "sunday": 6,
}
_DAY_GROUPS = {"weekdays": [0, 1, 2, 3, 4], "weekday": [0, 1, 2, 3, 4], "daily": list(range(7)),
               "everyday": list(range(7)), "weekends": [5, 6], "weekend": [5, 6]}
_COMPACT = re.compile(r"(?:Th|Tu|Sa|Su|M|T|W|R|F|S|U)+")
_COMPACT_CODES = {"Th": 3, "Tu": 1, "Sa": 5, "Su": 6, "M": 0, "T": 1, "W": 2, "R": 3, "F": 4,
                  "S": 5, "U": 6}

_T = r"(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?"
_RANGE = re.compile(rf"(?<![\d:]){_T}\s*(?:-|–|—|to|until|till)\s*{_T}(?![\d:])", re.IGNORECASE)
_DUR = re.compile(
    r"(?P<h>\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\b(?:\s*(?:and\s*)?(?P<hm>\d+)\s*(?:m|min|mins|minutes)\b)?"
    r"|(?P<m>\d+)\s*(?:m|min|mins|minute|minutes)\b"
    r"|(?P<half>half\s+an?\s+hour|half\s+hour)"
    r"|(?P<one>\ban?\s+hour\b)",
    re.IGNORECASE,
)
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_DATE = (r"(?P<rel>today|tonight|tomorrow|tmrw|tmr)"
         r"|(?:(?:this|next)\s+)?(?P<wd>mon|tue|wed|thu|fri|sat|sun)[a-z]*"
         r"|(?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(?P<md>\d{1,2})(?:st|nd|rd|th)?"
         r"|(?P<sm>\d{1,2})/(?P<sd>\d{1,2})")
_DUE = re.compile(rf"\b(?:due|by|before|deadline)\s+(?:on\s+)?(?:{_DATE})\b", re.IGNORECASE)
_ON_DATE = re.compile(rf"\b(?:on\s+)?(?:{_DATE})\b", re.IGNORECASE)

_TYPE_WORDS = [
    (TaskType.MEMORIZATION, r"flash ?cards?|vocab|memori[sz]e|anki|terms|definitions"),
    (TaskType.READING, r"\bread|chapter|\bch\.? ?\d|paper|article|textbook|pages?\b"),
    (TaskType.PROBLEM_SET, (r"assignment|homework|\bhw\b|problem|pset|project|code|coding|program|"
                           r"implement|debug|\blab\b|report|essay|write|writing|draft|presentation|slides")),
    (TaskType.REVIEW, r"review|study|exam|midterm|final|quiz|test\b|practice|revise|notes|prep"),
]
_CLASS_WORDS = re.compile(r"\b(class|classes|lecture|lectures|lab|seminar|recitation|section|course)\b", re.IGNORECASE)
_BUSY_WORDS = re.compile(r"\b(busy|work|shift|meeting|appointment|gym|practice|club|event|dinner)\b", re.IGNORECASE)

_COMMANDS = [
    ("plan", (r"^(?:ok(?:ay)?[, ]+)?(?:please\s+)?(?:plan|schedule|arrange|build|make|organi[sz]e|create|do)\b"
             r"(?!.*\b(?:due|by)\b)")),
    ("done", r"^(?:done|that'?s (?:it|all)|no more|nope|no|next|finished|all done|skip)\b"),
    ("show", r"^(?:show|list|what do i have|what'?s on|summary|my list)\b"),
    ("reset", r"^(?:start over|reset|clear (?:all|everything))\b"),
    ("clear_classes", r"^clear (?:my )?(?:classes|class schedule|commitments)\b"),
    ("clear_tasks", r"^clear (?:my )?(?:tasks|to-?dos?|list)\b"),
    ("remove", r"^(?:remove|delete|drop|cancel)\s+(?P<arg>.+)$"),
    ("help", r"^(?:help|how|what can you do|\?)"),
    ("hello", r"^(?:hi|hey|hello|yo|sup)\b"),
]

_LEAD_FILLER = re.compile(
    r"^(?:(?:and|also|plus|then|ok|okay|so|um|i|i've|ive|i'm|im|have|has|got|get|need|needs|to|"
    r"gotta|must|should|want|my|a|an|the|finish|do|is|there's|theres|on|at|from|for|"
    r"every|with)\b[\s,]*)+",
    re.IGNORECASE,
)
_TRAIL_FILLER = re.compile(
    r"(?:[\s,;:.\-–—]+|\b(?:on|at|from|for|by|due|and|that|takes?|about|around|roughly|approx|"
    r"it|its|it's|which|will|in|every|each)\b)+$",
    re.IGNORECASE,
)


def _clean_title(text: str, spans: list[tuple[int, int]], is_class: bool) -> str:
    keep, last = [], 0
    for a, b in sorted(spans):
        if a >= last:
            keep.append(text[last:a])
            last = b
    keep.append(text[last:])
    title = " ".join("".join(keep).split())
    if is_class:
        title = re.sub(r"\b(?:classes|class|lectures|lecture|course)\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"[()\[\]]", " ", title)
    for _ in range(3):
        title = _LEAD_FILLER.sub("", title.strip(" ,;:.-–—"))
        title = _TRAIL_FILLER.sub("", title)
    title = " ".join(title.split())
    return title[:1].upper() + title[1:] if title else ""


def _resolve_range(m: re.Match) -> tuple[time, time] | None:
    h1, m1, s1, h2, m2, s2 = m.groups()
    h1, h2 = int(h1), int(h2)
    m1, m2 = int(m1 or 0), int(m2 or 0)
    if h1 > 23 or h2 > 23 or m1 > 59 or m2 > 59:
        return None
    s1 = (s1 or "").lower().replace(".", "")[:1]
    s2 = (s2 or "").lower().replace(".", "")[:1]

    def to24(h: int, suf: str) -> int:
        if suf == "a":
            return 0 if h == 12 else h
        if suf == "p":
            return h if h == 12 else h + 12
        return h

    if not s1 and s2 and h1 <= 12:
        s1 = s2 if to24(h1, s2) * 60 + m1 <= to24(h2, s2) * 60 + m2 else ("a" if s2 == "p" else "p")
    start_h = to24(h1, s1) if s1 or h1 > 12 else (h1 + 12 if 1 <= h1 <= 7 else h1)
    end_h = to24(h2, s2) if s2 or h2 > 12 else h2
    if not s2 and h2 <= 12 and end_h * 60 + m2 <= start_h * 60 + m1:
        end_h = h2 + 12 if h2 < 12 else h2
    if end_h > 23 or end_h * 60 + m2 <= start_h * 60 + m1:
        return None
    return time(start_h, m1), time(end_h, m2)


def _days(text: str) -> tuple[list[int], list[tuple[int, int]]]:
    days: set[int] = set()
    spans = []
    for m in re.finditer(r"[A-Za-z]+", text):
        tok = m.group(0)
        low = tok.lower()
        plural = low[:-1] if low.endswith("s") and low[:-1] in _DAY_WORDS else low
        if plural in _DAY_WORDS:
            days.add(_DAY_WORDS[plural])
        elif low in _DAY_GROUPS:
            days.update(_DAY_GROUPS[low])
        elif (tok[0].isupper() and _COMPACT.fullmatch(tok) and (len(tok) >= 2 or tok in "MWRF")
              and tok not in ("Sa", "Su", "S", "U")):
            for code in re.findall(r"Th|Tu|Sa|Su|M|T|W|R|F|S|U", tok):
                days.add(_COMPACT_CODES[code])
        else:
            continue
        spans.append(m.span())
    if re.search(r"\bevery ?day\b", text, re.IGNORECASE):
        days.update(range(7))
    return sorted(days), spans


def _date_from(m: re.Match, today: date) -> date:
    g = m.groupdict()
    if g.get("rel"):
        return today + timedelta(days=0 if g["rel"].lower() in ("today", "tonight") else 1)
    if g.get("wd"):
        target = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"].index(g["wd"].lower())
        ahead = (target - today.weekday()) % 7
        if "next" in m.group(0).lower() and ahead == 0:
            ahead = 7
        return today + timedelta(days=ahead)
    if g.get("mon"):
        month, day = _MONTHS.index(g["mon"].lower()[:3]) + 1, int(g["md"])
    else:
        month, day = int(g["sm"]), int(g["sd"])
    try:
        d = date(today.year, month, day)
    except ValueError:
        return today + timedelta(days=DEFAULT_DUE_DAYS)
    return d if d >= today else date(today.year + 1, month, day)


def _duration(text: str) -> tuple[int | None, tuple[int, int] | None]:
    m = _DUR.search(text)
    if not m:
        return None, None
    if m.group("h"):
        minutes = round(float(m.group("h")) * 60) + int(m.group("hm") or 0)
    elif m.group("m"):
        minutes = int(m.group("m"))
    elif m.group("half"):
        minutes = 30
    else:
        minutes = 60
    return (minutes if 5 <= minutes <= 24 * 60 else None), m.span()


def guess_task_type(text: str) -> TaskType:
    for task_type, pattern in _TYPE_WORDS:
        if re.search(pattern, text, re.IGNORECASE):
            return task_type
    return TaskType.REVIEW


def parse_message(text: str, today: date, new_id: Callable[[str], str]) -> Parsed:
    """Read one chat message. `new_id(prefix)` mints ids for new items."""
    raw = " ".join(text.strip().split())
    low = raw.lower().rstrip("!. ")
    for name, pattern in _COMMANDS:
        m = re.match(pattern, low, re.IGNORECASE)
        if m and not (name in ("plan", "done") and _RANGE.search(raw)):
            return Parsed("command", command=name, arg=(m.groupdict().get("arg") or "").strip())

    rng = next((r for r in _RANGE.finditer(raw) if _resolve_range(r)), None)
    if rng:
        start, end = _resolve_range(rng)
        days, day_spans = _days(raw[:rng.start()] + " " * (rng.end() - rng.start()) + raw[rng.end():])
        spans = [rng.span(), *day_spans]
        on = None
        if not days:
            dm = _ON_DATE.search(raw)
            if dm:
                on, spans = _date_from(dm, today), [*spans, dm.span()]
        is_class = bool(_CLASS_WORDS.search(raw)) or (bool(days) and not _BUSY_WORDS.search(raw))
        title = _clean_title(raw, spans, is_class) or ("Class" if is_class else "Busy")
        if not days and on is None:
            return Parsed("needs_days", arg=title)
        kind = "class" if is_class else "other"
        return Parsed("commitment", commitment=Commitment(
            new_id("class" if kind == "class" else "busy"), title, start, end, days, on, kind))

    assumed, spans = [], []
    due_m = _DUE.search(raw) or _ON_DATE.search(raw)
    if due_m:
        due = _date_from(due_m, today)
        spans.append(due_m.span())
    else:
        due = today + timedelta(days=DEFAULT_DUE_DAYS)
        assumed.append(f"due {due:%a %b} {due.day}")
    minutes, dspan = _duration(raw)
    if dspan:
        spans.append(dspan)
    if minutes is None:
        minutes = DEFAULT_TASK_MINUTES
        assumed.append("about 1 hour")
    title = _clean_title(raw, spans, is_class=False)
    if not title or len(title) < 2:
        return Parsed("unknown")
    task_type = guess_task_type(raw)
    return Parsed("task", task=TodoTask(new_id("task"), title, task_type.value, minutes, due),
                  assumed=assumed)


# -- scheduling -------------------------------------------------------------------


@dataclass
class Placement:
    task_id: str
    title: str
    task_type: str
    start: datetime
    end: datetime
    energy: float
    fits: bool  # the planner would recommend this task type at this energy


def _chunks(minutes: int, task_type: str) -> list[int]:
    size = MAX_CHUNK.get(task_type, 60)
    if minutes <= size:
        return [minutes]
    n = -(-minutes // size)
    base = minutes // n
    out = [base] * n
    out[-1] += minutes - base * n
    if out[-1] < MIN_CHUNK and len(out) > 1:
        out[-2] += out.pop()
    return out


def _free(busy: list[tuple[datetime, datetime]], start: datetime, end: datetime) -> bool:
    return all(end + GAP <= b0 or start >= b1 + GAP for b0, b1 in busy)


def plan_sessions(
    tasks: list[TodoTask],
    busy: list[tuple[datetime, datetime]],
    now: datetime,
    day_start: time,
    energy_at: Callable[[time], float],
    fit_score: Callable[[float, str], float],
    fits: Callable[[float, str], bool],
    already_done: dict[str, int] | None = None,
) -> tuple[list[Placement], dict[str, int]]:
    """Place each task's remaining minutes into free time before its due date.

    `busy` is every fixed block (classes, meetings, sessions to keep).
    `energy_at(clock_time)` is the user model's typical-day energy at that
    time; `fit_score(energy, task_type)` (0..1) is how well that task type
    suits that energy, and `fits(energy, task_type)` whether the domain model
    would recommend it there (shown to the student). Returns the placements
    and, per task id, the minutes that didn't fit before the due date.
    """
    already_done = already_done or {}
    busy = sorted(busy)
    placed: list[Placement] = []
    unplaced: dict[str, int] = {}
    tz = now.tzinfo
    first = now + timedelta(minutes=(-now.minute) % GRID)
    first = first.replace(second=0, microsecond=0)
    energy_cache: dict[time, float] = {}

    def energy(t: time) -> float:
        if t not in energy_cache:
            energy_cache[t] = energy_at(t)
        return energy_cache[t]

    day_minutes: dict[date, int] = {}
    order = sorted(tasks, key=lambda t: (t.due, -t.minutes))
    for task in order:
        remaining = max(0, task.minutes - already_done.get(task.task_id, 0))
        last_day = min(task.due, now.date() + timedelta(days=HORIZON_DAYS))
        task_days: set[date] = set()
        for chunk in _chunks(remaining, task.task_type) if remaining else []:
            best, best_score = None, -1e9
            d = now.date()
            while d <= last_day:
                start = datetime.combine(d, day_start, tzinfo=tz)
                stop = datetime.combine(d, DAY_END, tzinfo=tz)
                if d == now.date():
                    start = max(start, first)
                cursor = start
                while cursor + timedelta(minutes=chunk) <= stop:
                    end = cursor + timedelta(minutes=chunk)
                    if _free(busy, cursor, end):
                        level = energy(cursor.time())
                        score = fit_score(level, task.task_type)
                        score -= 0.35 if d in task_days else 0  # spread a task over days
                        score -= 0.25 * day_minutes.get(d, 0) / 240  # don't pile up one day
                        score -= 0.015 * (d - now.date()).days  # slight pull toward earlier
                        late = cursor.hour + cursor.minute / 60 - LATE_HOUR
                        if late > 0:
                            score -= 0.08 * late  # nights are for winding down
                        if d == task.due:
                            score -= 0.1  # leave the due day as a buffer when possible
                        if score > best_score:
                            best, best_score = (cursor, end, level), score
                    cursor += timedelta(minutes=GRID)
                d += timedelta(days=1)
            if best is None:
                unplaced[task.task_id] = unplaced.get(task.task_id, 0) + chunk
                continue
            s, e, level = best
            busy.append((s, e))
            busy.sort()
            task_days.add(s.date())
            day_minutes[s.date()] = day_minutes.get(s.date(), 0) + chunk
            placed.append(Placement(task.task_id, task.title, task.task_type, s, e, level,
                                    fits(level, task.task_type)))
    placed.sort(key=lambda p: p.start)
    return placed, unplaced


# -- words --------------------------------------------------------------------------


def fmt_minutes(minutes: int) -> str:
    h, m = divmod(int(minutes), 60)
    if h and m:
        return f"{h}h {m}m"
    return f"{h}h" if h else f"{m} min"


def type_label(task_type: str) -> str:
    return TaskType(task_type).label


GREETING = (
    "Hi! I'll build your week with you. **First, your classes**: send them one per message, "
    "like `CSCE 634 MWF 10:20-11:10` or `Distributed Systems Tue Thu 2:20pm-3:35pm`. "
    "Other fixed things work too (`work Sat 9-1`, `busy Friday 6-9pm`). "
    "Say **done** when that's everything."
)
TASKS_PROMPT = (
    "**Now, what do you need to get done?** One per message, with roughly how long and when it's due, "
    "like `IUI final report due Dec 3, 4 hours` or `read chapter 8 by Thursday 1h`. "
    "When the list is complete, say **plan my week**."
)
HELP = (
    "Things I understand:\n"
    "- a class: `CSCE 634 MWF 10:20-11:10`, `Bio lab Thursday 2-5pm`\n"
    "- a one-off busy block: `dentist tomorrow 3-4pm`\n"
    "- a task: `stats homework due Friday 2h`, `flashcards 30 min by Wed`\n"
    "- **plan my week** to arrange everything, **show** to see your list\n"
    "- **remove** _name_, **clear tasks**, **clear classes**, **start over**"
)
