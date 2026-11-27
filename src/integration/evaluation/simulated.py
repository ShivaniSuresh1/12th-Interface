"""Simulated participants for the evaluation harness.

NOT REAL DATA. This runs the real harness (same scenarios, same
counterbalancing, same logging, same exit survey) with a *response model*
answering instead of a person, so the whole pipeline (logs -> analyze ->
report) can be shown end to end without an outside pilot.

    PYTHONPATH=src python -m integration.evaluation simulate --n 8
    PYTHONPATH=src python -m integration.evaluation analyze --log-dir eval_logs/simulated

Every simulated log directory gets a SIMULATED.md marker, and `analyze`
puts a "SIMULATED DATA" banner on any report built from it.

Important for the write-up: the response model *assumes* that explanations
raise trust and acceptance (EXPLANATION_EFFECT below). Any difference
between conditions in the simulated report is therefore an input of the
simulation, not a finding. Report it as "simulated participants generated
from a response model", state the assumed effect, and don't present the
numbers as evidence that the explanation changed trust.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from .__main__ import run_session
from .log import LOG_DIR
from .scenarios import PILOT_SCENARIOS, Scenario

SIM_DIR = LOG_DIR / "simulated"
MARKER = "SIMULATED.md"

# --- response model (all assumptions, stated so they can go in the report) ---
BASELINE_TRUST_MEAN = 4.5  # per-person trust level, 1-7 scale
BASELINE_TRUST_SD = 0.7
EXPLANATION_EFFECT = 1.0  # ASSUMED trust boost when "Why:" is shown
SCENARIO_NOISE_SD = 0.8
ACCEPT_SLOPE = 0.9  # how strongly trust drives accepting
EDIT_SHARE = 0.4  # of non-accepts, share that are edits (rest reject)
ANSWER_ASK_P = 0.7  # chance of answering the planner's question in s4
TIME_MEDIAN_S = {"explanation": 9.0, "plain": 5.0}  # more to read when explained
TIME_SD_LOG = 0.4


def _clamp7(x: float) -> int:
    return max(1, min(7, round(x)))


@dataclass
class SimulatedParticipant:
    """Answers harness prompts the way the response model says to."""

    participant: int
    rng: random.Random
    baseline: float = 0.0
    _time: float = 0.0
    _pending_delta: float = 0.0
    _condition: str = "plain"
    _trust: int = 4
    _survey_trust: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.baseline = self.rng.gauss(BASELINE_TRUST_MEAN, BASELINE_TRUST_SD)

    # run_session calls clock() when a scenario is shown and again after the
    # decision; the decision prompt sets how long that decision "took".
    def clock(self) -> float:
        self._time += self._pending_delta
        self._pending_delta = 0.0
        return self._time

    def start_scenario(self, condition: str) -> None:
        self._condition = condition
        boost = EXPLANATION_EFFECT if condition == "explanation" else 0.0
        self._trust = _clamp7(self.baseline + boost + self.rng.gauss(0, SCENARIO_NOISE_SD))
        self._survey_trust.append(self._trust)

    def _decision_time(self) -> float:
        median = TIME_MEDIAN_S[self._condition]
        return round(math.exp(self.rng.gauss(math.log(median), TIME_SD_LOG)), 2)

    def answer(self, prompt: str) -> str:
        if "[a/e/r]" in prompt:
            self._pending_delta = self._decision_time()
            p_accept = 1 / (1 + math.exp(-ACCEPT_SLOPE * (self._trust - 4)))
            if self.rng.random() < p_accept:
                return "a"
            return "e" if self.rng.random() < EDIT_SHARE else "r"
        if "[y/n]" in prompt:
            self._pending_delta = self._decision_time()
            return "y" if self.rng.random() < ANSWER_ASK_P else "n"
        if prompt.startswith("What would you change?"):
            return "[simulated edit]"
        if "optional, press Enter" in prompt:
            return ""
        if prompt.startswith("How much do you trust"):
            return str(self._trust)
        if prompt.startswith("How confident"):
            return str(_clamp7(self._trust + self.rng.gauss(0.3, 0.8)))
        return self._survey_answer(prompt)

    def _survey_answer(self, prompt: str) -> str:
        mean_trust = sum(self._survey_trust) / max(1, len(self._survey_trust))
        if "[1] with explanation" in prompt:
            return "1" if self.rng.random() < 0.75 else self.rng.choice(["2", "3"])
        if "strongly agree" in prompt:
            lift = 0.8 if ("Why" in prompt or "explained" in prompt) else 0.0
            return str(_clamp7(mean_trust + lift + self.rng.gauss(0, 0.7)))
        return ""  # free-text questions: left blank, no invented quotes


def _sequence_conditions(participant: int, scenarios: list[Scenario]) -> list[str]:
    from .present import assign

    return [condition for _s, condition in assign(participant, scenarios)]


def simulate(
    n: int = 8,
    seed: int = 634,
    log_dir: Path = SIM_DIR,
    scenarios: list[Scenario] = PILOT_SCENARIOS,
) -> Path:
    """Write n simulated participants' logs + surveys to log_dir."""
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / MARKER).write_text(
        "# SIMULATED DATA\n\n"
        "These logs were generated by integration.evaluation.simulated, not by people.\n"
        f"n={n}, seed={seed}, assumed explanation trust effect={EXPLANATION_EFFECT}.\n"
        "Do not report them as pilot results.\n",
        encoding="utf-8",
    )
    rng = random.Random(seed)
    for participant in range(1, n + 1):
        sim = SimulatedParticipant(participant, random.Random(rng.random()))
        conditions = iter(_sequence_conditions(participant, scenarios))

        def input_fn(prompt: str, sim: SimulatedParticipant = sim, conditions=conditions) -> str:
            if "[a/e/r]" in prompt or "[y/n]" in prompt:
                sim.start_scenario(next(conditions))
            return sim.answer(prompt)

        run_session(participant, scenarios, input_fn=input_fn, log_dir=log_dir, clock=sim.clock)
    return log_dir


def is_simulated(log_dir: Path) -> bool:
    return (log_dir / MARKER).exists()
