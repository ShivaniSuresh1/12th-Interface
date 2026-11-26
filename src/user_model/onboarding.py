"""Command-line onboarding survey, User Model half (Q2 cold start).

Asks a new student the two sleep questions and feeds the real answers into
`apply_sleep_survey()`, instead of a hardcoded profile. The task-preference
questions belong to domain_model (`StudentTaskMapping.from_survey`) and are
not asked here.

    PYTHONPATH=src python -m user_model.onboarding --student-id s1 --out profiles/s1.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from datetime import datetime, time
from pathlib import Path

from .energy_estimate import estimate_baseline_energy
from .models import StudentProfile
from .survey import MAX_SURVEY_SLEEP_HOURS, apply_sleep_survey

SLEEP_QUESTION = "About how many hours do you usually sleep a night? (e.g. 7 or 7.5): "
WAKE_QUESTION = "What time do you usually wake up? (e.g. 7:30, 7:30am or 19:00): "

_HOURS = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:h|hrs?|hours?)?\s*$", re.IGNORECASE)
_CLOCK = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(?:([ap])\.?\s*m\.?)?\s*$", re.IGNORECASE)


def parse_sleep_hours(text: str) -> float:
    """Read a sleep answer like "7", "7.5", "7h" or "8 hours" as hours.

    Raises ValueError with a message that can be shown to the student."""
    m = _HOURS.match(text)
    if m is None:
        raise ValueError("Please enter a number of hours, like 7 or 7.5.")
    hours = float(m.group(1))
    if not 0 <= hours <= MAX_SURVEY_SLEEP_HOURS:
        raise ValueError(f"Please enter a number between 0 and {MAX_SURVEY_SLEEP_HOURS:g}.")
    return hours


def parse_wake_time(text: str) -> time:
    """Read a wake time like "7", "7:30", "7:30am", "7 pm" or "19:00".

    Without am/pm the hour is read as 24-hour. Raises ValueError with a
    message that can be shown to the student."""
    m = _CLOCK.match(text)
    if m is None:
        raise ValueError("Please enter a time like 7:30, 7:30am or 19:00.")
    hour, minute, half = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if half:
        if not 1 <= hour <= 12:
            raise ValueError("With am/pm, the hour must be between 1 and 12.")
        hour = hour % 12 + (12 if half == "p" else 0)
    if hour > 23 or minute > 59:
        raise ValueError("That isn't a valid time of day.")
    return time(hour, minute)


def _ask_until_valid(
    question: str, parse: Callable[[str], object], ask: Callable[[str], str], say: Callable
) -> object:
    while True:
        try:
            return parse(ask(question))
        except ValueError as e:
            say(str(e))


def run_onboarding(
    profile: StudentProfile,
    ask: Callable[[str], str] | None = None,
    say: Callable[..., None] | None = None,
    now: datetime | None = None,
) -> None:
    """Ask the sleep questions, re-asking on invalid answers, and apply them to
    `profile` via `apply_sleep_survey()`. `ask`/`say` default to the terminal;
    tests pass their own. EOFError/KeyboardInterrupt from `ask` propagate."""
    ask = ask if ask is not None else input
    say = say if say is not None else print
    say("A couple of quick questions about your sleep, so the planner can")
    say("estimate your energy before you've done any check-ins.\n")
    hours = _ask_until_valid(SLEEP_QUESTION, parse_sleep_hours, ask, say)
    wake = _ask_until_valid(WAKE_QUESTION, parse_wake_time, ask, say)
    apply_sleep_survey(profile, typical_sleep_hours=hours, typical_wake_time=wake, now=now)
    wake_text = wake.strftime("%I:%M %p").lstrip("0")
    say(f"\nThanks! Saved: about {hours:g} hours of sleep, usually up at {wake_text}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m user_model.onboarding",
        description="Onboarding survey (sleep questions) for a new student.",
    )
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--out", type=Path, help="save the profile as JSON to this file")
    args = parser.parse_args(argv)

    if args.out is not None and args.out.exists():
        print(f"{args.out} already exists; not overwriting it.", file=sys.stderr)
        return 1

    profile = StudentProfile(student_id=args.student_id)
    try:
        run_onboarding(profile)
    except (EOFError, KeyboardInterrupt):
        print("\nOnboarding cancelled; nothing was saved.", file=sys.stderr)
        return 1

    energy = estimate_baseline_energy(profile).energy_level
    print(f"Right now your estimated energy is {energy:.0%}.")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(profile.to_dict(), indent=2) + "\n", encoding="utf-8")
        print(f"Profile saved to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
