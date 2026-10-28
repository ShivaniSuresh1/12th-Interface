"""End-to-end scenario: a student's day, a disruption, a replan, learning."""

from unittest.mock import patch

from domain_model.taxonomy import TaskType
from integration import StudySessionPlanner
from negotiation import ReplanProposal
from negotiation.replanning import ReplanResolution
from user_model import EnergyReport


def _proposal(change: dict | None = None) -> ReplanProposal:
    return ReplanProposal(
        student_id="s1",
        trigger="meeting_ran_late",
        message="Your meeting ran late. Switch to a lighter task?",
        proposed_change=change if change is not None else {"task_type": "review"},
    )


def test_full_day_flow_with_real_modules():
    planner = StudySessionPlanner(student_id="s1")

    plan = planner.plan_day()
    assert {"energy", "recommended_task_type", "why"} <= set(plan)
    assert isinstance(plan["recommended_task_type"], TaskType)

    corrected = planner.handle_checkin(response="tired")
    assert isinstance(corrected, EnergyReport)
    assert len(planner.profile.energy_history) == 1

    proposal = planner.handle_disruption(trigger="meeting_ran_late")
    assert isinstance(proposal, ReplanProposal)
    assert proposal.trigger == "meeting_ran_late"
    assert proposal.message  # narrated, never silent

    resolution = planner.handle_resolution(proposal, student_response="yes")
    assert isinstance(resolution, ReplanResolution)
    assert resolution.outcome in {"accepted", "edited", "rejected"}


def test_accepted_replan_updates_mapping():
    planner = StudySessionPlanner(student_id="s1")
    planner.handle_checkin(response="tired")
    level = planner.profile.energy_history[-1].energy_level
    proposal = _proposal({"task_type": "review"})
    fake = ReplanResolution(proposal=proposal, outcome="accepted", edited_change=None)

    with patch("integration.planner.resolve_proposal", return_value=fake), patch.object(
        planner.task_mapping, "record_choice"
    ) as record:
        planner.handle_resolution(proposal, student_response="yes")

    record.assert_called_once_with(level, TaskType.REVIEW)


def test_edited_replan_uses_students_edit():
    planner = StudySessionPlanner(student_id="s1")
    proposal = _proposal({"task_type": "review"})
    fake = ReplanResolution(
        proposal=proposal, outcome="edited", edited_change={"task_type": "reading"}
    )

    with patch("integration.planner.resolve_proposal", return_value=fake), patch.object(
        planner.task_mapping, "record_choice"
    ) as record:
        planner.handle_resolution(proposal, student_response="make it reading")

    assert record.call_args.args[1] == TaskType.READING


def test_rejected_replan_does_not_update_mapping():
    planner = StudySessionPlanner(student_id="s1")
    proposal = _proposal()
    fake = ReplanResolution(proposal=proposal, outcome="rejected", edited_change=None)

    with patch("integration.planner.resolve_proposal", return_value=fake), patch.object(
        planner.task_mapping, "record_choice"
    ) as record:
        planner.handle_resolution(proposal, student_response="no")

    record.assert_not_called()


def test_enough_checkins_turn_off_cold_start():
    from user_model.models import COLD_START_MIN_CHECKINS

    planner = StudySessionPlanner(student_id="s1")
    assert planner.profile.cold_start is True

    for _ in range(COLD_START_MIN_CHECKINS - 1):
        planner.handle_checkin(response="tired")
        assert planner.profile.cold_start is True

    planner.handle_checkin(response="tired")
    assert planner.profile.cold_start is False
