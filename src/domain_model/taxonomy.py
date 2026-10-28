"""Fixed task taxonomy (Q3). Owner: Vyshnavi.

Small, fixed set of task types so energy->task matching stays tractable.
Extend the enum deliberately -- the whole point of Q3 was to keep this
small.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskType(str, Enum):
    PROBLEM_SET = "problem_set"
    READING = "reading"
    REVIEW = "review"
    MEMORIZATION = "memorization"

    @property
    def label(self) -> str:
        """Human-readable name for explanations ("problem sets", "reading", ...)."""
        return _LABELS[self]


_LABELS: dict[TaskType, str] = {
    TaskType.PROBLEM_SET: "problem sets",
    TaskType.READING: "reading",
    TaskType.REVIEW: "review",
    TaskType.MEMORIZATION: "memorization",
}

# Difficulty scale: 1 (very easy) .. 5 (very hard).
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5

# Default difficulty per type, used until the student overrides it on a task.
# Problem sets need the most active effort, reading the least; review and
# memorization sit in between.
DEFAULT_DIFFICULTY: dict[TaskType, int] = {
    TaskType.PROBLEM_SET: 4,
    TaskType.READING: 2,
    TaskType.REVIEW: 3,
    TaskType.MEMORIZATION: 3,
}


@dataclass
class Task:
    """A single study task a student needs to schedule.

    `task_type` also accepts the plain string value (e.g. "reading"), since
    schedule events and replan payloads carry task types as strings.
    `difficulty` is the student's override; None means "use the default for
    this type".
    """

    task_id: str
    title: str
    task_type: TaskType
    difficulty: int | None = None  # None -> fall back to DEFAULT_DIFFICULTY

    def __post_init__(self) -> None:
        self.task_type = TaskType(self.task_type)
        if self.difficulty is not None:
            _check_difficulty(self.difficulty)

    def effective_difficulty(self) -> int:
        return (
            self.difficulty
            if self.difficulty is not None
            else DEFAULT_DIFFICULTY[self.task_type]
        )

    def set_difficulty(self, difficulty: int | None) -> None:
        """Student override of this task's difficulty (None resets to the default)."""
        if difficulty is not None:
            _check_difficulty(difficulty)
        self.difficulty = difficulty


def _check_difficulty(difficulty: int) -> None:
    if isinstance(difficulty, bool) or not isinstance(difficulty, int):
        raise TypeError(f"difficulty must be an int, got {difficulty!r}")
    if not MIN_DIFFICULTY <= difficulty <= MAX_DIFFICULTY:
        raise ValueError(
            f"difficulty must be between {MIN_DIFFICULTY} and {MAX_DIFFICULTY}, "
            f"got {difficulty}"
        )
