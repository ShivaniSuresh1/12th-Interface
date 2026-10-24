"""Negotiated replanning (Q5). Owner: Soumyadip.

Design intent: never silently reschedule. Propose + narrate, let the
student accept or edit with one tap. The resolution is a labeled example
that should feed back into domain_model.StudentTaskMapping.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReplanProposal:
    student_id: str
    trigger: str  # e.g. "fatigue", "meeting_ran_late", "missed_session"
    message: str  # narrated, batched with any check-in (Q6)
    proposed_change: dict  # TODO: real shape (move/shorten/defer which session)


@dataclass
class ReplanResolution:
    proposal: ReplanProposal
    outcome: str  # "accepted" | "edited" | "rejected"
    edited_change: dict | None = None


def propose_replan(student_profile: object, trigger: str) -> ReplanProposal:
    """Build a narrated replan proposal.

    TODO: implement the actual move/shorten/defer decision logic, and the
    "not sure, want to just tell me what changed?" fallback for low
    confidence (Calendar.help-style).
    """
    return ReplanProposal(
        student_id=getattr(student_profile, "student_id", "unknown"),
        trigger=trigger,
        message=f"Noticed {trigger} -- want me to adjust today's plan?",
        proposed_change={},
    )


def resolve_proposal(
    proposal: ReplanProposal, student_response: str, edited_change: dict | None = None
) -> ReplanResolution:
    """Resolve a proposal based on the student's one-tap response.

    `student_response` is a placeholder for "accept" | "edit" | "reject".
    TODO: on resolution, call domain_model.StudentTaskMapping.record_choice(...)
    so this feeds the learned mapping (Q4 x Q5 interaction).
    """
    outcome = {"accept": "accepted", "edit": "edited", "reject": "rejected"}.get(
        student_response, "rejected"
    )
    return ReplanResolution(
        proposal=proposal, outcome=outcome, edited_change=edited_change
    )
