"""Exit survey (Phase 1, step 4).

Asked once, after a participant finishes all scenarios. Questions follow
the team's evaluation plan (evaluation-plan.md): the value of the energy
estimate, the check-in, and the "why this task" explanation, plus clarity
and trust, with free text for confusion/mistrust signals.

Saved to eval_logs/participant_NN_survey.csv, one row per question.
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .log import LOG_DIR

SURVEY_FIELDS = ["participant", "question_id", "kind", "question", "answer", "timestamp"]

LIKERT_HINT = "1 = strongly disagree, 7 = strongly agree"


@dataclass(frozen=True)
class Question:
    question_id: str
    kind: str  # "likert" (1-7) | "choice" | "text"
    text: str
    choices: tuple[str, ...] = ()


QUESTIONS: list[Question] = [
    # Clarity of each feature
    Question("energy_clear", "likert", "The energy estimate (the % and the bar) was easy to understand."),
    Question(
        "checkin_sensible",
        "likert",
        "When a scenario included a check-in answer, the energy estimate reflected it in a way "
        "that made sense.",
    ),
    Question(
        "why_helpful",
        "likert",
        'The "Why:" explanations helped me understand why a task was recommended.',
    ),
    Question("change_clear", "likert", "The proposed schedule changes were clear."),
    # Trust
    Question(
        "trust_with_why",
        "likert",
        "I trusted the planner more when it explained its reasoning.",
    ),
    Question("would_use", "likert", "I would use a planner like this for my own studying."),
    # Direct comparison of the two conditions
    Question(
        "preferred_version",
        "choice",
        'Which did you prefer: scenarios that showed the "Why:" explanation, or the ones that '
        "only showed the numbers?",
        ("with explanation", "numbers only", "no preference"),
    ),
    # Free text: confusion / mistrust signals
    Question(
        "confusing",
        "text",
        "Was anything confusing, or hard to trust? (press Enter to skip)",
    ),
    Question("change_one_thing", "text", "If you could change one thing, what would it be? (Enter to skip)"),
]


def survey_path(participant: int, log_dir: Path = LOG_DIR) -> Path:
    return log_dir / f"participant_{participant:02d}_survey.csv"


def _ask(question: Question, input_fn: Callable[[str], str]) -> str:
    if question.kind == "likert":
        prompt = f"{question.text}\n  ({LIKERT_HINT}): "
        while True:
            answer = input_fn(prompt).strip()
            if answer.isdigit() and 1 <= int(answer) <= 7:
                return answer
            print("Please type a whole number from 1 to 7.")
    if question.kind == "choice":
        options = "  ".join(f"[{i}] {c}" for i, c in enumerate(question.choices, start=1))
        prompt = f"{question.text}\n  {options}: "
        while True:
            answer = input_fn(prompt).strip()
            if answer.isdigit() and 1 <= int(answer) <= len(question.choices):
                return question.choices[int(answer) - 1]
            print(f"Please type a number from 1 to {len(question.choices)}.")
    return input_fn(f"{question.text}\n  > ").strip()


def run_survey(
    participant: int,
    input_fn: Callable[[str], str] = input,
    log_dir: Path = LOG_DIR,
) -> dict[str, str]:
    """Ask every question, saving each answer as soon as it's given."""
    path = survey_path(participant, log_dir)
    if path.exists():
        raise FileExistsError(f"{path} already exists. Use a new participant number.")
    path.parent.mkdir(parents=True, exist_ok=True)

    print("\nA few last questions about the whole session.\n")
    answers: dict[str, str] = {}
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SURVEY_FIELDS)
        writer.writeheader()
        for question in QUESTIONS:
            answer = _ask(question, input_fn)
            answers[question.question_id] = answer
            writer.writerow(
                {
                    "participant": participant,
                    "question_id": question.question_id,
                    "kind": question.kind,
                    "question": question.text,
                    "answer": answer,
                    "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                }
            )
            f.flush()
            print()
    return answers
