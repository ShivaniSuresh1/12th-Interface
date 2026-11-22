"""Fixed energy scenarios for the Nov 20 pilot dry-run (User Model half).

Each scenario is (time of day, last night's sleep, check-in response). The
energy numbers are NOT hand-picked: `build_scenarios()` runs every input
through the real pipeline (`estimate_energy_at` -> `apply_checkin_correction`)
so the harness sees exactly what the system would produce.

    from tests.user_model.scenarios import SCENARIOS
    for s in SCENARIOS:
        s.energy_level, s.bucket, s.profile ...

Scenario N here pairs with Vyshnavi's and Soumyadip's scenario N.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from user_model.energy_estimate import apply_checkin_correction, estimate_energy_at
from user_model.models import EnergyReport, StudentProfile, StudentSchedule

# Fixed local (naive) date so results never depend on when the tests run.
SCENARIO_DATE = date(2026, 11, 20)
WAKE_TIME = time(7, 30)

# Same cut points as domain_model's energy buckets.
LOW_ENERGY = 0.33
HIGH_ENERGY = 0.66


@dataclass(frozen=True)
class ScenarioInput:
    number: int
    label: str
    time_of_day: time
    sleep_hours: float
    checkin_response: str | None  # None = student skipped the check-in


@dataclass
class EnergyScenario:
    number: int
    label: str
    time_of_day: time
    sleep_hours: float
    sleep_window: str  # human-readable, e.g. "2:30 AM to 7:30 AM"
    checkin_response: str | None
    baseline_energy: float
    energy_level: float  # what downstream modules should consume
    source: str  # "baseline" | "checkin_corrected"
    bucket: str  # "low" | "medium" | "high"
    profile: StudentProfile
    report: EnergyReport

    def as_dict(self) -> dict:
        return {
            "number": self.number,
            "label": self.label,
            "time_of_day": self.time_of_day.strftime("%I:%M %p").lstrip("0"),
            "sleep_hours": self.sleep_hours,
            "sleep_window": self.sleep_window,
            "checkin_response": self.checkin_response,
            "baseline_energy": round(self.baseline_energy, 3),
            "energy_level": round(self.energy_level, 3),
            "source": self.source,
            "bucket": self.bucket,
        }


INPUTS: list[ScenarioInput] = [
    ScenarioInput(1, "well rested, morning", time(9, 30), 8.0, "focused"),
    ScenarioInput(2, "short night, post-lunch", time(14, 0), 5.0, "exhausted"),
    ScenarioInput(3, "slept fine but says tired", time(10, 30), 7.0, "tired"),
    ScenarioInput(4, "evening, rested", time(20, 0), 8.0, "good"),
    ScenarioInput(5, "no check-in, short night, afternoon", time(16, 0), 5.0, None),
    ScenarioInput(6, "very short night, late morning", time(11, 0), 4.0, "exhausted"),
]


def bucket_for(energy_level: float) -> str:
    if energy_level < LOW_ENERGY:
        return "low"
    if energy_level < HIGH_ENERGY:
        return "medium"
    return "high"


def _fmt(t: datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


def build_scenario(inp: ScenarioInput) -> EnergyScenario:
    wake = datetime.combine(SCENARIO_DATE, WAKE_TIME)
    sleep_start = wake - timedelta(hours=inp.sleep_hours)
    profile = StudentProfile(
        student_id=f"pilot_s{inp.number}",
        sleep_hours=inp.sleep_hours,
        schedule=StudentSchedule(
            student_id=f"pilot_s{inp.number}",
            events=[{"kind": "sleep", "start": sleep_start, "end": wake, "title": "last night"}],
        ),
        cold_start=True,
        energy_history=[],
    )
    at = datetime.combine(SCENARIO_DATE, inp.time_of_day)
    baseline = estimate_energy_at(profile, at)
    report = (
        apply_checkin_correction(baseline, inp.checkin_response)
        if inp.checkin_response is not None
        else baseline
    )
    return EnergyScenario(
        number=inp.number,
        label=inp.label,
        time_of_day=inp.time_of_day,
        sleep_hours=inp.sleep_hours,
        sleep_window=f"{_fmt(sleep_start)} to {_fmt(wake)}",
        checkin_response=inp.checkin_response,
        baseline_energy=baseline.energy_level,
        energy_level=report.energy_level,
        source=report.source,
        bucket=bucket_for(report.energy_level),
        profile=profile,
        report=report,
    )


def build_scenarios() -> list[EnergyScenario]:
    return [build_scenario(i) for i in INPUTS]


SCENARIOS: list[EnergyScenario] = build_scenarios()


if __name__ == "__main__":
    for s in SCENARIOS:
        print(s.as_dict())
