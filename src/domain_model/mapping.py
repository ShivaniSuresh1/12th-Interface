"""Per-student energy-to-task mapping (Q4). Owner: Vyshnavi.

Design intent (see docs/design-decisions.md): a per-student weighted
rule/lookup table, blending the cold-start survey default with learned
choices, decaying the survey's weight as real sessions accumulate. Must
stay explainable in one sentence -- no black box.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .taxonomy import TaskType

# Cold-start default rule (Q2 fallback): hard tasks at high energy.
_DEFAULT_RULE: dict[str, TaskType] = {
    "high": TaskType.PROBLEM_SET,
    "medium": TaskType.REVIEW,
    "low": TaskType.READING,
}


def _bucket(energy_level: float) -> str:
    if energy_level >= 0.66:
        return "high"
    if energy_level >= 0.33:
        return "medium"
    return "low"


@dataclass
class StudentTaskMapping:
    """Per-student learned preference, with a decaying blend against the
    cold-start default rule.

    TODO: replace `learned_weight` / `preferences` placeholders with the
    real decaying-blend implementation (PTIME-style) described in Q4.
    """

    student_id: str
    learned_weight: float = 0.0  # 0.0 = pure default rule, 1.0 = pure learned
    preferences: dict[str, TaskType] = field(default_factory=dict)  # bucket -> TaskType

    def record_choice(self, energy_level: float, chosen_type: TaskType) -> None:
        """Record a student's accept/edit from Negotiation as a labeled example.

        TODO: implement the actual decay schedule for learned_weight and the
        actual learning rule for `preferences`.
        """
        bucket = _bucket(energy_level)
        self.preferences[bucket] = chosen_type
        self.learned_weight = min(1.0, self.learned_weight + 0.05)


def recommend_task_type(
    mapping: StudentTaskMapping, energy_level: float
) -> tuple[TaskType, str]:
    """Return (recommended TaskType, one-sentence explanation).

    TODO: implement the real blend. Currently just falls back to the
    default rule unless a learned preference exists for this bucket.
    """
    bucket = _bucket(energy_level)
    if bucket in mapping.preferences and mapping.learned_weight > 0:
        task_type = mapping.preferences[bucket]
        return task_type, f"because you usually do {task_type.value} when your energy is {bucket}"

    task_type = _DEFAULT_RULE[bucket]
    return task_type, f"because {bucket} energy is matched to {task_type.value} by default"
