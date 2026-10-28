"""Per-student energy-to-task mapping (Q4). Owner: Vyshnavi.

Design intent (see docs/design-decisions.md): a per-student weighted
rule/lookup table, blending the cold-start survey default with learned
choices, decaying the survey's weight as real sessions accumulate. Must
stay explainable in one sentence -- no black box.

How the blend works, per energy bucket ("low" / "medium" / "high"):

- The *prior* is the student's onboarding-survey answer for that bucket,
  or the fixed default rule (Q2: hard tasks at high energy) if they skipped it.
- The *learned* part is how often the student actually picked each task
  type at that energy (accepted/edited replans, via `record_choice`).
- score(type) = (1 - learned_weight) * [type is the prior]
              + learned_weight * (share of choices in this bucket that were type)
- `learned_weight` starts at 0 and grows as n / (n + PRIOR_STRENGTH) with
  n recorded choices (PTIME-style), so the survey/default fades out. With
  PRIOR_STRENGTH = 5, five real choices make learned data and the prior
  count equally, matching user_model's COLD_START_MIN_CHECKINS.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from .taxonomy import Task, TaskType

# Bucket cut points. negotiation.replanning mirrors these (LOW_ENERGY /
# HIGH_ENERGY), so change both together.
LOW_ENERGY = 0.33
HIGH_ENERGY = 0.66

BUCKETS = ("low", "medium", "high")

# How many real choices it takes before learned data counts as much as the
# survey/default prior.
PRIOR_STRENGTH = 5

# Cold-start default rule (Q2 fallback): hard tasks at high energy.
_DEFAULT_RULE: dict[str, TaskType] = {
    "high": TaskType.PROBLEM_SET,
    "medium": TaskType.REVIEW,
    "low": TaskType.READING,
}

_BUCKET_PHRASE: dict[str, str] = {
    "high": "you're energized",
    "medium": "your energy is moderate",
    "low": "you're tired",
}


def _bucket(energy_level: float) -> str:
    if isinstance(energy_level, bool) or not isinstance(energy_level, (int, float)):
        raise TypeError(f"energy_level must be a float in [0, 1], got {energy_level!r}")
    if not math.isfinite(energy_level) or not 0.0 <= energy_level <= 1.0:
        raise ValueError(f"energy_level must be in [0, 1], got {energy_level!r}")
    if energy_level >= HIGH_ENERGY:
        return "high"
    if energy_level >= LOW_ENERGY:
        return "medium"
    return "low"


def _check_bucket(bucket: str) -> None:
    if bucket not in BUCKETS:
        raise ValueError(f"unknown energy bucket {bucket!r}; expected one of {BUCKETS}")


@dataclass
class StudentTaskMapping:
    """Per-student learned preference, with a decaying blend against the
    survey answers / cold-start default rule.

    - `learned_weight`: 0.0 = pure prior (survey/default), 1.0 = pure learned.
      Updated by `record_choice`; shown to the student via `blend_summary()`.
    - `preferences`: bucket -> the task type the student has most often
      actually chosen at that energy level (their learned favourite).

    Survey answers and per-bucket choice counts are kept as plain attributes
    (not dataclass fields) so the frozen contract's field list is unchanged.
    """

    student_id: str
    learned_weight: float = 0.0  # 0.0 = pure default rule, 1.0 = pure learned
    preferences: dict[str, TaskType] = field(default_factory=dict)  # bucket -> TaskType

    def __post_init__(self) -> None:
        if not 0.0 <= self.learned_weight <= 1.0:
            raise ValueError(f"learned_weight must be in [0, 1], got {self.learned_weight!r}")
        for bucket in self.preferences:
            _check_bucket(bucket)
        self.preferences = {b: TaskType(t) for b, t in self.preferences.items()}
        self._survey: dict[str, TaskType] = {}
        # A preference passed in without history counts as one observed choice.
        self._counts: dict[str, Counter[TaskType]] = {
            b: Counter({self.preferences[b]: 1} if b in self.preferences else {})
            for b in BUCKETS
        }

    @classmethod
    def from_survey(
        cls, student_id: str, answers: dict[str, TaskType | str]
    ) -> StudentTaskMapping:
        """New mapping seeded with onboarding-survey answers (Q2).

        `answers` maps an energy bucket ("low" / "medium" / "high") to the
        task type the student says they prefer at that energy, e.g.
        {"low": "problem_set"} for a student who likes objective tasks when
        tired. Buckets left out fall back to the default rule.
        """
        mapping = cls(student_id=student_id)
        mapping.set_survey_answers(answers)
        return mapping

    def set_survey_answers(self, answers: dict[str, TaskType | str]) -> None:
        """Set (or replace) the survey answers used as this student's prior."""
        survey = {}
        for bucket, task_type in answers.items():
            _check_bucket(bucket)
            survey[bucket] = TaskType(task_type)
        self._survey = survey

    def prior(self, bucket: str) -> tuple[TaskType, str]:
        """(prior task type, "survey" | "default") for one energy bucket."""
        _check_bucket(bucket)
        if bucket in self._survey:
            return self._survey[bucket], "survey"
        return _DEFAULT_RULE[bucket], "default"

    def record_choice(self, energy_level: float, chosen_type: TaskType) -> None:
        """Record a student's accept/edit from Negotiation as a labeled example.

        Bumps the count for (energy bucket, task type), refreshes that
        bucket's learned favourite in `preferences`, and moves
        `learned_weight` one step along n / (n + PRIOR_STRENGTH).
        """
        bucket = _bucket(energy_level)
        chosen = TaskType(chosen_type)
        counts = self._counts[bucket]
        counts[chosen] += 1

        top = max(counts.values())
        leaders = [t for t, c in counts.items() if c == top]
        current = self.preferences.get(bucket)
        if chosen in leaders:
            self.preferences[bucket] = chosen  # ties go to the most recent choice
        elif current not in leaders:
            self.preferences[bucket] = leaders[0]

        # Recover n from the current weight so the update also works for a
        # mapping restored from just its fields.
        w = self.learned_weight
        n = PRIOR_STRENGTH * w / (1.0 - w) if w < 1.0 else math.inf
        self.learned_weight = (n + 1) / (n + 1 + PRIOR_STRENGTH) if w < 1.0 else 1.0

    def choice_counts(self, bucket: str) -> dict[TaskType, int]:
        """How many times the student picked each task type in this bucket."""
        _check_bucket(bucket)
        return dict(self._counts[bucket])

    def scores(self, energy_level: float) -> dict[TaskType, float]:
        """Blended score for every task type at this energy (higher = better fit)."""
        bucket = _bucket(energy_level)
        prior, _ = self.prior(bucket)
        w = self.learned_weight
        counts = self._counts[bucket]
        total = sum(counts.values())
        result = {}
        for task_type in TaskType:
            score = (1.0 - w) * (task_type == prior)
            if total:
                score += w * counts[task_type] / total
            result[task_type] = score
        return result

    def blend_summary(self) -> str:
        """One sentence making the survey -> learned shift visible to the student (Q4)."""
        learned = round(self.learned_weight * 100)
        source = "survey answers" if self._survey else "starting defaults"
        if learned == 0:
            return f"Your recommendations are based on your {source} until you've made some choices."
        return (
            f"Your recommendations are now {learned}% based on your own choices "
            f"and {100 - learned}% on your {source}."
        )


def recommend_task_type(
    mapping: StudentTaskMapping, energy_level: float
) -> tuple[TaskType, str]:
    """Return (recommended TaskType, one-sentence explanation).

    Picks the task type with the highest blended score for this energy
    bucket (see the module docstring). A tie goes to the student's own
    learned favourite over the prior.
    """
    bucket = _bucket(energy_level)
    scores = mapping.scores(energy_level)
    prior, source = mapping.prior(bucket)
    learned = mapping.preferences.get(bucket)

    best = max(scores.values())
    if learned is not None and scores[learned] == best:
        task_type = learned
    elif scores[prior] == best:
        task_type = prior
    else:
        task_type = max(scores, key=scores.__getitem__)

    return task_type, _explain(mapping, bucket, task_type, prior, source, learned)


def _explain(
    mapping: StudentTaskMapping,
    bucket: str,
    task_type: TaskType,
    prior: TaskType,
    source: str,
    learned: TaskType | None,
) -> str:
    phrase = _BUCKET_PHRASE[bucket]
    counts = mapping.choice_counts(bucket)
    total = sum(counts.values())
    picked = counts.get(task_type, 0)

    if task_type == learned and task_type == prior and picked:
        return f"because you usually pick {task_type.label} when {phrase}"
    if task_type == learned and picked:
        override = "your survey answer" if source == "survey" else "the starting default"
        return (
            f"because you picked {task_type.label} in {picked} of your {total} choices "
            f"when {phrase}, which now outweighs {override}"
        )
    if source == "survey":
        reason = f"because you said you prefer {task_type.label} when {phrase}"
    else:
        reason = (
            f"because {task_type.label} is the starting default when {phrase}, "
            f"until I learn what you prefer"
        )
    if learned is not None and learned != task_type:
        so_far = "your 1 choice so far isn't" if total == 1 else f"your {total} choices so far aren't"
        reason += f" ({so_far} enough to change that yet)"
    return reason


def recommend_task(
    mapping: StudentTaskMapping, energy_level: float, tasks: list[Task]
) -> tuple[Task | None, str]:
    """Pick a concrete task from `tasks` for this energy, with a one-sentence why.

    Prefers tasks of the recommended type; among those, the one whose
    effective difficulty (1-5) is closest to what this energy can handle.
    If there are none of that type, falls back to the next-best type by
    blended score. Returns (None, explanation) when `tasks` is empty.
    """
    if not tasks:
        _bucket(energy_level)  # still validate the input
        return None, "because there are no tasks left to schedule"

    task_type, why = recommend_task_type(mapping, energy_level)
    target = 1 + 4 * energy_level  # 0.0 -> difficulty 1, 1.0 -> difficulty 5
    scores = mapping.scores(energy_level)

    def fit(task: Task) -> tuple[float, float]:
        return (-scores[task.task_type], abs(task.effective_difficulty() - target))

    best = min(tasks, key=fit)  # min() keeps list order on ties
    if best.task_type == task_type:
        return best, why
    return best, (
        f"because you have no {task_type.label} tasks left, and {best.title!r} "
        f"is the next best fit for your energy"
    )
