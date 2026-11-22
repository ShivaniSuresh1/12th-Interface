"""Run a scenario through StudySessionPlanner with the clock frozen.

The planner (and the modules it calls) read the real clock, so the same
scenario would give different energy estimates at 9am vs 9pm. For a fair
experiment every participant must see identical output, so we freeze
"now" at the scenario's time while the planner runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, tzinfo
from unittest.mock import patch

from domain_model import StudentTaskMapping
from integration.planner import StudySessionPlanner
from user_model import StudentSchedule

from .scenarios import Scenario

# Modules that call datetime.now() on the planner's code path.
_DATETIME_USERS = ("user_model.energy_estimate.datetime", "integration.planner.datetime")


@dataclass
class ScenarioOutput:
    """What the planner produced for one scenario (JSON-friendly)."""

    scenario_id: str
    energy_level: float
    energy_source: str  # "baseline" | "checkin_corrected"
    recommended_task_type: str  # TaskType value
    why: str  # domain_model's one-sentence explanation
    proposal_message: str | None = None  # negotiation's narrated replan, if a disruption
    proposed_change: dict | None = None

    @property
    def has_proposal(self) -> bool:
        return self.proposal_message is not None


@contextmanager
def frozen_clock(now: datetime) -> Iterator[None]:
    """Make datetime.now() return `now` inside the planner's modules."""

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return now if tz is None else now.astimezone(tz)

    patches = [patch(target, _FrozenDatetime) for target in _DATETIME_USERS]
    patches.append(
        patch(
            "negotiation.replanning._now",
            lambda reference=None: now.astimezone(reference.tzinfo)
            if reference is not None and reference.tzinfo is not None
            else now,
        )
    )
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in reversed(patches):
            p.stop()


def build_planner(scenario: Scenario) -> StudySessionPlanner:
    """A planner whose student matches the scenario (sleep, schedule, survey)."""
    planner = StudySessionPlanner(student_id=scenario.scenario_id)
    planner.profile.sleep_hours = scenario.sleep_hours
    planner.profile.schedule = StudentSchedule(
        student_id=scenario.scenario_id, events=scenario.schedule_events()
    )
    if scenario.survey:
        planner.task_mapping = StudentTaskMapping.from_survey(
            scenario.scenario_id, scenario.survey
        )
    return planner


def run_scenario(scenario: Scenario) -> ScenarioOutput:
    """check-in (optional) -> plan_day() -> disruption (optional)."""
    planner = build_planner(scenario)
    with frozen_clock(scenario.now):
        if scenario.checkin:
            planner.handle_checkin(response=scenario.checkin)
        plan = planner.plan_day()
        proposal = (
            planner.handle_disruption(trigger=scenario.disruption)
            if scenario.disruption
            else None
        )

    energy = plan["energy"]
    return ScenarioOutput(
        scenario_id=scenario.scenario_id,
        energy_level=round(energy.energy_level, 3),
        energy_source=energy.source,
        recommended_task_type=plan["recommended_task_type"].value,
        why=plan["why"],
        proposal_message=proposal.message if proposal else None,
        proposed_change=proposal.proposed_change if proposal else None,
    )
