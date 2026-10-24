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


# Default difficulty per type (TODO: tune; placeholder scale 1-5).
DEFAULT_DIFFICULTY: dict[TaskType, int] = {
    TaskType.PROBLEM_SET: 4,
    TaskType.READING: 2,
    TaskType.REVIEW: 3,
    TaskType.MEMORIZATION: 3,
}


@dataclass
class Task:
    """A single study task a student needs to schedule."""

    task_id: str
    title: str
    task_type: TaskType
    difficulty: int | None = None  # None -> fall back to DEFAULT_DIFFICULTY

    def effective_difficulty(self) -> int:
        return (
            self.difficulty
            if self.difficulty is not None
            else DEFAULT_DIFFICULTY[self.task_type]
        )
