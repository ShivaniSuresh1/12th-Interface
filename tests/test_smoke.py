"""Smoke test: the four modules import and wire together end-to-end.

This is deliberately trivial -- it exists so CI has something to run from
day one, and so each owner has a concrete place to extend with real tests
for their module.
"""

from integration import StudySessionPlanner


def test_planner_plans_a_day():
    planner = StudySessionPlanner(student_id="test-student")
    plan = planner.plan_day()
    assert "recommended_task_type" in plan
    assert plan["why"]  # explanation string is non-empty


def test_checkin_corrects_energy():
    planner = StudySessionPlanner(student_id="test-student")
    corrected = planner.handle_checkin(response="tired")
    assert corrected.source == "checkin_corrected"


def test_disruption_proposes_not_silently_applies():
    planner = StudySessionPlanner(student_id="test-student")
    proposal = planner.handle_disruption(trigger="meeting_ran_late")
    assert proposal.trigger == "meeting_ran_late"
    assert proposal.message  # must be narrated, not silent
