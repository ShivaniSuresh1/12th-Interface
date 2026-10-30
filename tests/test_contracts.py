"""Contract checks: catches interface drift regardless of who (or which AI
assistant) wrote the implementation.

Four people may be prompting four different LLMs independently. This test
is the mechanical backstop for docs/CONTRACTS.md -- if someone's assistant
renamed a function, reordered parameters, or renamed a dataclass field,
this fails loudly in CI instead of surfacing as a confusing integration
bug days before a deadline.

Do NOT "fix" a failure here by editing this test to match a changed
signature. Fix it by either reverting the signature change, or -- if the
team agreed the contract itself should change -- updating docs/CONTRACTS.md
AND this test together, in the same PR, with the reason in the PR
description.
"""

from __future__ import annotations

import inspect


def _params(fn) -> list[str]:
    return list(inspect.signature(fn).parameters.keys())


def _fields(dc) -> list[str]:
    return [f.name for f in __import__("dataclasses").fields(dc)]


# ---------------------------------------------------------------------
# user_model (owner: Shivani) -- Q1, Q2
# ---------------------------------------------------------------------


def test_user_model_contract():
    from user_model import (
        EnergyReport,
        StudentProfile,
        StudentSchedule,
        apply_checkin_correction,
        estimate_baseline_energy,
    )

    assert _fields(StudentSchedule) == ["student_id", "events"]
    assert _fields(EnergyReport) == [
        "student_id",
        "timestamp",
        "energy_level",
        "source",
    ]
    assert _fields(StudentProfile) == [
        "student_id",
        "sleep_hours",
        "schedule",
        "cold_start",
        "energy_history",
    ]

    assert _params(estimate_baseline_energy) == ["profile"]
    assert _params(apply_checkin_correction) == ["baseline", "checkin_response"]


# ---------------------------------------------------------------------
# domain_model (owner: Vyshnavi) -- Q3, Q4
# ---------------------------------------------------------------------


def test_domain_model_contract():
    from domain_model import StudentTaskMapping, Task, TaskType, recommend_task_type

    assert {t.value for t in TaskType} == {
        "problem_set",
        "reading",
        "review",
        "memorization",
    }
    assert _fields(Task) == ["task_id", "title", "task_type", "difficulty"]
    assert _fields(StudentTaskMapping) == [
        "student_id",
        "learned_weight",
        "preferences",
    ]
    assert _params(recommend_task_type) == ["mapping", "energy_level"]


# ---------------------------------------------------------------------
# negotiation (owner: Soumyadip) -- Q5, Q6
# ---------------------------------------------------------------------


def test_negotiation_contract():
    from negotiation import (
        CheckinWindow,
        ReplanProposal,
        is_session_boundary,
        propose_replan,
        resolve_proposal,
    )
    from negotiation.replanning import ReplanResolution

    assert _fields(CheckinWindow) == ["student_id", "boundary_type", "timestamp"]
    assert _fields(ReplanProposal) == [
        "student_id",
        "trigger",
        "message",
        "proposed_change",
    ]
    assert _fields(ReplanResolution) == ["proposal", "outcome", "edited_change"]

    assert _params(is_session_boundary) == ["now", "schedule"]
    assert _params(propose_replan) == ["student_profile", "trigger"]
    assert _params(resolve_proposal) == [
        "proposal",
        "student_response",
        "edited_change",
    ]


# ---------------------------------------------------------------------
# integration (owner: Harshini) -- cross-cutting
# ---------------------------------------------------------------------


def test_integration_contract():
    from integration import StudySessionPlanner

    assert _params(StudySessionPlanner.plan_day) == ["self"]
    assert _params(StudySessionPlanner.handle_checkin) == ["self", "response"]
    assert _params(StudySessionPlanner.handle_disruption) == ["self", "trigger"]
    assert _params(StudySessionPlanner.handle_resolution) == [
        "self",
        "proposal",
        "student_response",
        "edited_change",
    ]
