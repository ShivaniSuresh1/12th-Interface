"""Negotiated replanning (Q5). Owner: Soumyadip.

Design intent: never silently reschedule. Propose + narrate, let the
student accept or edit with one tap. The resolution is a labeled example
that should feed back into domain_model.StudentTaskMapping.

`trigger` is free-form; recognized values (case/space/hyphen-insensitive):

    fatigue | tired | low_energy
    meeting_ran_late | running_late | late   -- optional ":<minutes>" suffix,
                                                e.g. "meeting_ran_late:20"
    missed_session | missed

Anything else, or a situation where we can't pick a change with
confidence, gets the "not sure -- want to just tell me what changed?"
fallback (action "ask") instead of a guess.

`proposed_change` shape (opaque to other modules, but stable within ours):

    {
        "action": "move" | "shorten" | "defer" | "ask",
        "confidence": float,              # 0.0..1.0
        "energy_level": float | None,     # latest known, for training_example()
        # every action except "ask" also has:
        "session_id": str | None,
        "title": str | None,
        "task_type": str | None,          # domain_model TaskType value, if known
        "original_start": ISO str, "original_end": ISO str,
        "new_start": ISO str, "new_end": ISO str,
    }
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from ._schedule import Event, align, parse_events

# Same cut points as domain_model's energy buckets, so "low" means the same
# thing on both sides.
LOW_ENERGY = 0.33
HIGH_ENERGY = 0.66
VERY_LOW_ENERGY = 0.2

CONFIDENCE_THRESHOLD = 0.5  # below this, ask instead of proposing
SHORT_SESSION = timedelta(minutes=25)  # one Pomodoro
MIN_USEFUL_SESSION = timedelta(minutes=15)  # shorter than this -> defer instead
FATIGUE_BREAK = timedelta(minutes=10)
DEFAULT_DELAY = timedelta(minutes=15)
DAY_END = time(22, 0)  # don't propose study slots past this

ASK_PROMPT = "Want to just tell me what changed?"
RESPONSE_HINT = "Sound good? (accept / edit / skip)"

_TRIGGERS = {
    "fatigue": "fatigue",
    "tired": "fatigue",
    "low_energy": "fatigue",
    "meeting_ran_late": "running_late",
    "running_late": "running_late",
    "late": "running_late",
    "missed_session": "missed_session",
    "missed": "missed_session",
}

_RESPONSES = {
    "accepted": {"accept", "accepted", "yes", "y", "ok", "okay", "sure", "sounds good", "👍"},
    "edited": {"edit", "edited", "change", "modify", "adjust"},
    "rejected": {"reject", "rejected", "no", "n", "nope", "skip", "keep", "👎"},
}


@dataclass
class ReplanProposal:
    student_id: str
    trigger: str  # e.g. "fatigue", "meeting_ran_late", "missed_session"
    message: str  # narrated, batched with any check-in (Q6)
    proposed_change: dict  # see module docstring for the shape


@dataclass
class ReplanResolution:
    proposal: ReplanProposal
    outcome: str  # "accepted" | "edited" | "rejected"
    edited_change: dict | None = None


def _now(reference: datetime | None = None) -> datetime:
    """Current time, naive or aware to match `reference`. Patched in tests."""
    if reference is not None and reference.tzinfo is not None:
        return datetime.now(reference.tzinfo)
    return datetime.now()


def _parse_trigger(trigger: str) -> tuple[str | None, timedelta | None]:
    name, _, minutes = trigger.strip().lower().partition(":")
    key = name.strip().replace("-", "_").replace(" ", "_")
    delay = None
    if minutes.strip().isdigit():
        delay = timedelta(minutes=int(minutes.strip()))
    return _TRIGGERS.get(key), delay


def _latest_energy(profile: object) -> float | None:
    history = getattr(profile, "energy_history", None) or []
    if not history:
        return None
    level = getattr(history[-1], "energy_level", None)
    if isinstance(level, (int, float)) and 0.0 <= level <= 1.0:
        return float(level)
    return None


def _events(profile: object) -> list[Event]:
    return parse_events(getattr(profile, "schedule", None))


def _fmt(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _session_change(
    event: Event,
    action: str,
    new_start: datetime,
    new_end: datetime,
    confidence: float,
    energy: float | None,
) -> dict:
    return {
        "action": action,
        "confidence": confidence,
        "energy_level": energy,
        "session_id": event.session_id,
        "title": event.title,
        "task_type": event.task_type,
        "original_start": event.start.isoformat(),
        "original_end": event.end.isoformat(),
        "new_start": new_start.isoformat(),
        "new_end": new_end.isoformat(),
    }


def _ask(student_id: str, trigger: str, lead: str, energy: float | None, confidence: float):
    return ReplanProposal(
        student_id=student_id,
        trigger=trigger,
        message=f"{lead} {ASK_PROMPT}",
        proposed_change={"action": "ask", "confidence": confidence, "energy_level": energy},
    )


def _current_or_next_session(events: list[Event], now: datetime) -> Event | None:
    """The study session in progress, else the next one today."""
    for event in events:
        if not event.is_study:
            continue
        local_now = align(now, event.end)
        if event.end > local_now and event.start.date() == local_now.date():
            return event
    return None


def _last_missed_session(events: list[Event], now: datetime) -> Event | None:
    missed = [e for e in events if e.is_study and e.start <= align(now, e.start)]
    return missed[-1] if missed else None


def _free_slot(
    events: list[Event], after: datetime, length: timedelta, skip: Event | None = None
) -> datetime | None:
    """Earliest start >= `after` today where `length` fits between events
    (ignoring `skip`, the session being rescheduled) and ends by DAY_END.
    None if nothing fits."""
    day_end = datetime.combine(after.date(), DAY_END, tzinfo=after.tzinfo)
    candidate = after
    for event in events:
        if event is skip or event.end <= candidate or event.start.date() != after.date():
            continue
        if event.start - candidate >= length:
            break
        candidate = max(candidate, event.end)
    if candidate + length <= day_end:
        return candidate
    return None


def _next_event_start(events: list[Event], skip: Event, after: datetime) -> datetime | None:
    for event in events:
        if event is not skip and event.start >= after:
            return event.start
    return None


def _propose_fatigue(student_id, trigger, events, energy, now) -> ReplanProposal:
    target = _current_or_next_session(events, now)
    if target is None:
        return _ask(
            student_id,
            trigger,
            "Sorry you're worn out -- I don't see a session left today to adjust.",
            energy,
            0.2,
        )

    if energy is not None and energy >= HIGH_ENERGY:
        # Q1: the two signals disagree. Don't guess which one is right.
        return _ask(
            student_id,
            trigger,
            "Your energy estimate looked good, but you're telling me you're tired, "
            f'so I\'m not sure how to change "{target.label}".',
            energy,
            0.3,
        )

    # No estimate yet: the trigger itself says tired, so treat it as low,
    # just with a bit less confidence.
    confidence = 0.8 if energy is not None else 0.6
    local_now = align(now, target.start)
    start = max(target.start, local_now)
    remaining = target.end - start

    very_low = energy is not None and energy < VERY_LOW_ENERGY
    low = energy is None or energy < LOW_ENERGY
    if very_low or (low and remaining <= SHORT_SESSION):
        later = _free_slot(events, target.end + FATIGUE_BREAK * 3, remaining, skip=target)
        if later is None:
            tomorrow = target.start + timedelta(days=1)
            change = _session_change(
                target, "defer", tomorrow, tomorrow + remaining, confidence, energy
            )
            when = f"to tomorrow at {_fmt(tomorrow)}"
        else:
            change = _session_change(target, "defer", later, later + remaining, confidence, energy)
            when = f"to {_fmt(later)} after you've rested"
        message = (
            f'Your energy is running really low, so I\'d push "{target.label}" {when}. '
            f"{RESPONSE_HINT}"
        )
    elif low:
        new_end = start + SHORT_SESSION
        change = _session_change(target, "shorten", start, new_end, confidence, energy)
        message = (
            f"Since you're feeling tired, I'd cut \"{target.label}\" down to a 25-minute "
            f"session ending at {_fmt(new_end)}, because a short focused block beats "
            f"pushing through exhausted. {RESPONSE_HINT}"
        )
    else:
        new_start = start + FATIGUE_BREAK
        new_end = new_start + remaining
        change = _session_change(target, "move", new_start, new_end, confidence, energy)
        message = (
            f"You're a bit low, so I'd take a 10-minute break first and start "
            f'"{target.label}" at {_fmt(new_start)} instead. {RESPONSE_HINT}'
        )
    return ReplanProposal(student_id, trigger, message, change)


def _propose_running_late(student_id, trigger, events, energy, now, delay) -> ReplanProposal:
    target = _current_or_next_session(events, now)
    if target is None:
        return _ask(
            student_id,
            trigger,
            "Looks like something ran late, but I don't see a session to shift.",
            energy,
            0.2,
        )

    confidence = 0.85 if delay is not None else 0.6
    delay = delay or DEFAULT_DELAY
    late_by = f"{int(delay.total_seconds() // 60)} minutes"
    new_start = target.start + delay
    new_end = target.end + delay

    blocker = _next_event_start(events, target, target.end)
    if blocker is not None and new_end > blocker:
        new_end = blocker
        if new_end - new_start < MIN_USEFUL_SESSION:
            later = _free_slot(events, blocker, target.end - target.start, skip=target)
            if later is None:
                return _ask(
                    student_id,
                    trigger,
                    f'Running {late_by} late leaves no room for "{target.label}" today, '
                    "and I couldn't find another slot.",
                    energy,
                    0.3,
                )
            length = target.end - target.start
            change = _session_change(target, "defer", later, later + length, confidence, energy)
            message = (
                f'Since things ran {late_by} late, there\'s no room for "{target.label}" '
                f"before your next commitment, so I'd move it to {_fmt(later)}. {RESPONSE_HINT}"
            )
            return ReplanProposal(student_id, trigger, message, change)

        change = _session_change(target, "shorten", new_start, new_end, confidence, energy)
        message = (
            f'Since things ran {late_by} late, I\'d start "{target.label}" at '
            f"{_fmt(new_start)} and end it at {_fmt(new_end)} so it doesn't run into "
            f"what's next. {RESPONSE_HINT}"
        )
        return ReplanProposal(student_id, trigger, message, change)

    change = _session_change(target, "move", new_start, new_end, confidence, energy)
    message = (
        f'Since things ran {late_by} late, I\'d push "{target.label}" from '
        f"{_fmt(target.start)} to {_fmt(new_start)}. {RESPONSE_HINT}"
    )
    return ReplanProposal(student_id, trigger, message, change)


def _propose_missed(student_id, trigger, events, energy, now) -> ReplanProposal:
    target = _last_missed_session(events, now)
    if target is None:
        return _ask(student_id, trigger, "I couldn't tell which session got missed.", energy, 0.2)

    length = target.end - target.start
    local_now = align(now, target.start)
    later = _free_slot(events, local_now, length, skip=target)
    if later is None:
        later = target.start + timedelta(days=1)
        when = f"tomorrow at {_fmt(later)}"
    else:
        when = f"{_fmt(later)} today"
    change = _session_change(target, "defer", later, later + length, 0.75, energy)
    message = (
        f'No worries about missing "{target.label}" -- I\'d make it up at {when}, '
        f"because that's the next open slot that fits it. {RESPONSE_HINT}"
    )
    return ReplanProposal(student_id, trigger, message, change)


def propose_replan(student_profile: object, trigger: str) -> ReplanProposal:
    """Build a narrated replan proposal.

    Reads `student_id`, `schedule` and `energy_history` off the profile if
    present (any StudentProfile-shaped object works). Always returns a
    proposal with a non-empty message; when the right change isn't clear
    the proposal is an "ask" instead of a guess.
    """
    student_id = getattr(student_profile, "student_id", None) or "unknown"
    events = _events(student_profile)
    energy = _latest_energy(student_profile)
    now = _now(events[0].start if events else None)
    kind, delay = _parse_trigger(trigger)

    if kind == "fatigue":
        proposal = _propose_fatigue(student_id, trigger, events, energy, now)
    elif kind == "running_late":
        proposal = _propose_running_late(student_id, trigger, events, energy, now, delay)
    elif kind == "missed_session":
        proposal = _propose_missed(student_id, trigger, events, energy, now)
    else:
        proposal = _ask(
            student_id,
            trigger,
            f"Something changed ({trigger}) and I'm not sure what's best.",
            energy,
            0.0,
        )

    if (
        proposal.proposed_change["action"] != "ask"
        and proposal.proposed_change["confidence"] < CONFIDENCE_THRESHOLD
    ):
        return _ask(
            student_id,
            trigger,
            "I'm not confident about the best change here.",
            energy,
            proposal.proposed_change["confidence"],
        )
    return proposal


def _normalize_response(student_response: str) -> str | None:
    text = (student_response or "").strip().lower()
    for outcome, words in _RESPONSES.items():
        if text in words:
            return outcome
    return None


def resolve_proposal(
    proposal: ReplanProposal, student_response: str, edited_change: dict | None = None
) -> ReplanResolution:
    """Resolve a proposal based on the student's one-tap response.

    Accepts "accept" | "edit" | "reject" plus common synonyms ("yes", "ok",
    "skip", ...). Passing `edited_change` with anything but a rejection
    counts as an edit. An unrecognized response is treated as "rejected":
    we only apply a change the student clearly agreed to.
    """
    outcome = _normalize_response(student_response) or "rejected"
    if edited_change is not None and outcome != "rejected":
        outcome = "edited"
    return ReplanResolution(
        proposal=proposal,
        outcome=outcome,
        edited_change=edited_change if outcome == "edited" else None,
    )


def training_example(resolution: ReplanResolution) -> dict:
    """Turn a resolution into a labeled example for the learned mapping (Q4 x Q5).

    Integration owns the actual call; with this it's just:

        ex = training_example(resolution)
        if ex["chosen_task_type"] and ex["energy_level"] is not None:
            mapping.record_choice(ex["energy_level"], TaskType(ex["chosen_task_type"]))

    `chosen_task_type` is the task type the student ended up with: the
    proposal's on accept, the edited one on edit (if they changed it), and
    None on reject -- a rejection says what they didn't want, not what they did.
    """
    change = resolution.proposal.proposed_change or {}
    chosen = None
    if resolution.outcome == "accepted":
        chosen = change.get("task_type")
    elif resolution.outcome == "edited":
        chosen = (resolution.edited_change or {}).get("task_type") or change.get("task_type")
    return {
        "student_id": resolution.proposal.student_id,
        "trigger": resolution.proposal.trigger,
        "action": change.get("action"),
        "outcome": resolution.outcome,
        "energy_level": change.get("energy_level"),
        "chosen_task_type": chosen,
    }
