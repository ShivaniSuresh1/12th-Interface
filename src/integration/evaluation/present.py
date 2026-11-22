"""Show planner output to a participant in one of two conditions.

- "explanation": energy + recommendation + the planner's "why", and the
  full narrated replan message.
- "plain": the same numbers and decisions, with every explanation removed.

Both conditions show exactly the same recommendation and the same change;
the only thing that varies is whether the reasoning is visible.
"""

from __future__ import annotations

from datetime import datetime

from domain_model import TaskType

from .scenarios import Scenario
from .simulate import ScenarioOutput

CONDITIONS = ("explanation", "plain")

_SOURCE_TEXT = {
    "baseline": "estimated from your sleep and the time of day",
    "checkin_corrected": "estimated from your sleep, adjusted using your check-in answer",
}

_ACTION_VERB = {"move": "Move", "shorten": "Shorten", "defer": "Reschedule"}


def energy_bar(level: float, width: int = 20) -> str:
    """Text stand-in for the dashboard's energy gauge."""
    filled = round(level * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _time(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%I:%M %p").lstrip("0")


def plain_change(change: dict) -> str:
    """The proposed change with no reasoning, e.g. 'Move "X" to 3:10 PM-4:40 PM'."""
    action = change.get("action")
    if action == "ask":
        return "No specific change proposed. The planner asks you what changed."
    verb = _ACTION_VERB.get(action, "Change")
    title = change.get("title") or "this session"
    return f'{verb} "{title}" to {_time(change["new_start"])}-{_time(change["new_end"])}'


def render(scenario: Scenario, output: ScenarioOutput, condition: str) -> str:
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of {CONDITIONS}, got {condition!r}")
    explain = condition == "explanation"
    task = TaskType(output.recommended_task_type).label

    lines = [
        scenario.story,
        "",
        f"Estimated energy: {round(output.energy_level * 100)}%  {energy_bar(output.energy_level)}",
    ]
    if explain:
        lines.append(f"  ({_SOURCE_TEXT[output.energy_source]})")
    lines.append(f"Recommended next task type: {task}")
    if explain:
        lines.append(f"  Why: {output.why}")
    if output.has_proposal:
        lines.append("")
        if explain:
            lines.append(f"Proposed change: {output.proposal_message}")
        else:
            lines.append(f"Proposed change: {plain_change(output.proposed_change)}")
    return "\n".join(lines)


def decision_target(output: ScenarioOutput) -> str:
    """What the participant accepts/edits/rejects in this scenario."""
    return "the proposed change" if output.has_proposal else "the recommended task"


def assign(participant: int, scenarios: list[Scenario]) -> list[tuple[Scenario, str]]:
    """Counterbalanced (scenario, condition) sequence for one participant.

    Scenarios are split into two sets (alternating). Participants cycle
    through four groups so that, across every four people:
      - half see the explanation condition first (order effects), and
      - each scenario set appears in each condition equally often
        (so scenario difficulty isn't confounded with condition).
    Within-subjects: everyone sees both conditions, one block each.
    """
    if participant < 1:
        raise ValueError("participant numbers start at 1")
    group = (participant - 1) % 4
    set_a, set_b = scenarios[0::2], scenarios[1::2]
    explained, plain = (set_a, set_b) if group in (0, 1) else (set_b, set_a)
    blocks = [(explained, "explanation"), (plain, "plain")]
    if group in (1, 3):
        blocks.reverse()
    return [(s, cond) for block, cond in blocks for s in block]
