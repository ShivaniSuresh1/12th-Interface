"""Record domain_model's real recommendations for the pilot scenarios.

Runs each of Shivani's energy scenarios (tests/user_model/scenarios.py)
through recommend_task_type() for a representative student, sanity-checks
the result, and writes everything to src/domain_model/PILOT_RECOMMENDATIONS.md.
Nothing in that file is written by hand.

Also checks the recommendations the evaluation harness actually shows
participants (integration.evaluation.PILOT_SCENARIOS), since those are
what a pilot participant sees live.

    PYTHONPATH=src python -m tests.domain_model.pilot_recommendations
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from domain_model import StudentTaskMapping, TaskType, recommend_task_type
from domain_model.mapping import HIGH_ENERGY, LOW_ENERGY, _bucket
from integration.evaluation.scenarios import PILOT_SCENARIOS
from integration.evaluation.simulate import build_planner, run_scenario
from tests.user_model.scenarios import SCENARIOS

OUT = Path(__file__).resolve().parents[2] / "src" / "domain_model" / "PILOT_RECOMMENDATIONS.md"

# Sanity-check thresholds.
NEAR_CUT = 0.03  # energy this close to 0.33 / 0.66 flips bucket on a small change
MIN_SCORE_MARGIN = 0.05  # best vs runner-up blended score; below this is a near-tie


# -- representative students ----------------------------------------------------


def new_student() -> StudentTaskMapping:
    """First day: no survey answers, no history -> the default rule."""
    return StudentTaskMapping("pilot_new")


def survey_student() -> StudentTaskMapping:
    """Said in onboarding they'd rather do problem sets when tired (objective
    answers), the design doc's example. (The harness's s2 uses its own survey answer.)"""
    return StudentTaskMapping.from_survey("pilot_survey", {"low": "problem_set"})


def learned_student() -> StudentTaskMapping:
    """A couple of weeks in: 12 recorded accept/edit choices."""
    mapping = StudentTaskMapping("pilot_learned")
    history = (
        [(0.2, TaskType.MEMORIZATION)] * 4  # flashcards when tired
        + [(0.5, TaskType.READING)] * 4
        + [(0.5, TaskType.REVIEW)]
        + [(0.8, TaskType.PROBLEM_SET)] * 3  # agrees with the default
    )
    for energy, chosen in history:
        mapping.record_choice(energy, chosen)
    return mapping


STUDENTS = {"new": new_student, "survey": survey_student, "learned": learned_student}

# Which student each of Shivani's scenarios is paired with for the pilot set.
# Together they cover every explanation source (default rule, survey, learned
# override, learned habit) and all four task types.
REPRESENTATIVE = {1: "new", 2: "survey", 3: "new", 4: "learned", 5: "learned", 6: "learned"}


# -- running + checking ---------------------------------------------------------


@dataclass
class Row:
    label: str  # scenario number / id
    student: str
    energy_level: float
    bucket: str
    task_type: TaskType
    why: str
    source: str  # "default rule" | "survey" | "learned choices"
    margin: float  # best minus runner-up blended score
    issues: list[str]


def explanation_source(mapping: StudentTaskMapping, energy_level: float, chosen: TaskType) -> str:
    bucket = _bucket(energy_level)
    prior, prior_source = mapping.prior(bucket)
    if mapping.preferences.get(bucket) == chosen and mapping.choice_counts(bucket).get(chosen):
        return "learned choices"
    if chosen == prior and prior_source == "survey":
        return "survey"
    return "default rule"


def check(
    mapping: StudentTaskMapping, energy_level: float, expected_bucket: str | None = None
) -> tuple[TaskType, str, str, float, list[str]]:
    task_type, why = recommend_task_type(mapping, energy_level)
    ranked = sorted(mapping.scores(energy_level).values(), reverse=True)
    margin = ranked[0] - ranked[1]
    bucket = _bucket(energy_level)

    issues = []
    if margin < MIN_SCORE_MARGIN:
        issues.append(f"near-tie between task types (margin {margin:.2f})")
    for cut in (LOW_ENERGY, HIGH_ENERGY):
        if abs(energy_level - cut) < NEAR_CUT:
            issues.append(f"energy {energy_level:.3f} is within {NEAR_CUT} of the {cut} cut point")
    if expected_bucket is not None and expected_bucket != bucket:
        issues.append(f"bucket mismatch: user_model says {expected_bucket}, domain_model {bucket}")
    if not why.startswith("because ") or "\n" in why or ". " in why:
        issues.append("explanation is not a single 'because ...' sentence")
    return task_type, why, explanation_source(mapping, energy_level, task_type), margin, issues


def scenario_rows(students: dict[int, str] | None = None) -> list[Row]:
    """Shivani's scenarios, each paired with a student (REPRESENTATIVE by default)."""
    rows = []
    for s in SCENARIOS:
        student = (students or REPRESENTATIVE)[s.number]
        mapping = STUDENTS[student]()
        task_type, why, source, margin, issues = check(mapping, s.energy_level, s.bucket)
        rows.append(
            Row(str(s.number), student, s.energy_level, s.bucket, task_type, why, source, margin, issues)
        )
    return rows


def grid_rows() -> list[Row]:
    """Every scenario x every student, for choosing a different pairing."""
    return [
        row
        for student in STUDENTS
        for row in scenario_rows({s.number: student for s in SCENARIOS})
    ]


def harness_rows() -> list[Row]:
    """What the evaluation harness shows participants live, checked the same way."""
    rows = []
    for scenario in PILOT_SCENARIOS:
        out = run_scenario(scenario)
        mapping = build_planner(scenario).task_mapping
        task_type, _, source, margin, issues = check(mapping, out.energy_level)
        assert task_type.value == out.recommended_task_type  # same function, same answer
        student = "learned" if scenario.history else "survey" if scenario.survey else "new"
        rows.append(
            Row(
                scenario.scenario_id, student, out.energy_level, _bucket(out.energy_level),
                task_type, out.why, source, margin, issues,
            )
        )
    return rows


def pilot_set() -> list[dict]:
    """The scenario + recommendation + explanation set, for the harness."""
    by_number = {s.number: s for s in SCENARIOS}
    return [
        {
            **by_number[int(row.label)].as_dict(),
            "student": row.student,
            "recommended_task_type": row.task_type.value,
            "why": row.why,
            "explanation_source": row.source,
        }
        for row in scenario_rows()
    ]


# -- rendering --------------------------------------------------------------------


def _table(rows: list[Row], first_col: str) -> list[str]:
    lines = [
        f"| {first_col} | Student | Energy | Bucket | Recommendation | Source | Margin | Check |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        status = "; ".join(r.issues) if r.issues else "ok"
        lines.append(
            f"| {r.label} | {r.student} | {r.energy_level:.3f} | {r.bucket} | "
            f"{r.task_type.label} | {r.source} | {r.margin:.2f} | {status} |"
        )
    return lines


def render() -> str:
    by_number = {s.number: s for s in SCENARIOS}
    rows = scenario_rows()
    lines = [
        "# Pilot recommendations",
        "",
        "Generated by `tests/domain_model/pilot_recommendations.py` from Shivani's",
        "energy scenarios (`tests/user_model/scenarios.py`). Every recommendation and",
        "explanation below is the real output of `recommend_task_type()`, not",
        "hand-written. Regenerate after changing domain_model, the scenarios or the",
        "harness:",
        "",
        "```bash",
        "PYTHONPATH=src python -m tests.domain_model.pilot_recommendations",
        "```",
        "",
        "## Representative students",
        "",
        "- **new**: first day, no survey answers, no history, so the default rule applies.",
        "- **survey**: said in onboarding they prefer problem sets when tired.",
        "- **learned**: 12 recorded choices: memorization x4 when tired, reading x4 and",
        "  review x1 at moderate energy, problem sets x3 when energized.",
        "",
        "**Margin** is the gap between the best and runner-up blended score (1.00 =",
        f"no contest; below {MIN_SCORE_MARGIN} is flagged as a near-tie). **Check** also flags",
        f"energy within {NEAR_CUT} of a cut point ({LOW_ENERGY} / {HIGH_ENERGY}), where a small",
        "change would flip the bucket and the recommendation.",
        "",
        "## Pilot set (one student per scenario)",
        "",
        *_table(rows, "#"),
        "",
    ]
    for r in rows:
        s = by_number[int(r.label)]
        checkin = f'"{s.checkin_response}"' if s.checkin_response else "skipped"
        lines += [
            f"### {s.number}. {s.label}",
            "",
            (
                f"{s.as_dict()['time_of_day']}, slept {s.sleep_window} ({s.sleep_hours:g}h), "
                f"check-in {checkin} -> energy {r.energy_level:.3f} ({s.source}, {r.bucket}). "
                f"Student: **{r.student}**."
            ),
            "",
            f"**Recommendation:** {r.task_type.label}  ",
            f"**Explanation:** {r.why}",
            "",
        ]
    lines += [
        "## Every scenario x every student",
        "",
        "For picking a different pairing. Same checks as above.",
        "",
        *_table(grid_rows(), "#"),
        "",
        "## What the harness shows live",
        "",
        "`integration.evaluation.PILOT_SCENARIOS` run through `run_scenario()` (frozen",
        "clock; fresh, survey-seeded or learned student), checked the same way. These are",
        "separate stories from the six above.",
        "",
        *_table(harness_rows(), "Scenario"),
        "",
    ]
    for r in harness_rows():
        lines.append(f"- `{r.label}`: {r.why}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    OUT.write_text(render())
    print(f"wrote {OUT}")
