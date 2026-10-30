"""Top-level orchestrator (owner: Harshini).

Wires user_model + domain_model + negotiation together. Deliberately thin:
real logic belongs in the owning module, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from domain_model import StudentTaskMapping, recommend_task_type
from domain_model.taxonomy import TaskType
from negotiation import ReplanProposal, propose_replan, resolve_proposal
from negotiation.replanning import ReplanResolution
from user_model import (
    EnergyReport,
    StudentProfile,
    apply_checkin_correction,
    estimate_baseline_energy,
)
from user_model.models import as_aware

# A check-in older than this no longer reflects how the student feels now.
RECENT_CHECKIN_WINDOW = timedelta(hours=2)


@dataclass
class StudySessionPlanner:
    """Thin orchestrator tying the three owned components together."""

    student_id: str
    profile: StudentProfile = field(init=False)
    task_mapping: StudentTaskMapping = field(init=False)

    def __post_init__(self) -> None:
        self.profile = StudentProfile(student_id=self.student_id)
        self.task_mapping = StudentTaskMapping(student_id=self.student_id)

    def plan_day(self) -> dict:
        """Produce today's plan: current energy -> recommended task type."""
        energy = self._current_energy()
        task_type, why = recommend_task_type(self.task_mapping, energy.energy_level)
        return {"energy": energy, "recommended_task_type": task_type, "why": why}

    def handle_checkin(self, response: str) -> EnergyReport:
        """Apply a conversational check-in correction (Q1, at a session boundary)."""
        baseline = estimate_baseline_energy(self.profile)
        corrected = apply_checkin_correction(baseline, response)
        self.profile.record_energy(corrected)
        return corrected

    def handle_disruption(self, trigger: str) -> ReplanProposal:
        """Something changed -- propose (never silently apply) a replan."""
        return propose_replan(self.profile, trigger=trigger)

    def handle_resolution(
        self,
        proposal: ReplanProposal,
        student_response: str,
        edited_change: dict | None = None,
    ) -> ReplanResolution:
        """Resolve a replan proposal and feed the outcome back into learning."""
        resolution = resolve_proposal(
            proposal, student_response, edited_change=edited_change
        )
        chosen = self._chosen_task_type(resolution)
        if chosen is not None:
            level = self._current_energy().energy_level
            self.task_mapping.record_choice(level, chosen)
        return resolution

    # -- small private helpers (no domain logic, just plumbing) --

    def _current_energy(self) -> EnergyReport:
        """Latest check-in if it is recent, else the baseline estimate."""
        if self.profile.energy_history:
            latest = self.profile.energy_history[-1]
            age = datetime.now().astimezone() - as_aware(latest.timestamp)
            if age <= RECENT_CHECKIN_WINDOW:
                return latest
        return estimate_baseline_energy(self.profile)

    @staticmethod
    def _chosen_task_type(resolution: ReplanResolution) -> TaskType | None:
        """Pull the student's chosen TaskType out of a resolution, if any."""
        if resolution.outcome == "rejected":
            return None
        if resolution.outcome == "edited" and resolution.edited_change:
            change = resolution.edited_change
        else:
            change = resolution.proposal.proposed_change
        raw = change.get("task_type") if isinstance(change, dict) else None
        if raw is None:
            return None
        try:
            return TaskType(raw)
        except ValueError:
            return None
