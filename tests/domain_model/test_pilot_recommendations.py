"""Guard the recommendations the pilot scenarios rely on.

The pilot set is meant to show every explanation source (default rule,
survey, learned choices) and all four task types. If a change in any module
(energy curve, scenario inputs, mapping) flips one, fail here instead of
the pilot quietly losing a case.
"""

import pytest

from domain_model import TaskType

from .pilot_recommendations import (
    OUT,
    grid_rows,
    harness_rows,
    pilot_set,
    scenario_rows,
)

EXPECTED = {
    "1": (TaskType.PROBLEM_SET, "default rule"),
    "2": (TaskType.PROBLEM_SET, "survey"),
    "3": (TaskType.REVIEW, "default rule"),
    "4": (TaskType.PROBLEM_SET, "learned choices"),
    "5": (TaskType.READING, "learned choices"),
    "6": (TaskType.MEMORIZATION, "learned choices"),
}

ROWS = scenario_rows()


def test_expected_covers_every_scenario():
    assert {r.label for r in ROWS} == set(EXPECTED)


@pytest.mark.parametrize("row", ROWS, ids=lambda r: f"scenario{r.label}")
def test_pilot_scenario_gets_its_recommendation(row):
    assert (row.task_type, row.source) == EXPECTED[row.label]
    assert row.issues == []


def test_pilot_set_covers_every_source_and_task_type():
    assert {r.source for r in ROWS} == {"default rule", "survey", "learned choices"}
    assert {r.task_type for r in ROWS} == set(TaskType)


def test_no_near_ties_for_any_student():
    assert [r for r in grid_rows() if "near-tie" in " ".join(r.issues)] == []


def test_harness_recommendations_are_not_ties():
    for row in harness_rows():
        assert not any("near-tie" in issue for issue in row.issues), row.label


def test_pilot_set_for_harness():
    items = pilot_set()
    assert [i["number"] for i in items] == [1, 2, 3, 4, 5, 6]
    for item in items:
        assert item["why"].startswith("because ")
        assert TaskType(item["recommended_task_type"])


def test_pilot_recommendations_doc_is_generated():
    text = OUT.read_text()
    for row in ROWS + harness_rows():
        assert row.why in text, "regenerate: python -m tests.domain_model.pilot_recommendations"
