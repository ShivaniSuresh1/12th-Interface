"""The "tell me what changed" fallback, made interactive (Q5). Owner: Soumyadip.

When propose_replan() isn't confident it returns an "ask" proposal instead
of guessing. This module handles what comes after: the student's free-text
answer is read into a concrete `edited_change` and fed to resolve_proposal(),
and the student is told what will happen. Nothing changes silently, and
nothing changes at all if we couldn't tell what they want.

propose_replan() and its confidence threshold are untouched -- this only
runs after the fallback fires.

Reading the answer is rule-based on purpose (same reason as Q4: it has to be
explainable in one sentence, and work offline). `edited_change` shape:

    {
        "action": "shorten" | "move" | "defer" | "swap" | "note",
        "minutes": int | None,       # shorten: new length; move: delay
        "when": "later" | "tomorrow" | None,   # defer only
        "task_type": str | None,     # a domain_model TaskType value, if named
        "answer": str,               # what the student actually typed
    }

"note" means we kept what they said but found nothing to act on, so the
plan stays as it is.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from .replanning import SHORT_SESSION, ReplanProposal, ReplanResolution, resolve_proposal

ANSWER_PROMPT = "> "

_DEFAULT_SHORT = int(SHORT_SESSION.total_seconds() // 60)

_TIRED = (
    "tired",
    "exhausted",
    "sleepy",
    "worn out",
    "drained",
    "no energy",
    "burnt out",
    "burned out",
    "can't focus",
    "cant focus",
    "can't concentrate",
    "fried",
    "wiped",
    "beat",
)
_LATE = ("late", "ran over", "running behind", "took longer", "delayed", "held up")
_MISSED = ("missed", "skipped", "forgot", "didn't do", "did not do", "couldn't make")
_TOMORROW = ("tomorrow", "not today", "cancel", "skip today")
_LATER = ("later", "postpone", "push it", "move it", "reschedule")
_SHORTER = (
    "shorter",
    "shorten",
    "cut it",
    "less time",
    "only",
    "just",
    "max",
    "at most",
    "tops",
)
# Whole answers that mean "leave it" (matched exactly, so "no energy" isn't one).
_NOTHING = {
    "nothing",
    "never mind",
    "nevermind",
    "nvm",
    "all good",
    "i'm fine",
    "im fine",
    "no",
    "nope",
}

# Checked in order; first match wins, so "problem set" beats "set".
_TASK_TYPES = (
    ("memorization", r"flash ?cards?|memori[sz]\w*|vocab\w*"),
    ("problem_set", r"problem ?sets?|psets?|homework|practice problems"),
    ("review", r"review\w*|revis\w*|go over|notes"),
    ("reading", r"read|reading|textbook|chapter|article"),
)

_TASK_NAMES = {
    "memorization": "memorization",
    "problem_set": "a problem set",
    "review": "review",
    "reading": "reading",
}


def _has(text: str, phrases: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(p)}(?!\w)", text) for p in phrases)


def _minutes(text: str) -> int | None:
    if re.search(r"\bhalf (an )?hour\b", text):
        return 30
    if re.search(r"\b(an|one|1) hour\b", text):
        return 60
    hours = re.search(r"(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hours?)\b", text)
    if hours:
        return round(float(hours.group(1)) * 60)
    mins = re.search(r"(\d+)\s*(?:m|min|mins|minutes?)\b", text)
    if mins:
        return int(mins.group(1))
    return None


def _task_type(text: str) -> str | None:
    for task_type, pattern in _TASK_TYPES:
        if re.search(rf"\b(?:{pattern})\b", text):
            return task_type
    return None


def interpret_answer(answer: str) -> dict | None:
    """Turn the student's free-text answer into an `edited_change`.

    Returns None when there's nothing to act on (empty, or "never mind").
    Explicit requests ("move it to tomorrow", "just 20 minutes") win over
    reasons ("I'm tired"), since the student is telling us what they want.
    """
    raw = (answer or "").strip()
    text = raw.lower().replace("’", "'")
    if not text or re.sub(r"[^\w' ]", "", text).strip() in _NOTHING:
        return None

    minutes = _minutes(text)
    task_type = _task_type(text)
    change = {
        "action": "note",
        "minutes": None,
        "when": None,
        "task_type": task_type,
        "answer": raw,
    }

    if _has(text, _TOMORROW):
        change.update(action="defer", when="tomorrow")
    elif _has(text, _MISSED):
        change.update(action="defer", when="later")
    elif _has(text, _LATE):
        change.update(action="move", minutes=minutes)
    elif _has(text, _LATER) and not (minutes and _has(text, _SHORTER)):
        change.update(action="defer", when="later")
    elif _has(text, _SHORTER) and minutes:
        change.update(action="shorten", minutes=minutes)
    elif _has(text, _TIRED):
        change.update(action="shorten", minutes=minutes or _DEFAULT_SHORT)
    elif task_type:
        change.update(action="swap")
    elif minutes:
        # A bare "20 minutes" is the session length they can manage.
        change.update(action="shorten", minutes=minutes)
    return change


def resolve_answer(proposal: ReplanProposal, answer: str) -> ReplanResolution:
    """Resolve an "ask" proposal from the student's free-text answer.

    Anything we can read becomes an "edited" resolution carrying the
    `edited_change`; an empty answer or "never mind" is "rejected" (the plan
    stays as it is).
    """
    change = interpret_answer(answer)
    if change is None:
        return resolve_proposal(proposal, "reject")
    return resolve_proposal(proposal, "edit", edited_change=change)


def confirmation_message(resolution: ReplanResolution) -> str:
    """Tell the student, in one or two sentences, what happens now."""
    change = resolution.edited_change
    if resolution.outcome != "edited" or not change:
        return "No problem, I'll leave your plan as it is."

    action = change.get("action")
    minutes = change.get("minutes")
    task = _TASK_NAMES.get(change.get("task_type") or "")
    switch = f" and switch to {task}" if task else ""

    if action == "shorten":
        return f"Got it. I'll keep your session to {minutes} minutes{switch}."
    if action == "move":
        if minutes:
            return f"Got it. I'll push your session back {minutes} minutes{switch}."
        return f"Got it. I'll push your session back until you're ready{switch}."
    if action == "defer":
        when = "tomorrow" if change.get("when") == "tomorrow" else "later today"
        return f"Okay, I'll move it to {when}{switch}."
    if action == "swap":
        return f"Got it. I'll switch your session to {task}."
    return (
        f"Thanks, I've noted that (\"{change.get('answer', '')}\"). I wasn't sure what "
        "to change, so I'll leave your plan as it is."
    )


def run_ask_flow(
    proposal: ReplanProposal,
    ask: Callable[[str], str] | None = None,
    say: Callable[..., None] | None = None,
) -> ReplanResolution:
    """Show the question, read the student's answer, resolve, and confirm.

    `ask`/`say` default to input()/print() so this works in a terminal;
    the Streamlit UI or the harness can pass their own. EOFError and
    KeyboardInterrupt from `ask` propagate, so a cancelled flow changes nothing.
    """
    if proposal.proposed_change.get("action") != "ask":
        raise ValueError("run_ask_flow is only for 'ask' proposals; use resolve_proposal")
    ask = ask or input
    say = say or print
    say(proposal.message)
    resolution = resolve_answer(proposal, ask(ANSWER_PROMPT))
    say(confirmation_message(resolution))
    return resolution
