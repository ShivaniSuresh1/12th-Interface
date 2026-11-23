"""Record negotiation's real replan proposals for the pilot scenarios.

Runs every pilot scenario that has a disruption through the evaluation
harness (same frozen clock participants get) and writes what
propose_replan() actually says to src/negotiation/PILOT_PROPOSALS.md.
Nothing in that file is written by hand.

    PYTHONPATH=src python -m tests.negotiation.pilot_proposals
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from integration.evaluation.scenarios import PILOT_SCENARIOS
from integration.evaluation.simulate import run_scenario

OUT = Path(__file__).resolve().parents[2] / "src" / "negotiation" / "PILOT_PROPOSALS.md"


def _time(iso: str | None) -> str:
    if not iso:
        return "-"
    return datetime.fromisoformat(iso).strftime("%I:%M %p").lstrip("0")


def render() -> str:
    lines = [
        "# Pilot replan proposals",
        "",
        "Generated from `integration.evaluation.PILOT_SCENARIOS` by",
        "`tests/negotiation/pilot_proposals.py`. Every message below is the real",
        "output of `propose_replan()` for that scenario, not hand-written.",
        "Regenerate after changing negotiation or the scenarios:",
        "",
        "```bash",
        "PYTHONPATH=src python -m tests.negotiation.pilot_proposals",
        "```",
        "",
        "| Scenario | Trigger | Energy | Action | Session | Change |",
        "|---|---|---|---|---|---|",
    ]
    details = []
    for scenario in PILOT_SCENARIOS:
        if not scenario.disruption:
            continue
        out = run_scenario(scenario)
        change = out.proposed_change or {}
        action = change.get("action", "-")
        when = (
            f"{_time(change.get('original_start'))}-{_time(change.get('original_end'))} -> "
            f"{_time(change.get('new_start'))}-{_time(change.get('new_end'))}"
            if action != "ask"
            else "asks the student"
        )
        lines.append(
            f"| `{scenario.scenario_id}` | `{scenario.disruption}` | "
            f"{out.energy_level:.2f} ({out.energy_source}) | {action} | "
            f"{change.get('title') or '-'} | {when} |"
        )
        details += [
            f"## `{scenario.scenario_id}`",
            "",
            f"**Story:** {scenario.story}",
            "",
            f"**Proposal shown to the student:** {out.proposal_message}",
            "",
        ]
    return "\n".join(lines + [""] + details)


if __name__ == "__main__":
    OUT.write_text(render())
    print(f"wrote {OUT}")
