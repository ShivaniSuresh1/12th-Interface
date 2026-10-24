"""Top-level orchestrator (owner: Harshini).

Wires user_model + domain_model + negotiation together. Deliberately thin:
real logic belongs in the owning module, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain_model import StudentTaskMapping, recommend_task_type
from negotiation import ReplanProposal, propose_replan, resolve_proposal
from user_model import StudentProfile, apply_checkin_correction, estimate_baseline_energy


@dataclass
class StudySessionPlanner:
    """Thin orchestrator tying the three owned components together.

    TODO (Harshini): flesh this out as the other modules' real
    implementations land. This stub exists mainly so an end-to-end
    "smoke test" scenario can be written against *something* from day one.
    """

    student_id: str
    profile: StudentProfile = field(init=False)
    task_mapping: StudentTaskMapping = field(init=False)

    def __post_init__(self) -> None:
        self.profile = StudentProfile(student_id=self.student_id)
        self.task_mapping = StudentTaskMapping(student_id=self.student_id)

    def plan_day(self):
        """Produce today's plan: baseline energy -> recommended task type."""
        baseline = estimate_baseline_energy(self.profile)
        task_type, why = recommend_task_type(self.task_mapping, baseline.energy_level)
        return {"energy": baseline, "recommended_task_type": task_type, "why": why}

    def handle_checkin(self, response: str):
        """Apply a conversational check-in correction (Q1, at a session boundary)."""
        baseline = estimate_baseline_energy(self.profile)
        corrected = apply_checkin_correction(baseline, response)
        self.profile.energy_history.append(corrected)
        return corrected

    def handle_disruption(self, trigger: str) -> ReplanProposal:
        """Something changed -- propose (never silently apply) a replan."""
        return propose_replan(self.profile, trigger=trigger)

    def handle_resolution(self, proposal: ReplanProposal, student_response: str):
        """Resolve a replan proposal and feed the outcome back into learning."""
        resolution = resolve_proposal(proposal, student_response)
        # TODO: translate resolution.outcome into a
        # self.task_mapping.record_choice(...) call once the shapes line up.
        return resolution
