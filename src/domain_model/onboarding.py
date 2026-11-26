"""Command-line onboarding survey, Domain Model half (Q2 cold start).

Asks a new student which kind of task they prefer at each energy level and
feeds the real answers into `StudentTaskMapping.set_survey_answers()`. The
sleep questions belong to user_model (`user_model.onboarding`) and are not
asked here; integration can run both for one combined onboarding.

    PYTHONPATH=src python -m domain_model.onboarding --student-id s1 --out profiles/s1_tasks.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from .mapping import BUCKETS, StudentTaskMapping, recommend_task_type
from .taxonomy import TaskType

# One question per energy bucket, in the order they're asked.
QUESTIONS: dict[str, str] = {
    "low": "When you're tired, which kind of studying do you prefer?",
    "medium": "When your energy is so-so, which kind of studying do you prefer?",
    "high": "When you're energized, which kind of studying do you prefer?",
}

# Menu order: a number picks the task type at that position.
CHOICES: list[TaskType] = [
    TaskType.PROBLEM_SET,
    TaskType.READING,
    TaskType.REVIEW,
    TaskType.MEMORIZATION,
]

# A representative energy level per bucket, to show the resulting recommendation.
_BUCKET_ENERGY = {"low": 0.2, "medium": 0.5, "high": 0.8}

_SKIP = {"", "skip", "none", "no preference", "no", "-"}
_ALIASES = {
    "problem set": TaskType.PROBLEM_SET,
    "problem sets": TaskType.PROBLEM_SET,
    "problems": TaskType.PROBLEM_SET,
    "flashcards": TaskType.MEMORIZATION,
    "memorize": TaskType.MEMORIZATION,
}


def _menu() -> str:
    options = "  ".join(f"[{i}] {t.label}" for i, t in enumerate(CHOICES, start=1))
    return f"  {options}  (Enter = no preference): "


def parse_task_choice(text: str) -> TaskType | None:
    """Read an answer like "2", "reading", "problem sets" or "flashcards".

    Returns None for no preference (blank, "skip"). Raises ValueError with a
    message that can be shown to the student."""
    answer = " ".join(text.strip().lower().replace("_", " ").split())
    if answer in _SKIP:
        return None
    if answer.isdigit() and 1 <= int(answer) <= len(CHOICES):
        return CHOICES[int(answer) - 1]
    for task_type in CHOICES:
        if answer in (task_type.value.replace("_", " "), task_type.label):
            return task_type
    if answer in _ALIASES:
        return _ALIASES[answer]
    raise ValueError(f"Please type a number from 1 to {len(CHOICES)}, or press Enter to skip.")


def run_onboarding(
    mapping: StudentTaskMapping,
    ask: Callable[[str], str] | None = None,
    say: Callable[..., None] | None = None,
) -> dict[str, TaskType]:
    """Ask the task-preference questions, re-asking on invalid answers, and
    apply them to `mapping` as its survey answers. Skipped buckets keep the
    default rule. `ask`/`say` default to the terminal; tests pass their own.
    Returns the answers given. EOFError/KeyboardInterrupt from `ask` propagate."""
    ask = ask if ask is not None else input
    say = say if say is not None else print
    say("A few quick questions about what you like to study at different energy")
    say("levels, so the planner's first suggestions fit you.\n")
    answers: dict[str, TaskType] = {}
    for bucket in BUCKETS:
        say(QUESTIONS[bucket])
        while True:
            try:
                choice = parse_task_choice(ask(_menu()))
                break
            except ValueError as e:
                say(str(e))
        if choice is not None:
            answers[bucket] = choice
    mapping.set_survey_answers(answers)
    say("\nThanks! Here's what I'll suggest to start with:")
    for line in recommendation_summary(mapping):
        say(f"  - {line}")
    return answers


def recommendation_summary(mapping: StudentTaskMapping) -> list[str]:
    """One line per energy level: the recommendation and its "because ..."."""
    lines = []
    for bucket in BUCKETS:
        task_type, why = recommend_task_type(mapping, _BUCKET_ENERGY[bucket])
        lines.append(f"{bucket} energy: {task_type.label}, {why}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m domain_model.onboarding",
        description="Onboarding survey (task preferences) for a new student.",
    )
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--out", type=Path, help="save the task mapping as JSON to this file")
    args = parser.parse_args(argv)

    if args.out is not None and args.out.exists():
        print(f"{args.out} already exists; not overwriting it.", file=sys.stderr)
        return 1

    mapping = StudentTaskMapping(student_id=args.student_id)
    try:
        run_onboarding(mapping)
    except (EOFError, KeyboardInterrupt):
        print("\nOnboarding cancelled; nothing was saved.", file=sys.stderr)
        return 1

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(mapping.to_dict(), indent=2) + "\n", encoding="utf-8")
        print(f"Task preferences saved to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
