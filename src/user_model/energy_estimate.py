"""Energy estimation stubs (Q1: hybrid sleep-based + conversational).

Owner: Shivani. Replace the TODO bodies with the real logic; signatures are
a starting proposal, not a contract -- just flag it in PR if you change them
since Domain Model (energy->task mapping) consumes EnergyReport.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .models import EnergyReport, StudentProfile


def estimate_baseline_energy(profile: StudentProfile) -> EnergyReport:
    """Sleep-based baseline estimate for 'right now'.

    TODO: implement an actual sleep/circadian-style curve (RISE-inspired).
    For now returns a flat placeholder so downstream code has something to
    call against.
    """
    return EnergyReport(
        student_id=profile.student_id,
        timestamp=datetime.now(UTC),
        energy_level=0.5,
        source="baseline",
    )


def apply_checkin_correction(
    baseline: EnergyReport, checkin_response: str
) -> EnergyReport:
    """Correct the baseline using a short conversational check-in.

    TODO: implement the weighting rule between the sleep-based baseline and
    the check-in signal (two signals can disagree -- see docs/design-decisions.md Q1).
    `checkin_response` is a placeholder (e.g. "tired" / "fine" / "energized");
    Negotiation & Replanning decides how/when this gets collected (Q6).
    """
    # Placeholder: nudge the number slightly based on a crude keyword match.
    adjustment = {"tired": -0.15, "fine": 0.0, "energized": 0.15}.get(
        checkin_response, 0.0
    )
    corrected_level = max(0.0, min(1.0, baseline.energy_level + adjustment))
    return EnergyReport(
        student_id=baseline.student_id,
        timestamp=datetime.now(UTC),
        energy_level=corrected_level,
        source="checkin_corrected",
    )
