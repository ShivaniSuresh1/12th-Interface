"""Energy estimation (Q1: hybrid sleep-based baseline + conversational check-in).

Owner: Shivani. The two contract functions are `estimate_baseline_energy`
and `apply_checkin_correction` (see docs/CONTRACTS.md); everything else
here is a helper they're built from.

Baseline model (RISE-inspired two-process model, kept deliberately simple
so the planner can explain it in one sentence):

- Homeostatic sleep pressure builds the longer you're awake, starting
  higher when you slept less than you need (sleep debt).
- A circadian rhythm adds a late-afternoon/evening high, a post-lunch dip,
  and an early-morning trough.
- Once a student has check-ins at a given time of day, their own reports
  are blended in with a weight that grows with the number of reports
  (the Q4 decaying blend, reused): generic curve first, personal later.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, time, timedelta

from .models import EnergyReport, StudentProfile, as_aware

SLEEP_NEED_HOURS = 8.0
DEFAULT_WAKE_TIME = time(7, 30)  # used when no "sleep" event is logged

# Homeostatic process: pressure on waking, and its rise time constant (h).
WAKE_PRESSURE_RESTED = 0.15
WAKE_PRESSURE_PER_DEBT_HOUR = 0.15
WAKE_PRESSURE_MAX = 0.9
PRESSURE_RISE_TAU_HOURS = 18.2

HOMEOSTATIC_WEIGHT = 0.6  # circadian gets the remaining 0.4

# The raw two-process mix only spans roughly 0.1-0.8; stretch that onto the
# full 0-1 scale so domain_model's 0.33 / 0.66 buckets are all reachable
# (rested peak hours ~0.8 = "high", ~4h of sleep ~0.35-0.45 by day).
RAW_FLOOR = 0.1
RAW_CEILING = 0.8

# Personal learning: time-of-day bins of past check-ins.
BIN_HOURS = 3
HISTORY_WINDOW = 30  # most recent check-ins considered
LEARNING_HALF_N = 4  # reports in a bin at which learned weight hits half its cap
MAX_LEARNED_WEIGHT = 0.5  # today's sleep always counts for at least half

# How much a parsed check-in outweighs the baseline when they disagree.
CHECKIN_WEIGHT = 0.6

_CHECKIN_KEYWORDS: dict[str, float] = {
    "exhausted": 0.1,
    "drained": 0.15,
    "dead": 0.1,
    "tired": 0.3,
    "sleepy": 0.3,
    "low": 0.3,
    "meh": 0.45,
    "okay": 0.5,
    "ok": 0.5,
    "fine": 0.55,
    "good": 0.7,
    "alert": 0.75,
    "focused": 0.75,
    "great": 0.85,
    "energized": 0.9,
    "energetic": 0.9,
}


def estimate_baseline_energy(profile: StudentProfile) -> EnergyReport:
    """Sleep-based baseline estimate for 'right now'."""
    return estimate_energy_at(profile, datetime.now().astimezone())


def estimate_energy_at(profile: StudentProfile, at: datetime) -> EnergyReport:
    """Sleep-based baseline estimate for an arbitrary moment `at`."""
    at = as_aware(at)
    generic = generic_energy(_hours_awake(profile, at), _sleep_debt(profile, at), _hour(at))

    learned_level, n = _learned_level(profile, at)
    weight = MAX_LEARNED_WEIGHT * n / (n + LEARNING_HALF_N) if n else 0.0
    level = (1 - weight) * generic + weight * learned_level

    return EnergyReport(
        student_id=profile.student_id,
        timestamp=at,
        energy_level=_clamp(level),
        source="baseline",
    )


def generic_energy(hours_awake: float, sleep_debt_hours: float, hour_of_day: float) -> float:
    """The population-level curve, before any personal learning."""
    wake_pressure = min(
        WAKE_PRESSURE_MAX,
        WAKE_PRESSURE_RESTED + WAKE_PRESSURE_PER_DEBT_HOUR * max(0.0, sleep_debt_hours),
    )
    pressure = 1 - (1 - wake_pressure) * math.exp(-max(0.0, hours_awake) / PRESSURE_RISE_TAU_HOURS)
    homeostatic = 1 - pressure

    circadian = (
        0.5
        + 0.35 * math.cos(2 * math.pi * (hour_of_day - 16) / 24)  # trough ~4am, high ~4pm
        - 0.15 * math.cos(2 * math.pi * (hour_of_day - 14) / 12)  # post-lunch dip ~2pm
    )
    raw = HOMEOSTATIC_WEIGHT * homeostatic + (1 - HOMEOSTATIC_WEIGHT) * _clamp(circadian)
    return _clamp((raw - RAW_FLOOR) / (RAW_CEILING - RAW_FLOOR))


def apply_checkin_correction(baseline: EnergyReport, checkin_response: str) -> EnergyReport:
    """Correct the baseline using a short conversational check-in.

    The check-in is weighted above the baseline (CHECKIN_WEIGHT) because it
    reflects how the student feels today, but the baseline still pulls the
    result toward hidden sleep debt the student may not notice. If the
    response can't be interpreted, the baseline is returned unchanged
    (still marked "baseline") so it isn't mistaken for a real self-report.
    """
    reported = parse_checkin_response(checkin_response)
    if reported is None:
        return baseline

    level = (1 - CHECKIN_WEIGHT) * baseline.energy_level + CHECKIN_WEIGHT * reported
    return EnergyReport(
        student_id=baseline.student_id,
        timestamp=baseline.timestamp,
        energy_level=_clamp(level),
        source="checkin_corrected",
    )


def parse_checkin_response(response: str) -> float | None:
    """Turn a check-in answer into a 0.0-1.0 self-report, or None if unclear.

    Accepts a 1-5 rating ("3", "3/5"), a 0-1 value ("0.4"), or a phrase
    containing a known keyword ("pretty tired", "not tired"). A leading
    "not"/"no longer" flips the keyword around the midpoint.
    """
    text = response.strip().lower()

    rating = re.fullmatch(r"([1-5])(?:\s*/\s*5)?", text)
    if rating:
        return (int(rating.group(1)) - 1) / 4
    if re.fullmatch(r"0?\.\d+|0|1(?:\.0+)?", text):
        return float(text)

    words = re.findall(r"[a-z]+", text)
    for i, word in enumerate(words):
        if word in _CHECKIN_KEYWORDS:
            value = _CHECKIN_KEYWORDS[word]
            negated = i > 0 and words[i - 1] in {"not", "longer", "never"}
            return 1 - value if negated else value
    return None


def _hours_awake(profile: StudentProfile, at: datetime) -> float:
    sleep = profile.schedule.last_sleep_before(at) if profile.schedule else None
    if sleep is not None:
        wake = sleep["end"]
    else:
        wake = datetime.combine(at.date(), DEFAULT_WAKE_TIME, tzinfo=at.tzinfo)
        if wake > at:  # still up from yesterday (e.g. 1am)
            wake -= timedelta(days=1)
    return (at - wake).total_seconds() / 3600


def _sleep_debt(profile: StudentProfile, at: datetime) -> float:
    sleep_hours = profile.sleep_hours
    if sleep_hours is None and profile.schedule:
        sleep = profile.schedule.last_sleep_before(at)
        if sleep is not None and "start" in sleep:
            sleep_hours = (sleep["end"] - sleep["start"]).total_seconds() / 3600
    if sleep_hours is None:
        return 0.0  # unknown -> assume rested rather than invent a penalty
    return max(0.0, SLEEP_NEED_HOURS - sleep_hours)


def _learned_level(profile: StudentProfile, at: datetime) -> tuple[float, int]:
    """Mean self-reported energy in `at`'s time-of-day bin, and how many reports."""
    target_bin = int(_hour(at)) // BIN_HOURS
    recent = profile.checkin_reports()[-HISTORY_WINDOW:]
    levels = [
        r.energy_level
        for r in recent
        if int(_hour(as_aware(r.timestamp).astimezone(at.tzinfo))) // BIN_HOURS == target_bin
    ]
    if not levels:
        return 0.0, 0
    return sum(levels) / len(levels), len(levels)


def _hour(dt: datetime) -> float:
    return dt.hour + dt.minute / 60


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))
