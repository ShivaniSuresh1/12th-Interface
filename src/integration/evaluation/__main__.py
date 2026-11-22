"""Evaluation harness command line.

From the repo root:

    PYTHONPATH=src python -m integration.evaluation preview
        Print every scenario in both conditions (for checking content).

    PYTHONPATH=src python -m integration.evaluation run --participant 3
        Run one participant's session in their counterbalanced order.
        Answers are saved to eval_logs/participant_03.csv as they go.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .log import LOG_DIR, SessionLog
from .present import CONDITIONS, assign, decision_target, render
from .scenarios import PILOT_SCENARIOS, Scenario
from .simulate import run_scenario

DECISIONS = {"a": "accept", "e": "edit", "r": "reject"}
RULE = "-" * 70

TRUST_QUESTION = "How much do you trust the planner's suggestion here?"
CONFIDENCE_QUESTION = "How confident are you in the decision you just made?"
SCALE_HINT = "1 = not at all, 7 = completely"

InputFn = Callable[[str], str]


def ask_decision(target: str, input_fn: InputFn = input) -> str:
    prompt = f"Do you accept, edit, or reject {target}? [a/e/r]: "
    while True:
        answer = input_fn(prompt).strip().lower()[:1]
        if answer in DECISIONS:
            return DECISIONS[answer]
        print("Please type a, e, or r.")


def ask_rating(question: str, input_fn: InputFn = input) -> int:
    prompt = f"{question} ({SCALE_HINT}): "
    while True:
        answer = input_fn(prompt).strip()
        if answer.isdigit() and 1 <= int(answer) <= 7:
            return int(answer)
        print("Please type a whole number from 1 to 7.")


def preview(scenarios: list[Scenario]) -> None:
    for scenario in scenarios:
        output = run_scenario(scenario)
        for condition in CONDITIONS:
            print(RULE)
            print(f"{scenario.scenario_id}  [{condition}]")
            print(RULE)
            print(render(scenario, output, condition))
            print()


def run_session(
    participant: int,
    scenarios: list[Scenario],
    input_fn: InputFn = input,
    log_dir: Path = LOG_DIR,
    clock: Callable[[], float] = time.monotonic,
) -> list[dict]:
    sequence = assign(participant, scenarios)
    rows = []
    with SessionLog(participant, log_dir) as log:
        print(f"Participant {participant}: {len(sequence)} scenarios.")
        print(f"Saving answers to {log.path}\n")
        for i, (scenario, condition) in enumerate(sequence, start=1):
            output = run_scenario(scenario)
            print(RULE)
            print(f"Scenario {i} of {len(sequence)}")
            print(RULE)
            print(render(scenario, output, condition))
            print()

            shown_at = clock()
            decision = ask_decision(decision_target(output), input_fn)
            decision_time = clock() - shown_at

            edit_note = ""
            if decision == "edit":
                edit_note = input_fn("What would you change? ").strip()
            trust = ask_rating(TRUST_QUESTION, input_fn)
            confidence = ask_rating(CONFIDENCE_QUESTION, input_fn)

            change = output.proposed_change or {}
            row = {
                "participant": participant,
                "position": i,
                "scenario_id": scenario.scenario_id,
                "condition": condition,
                "decided_on": "proposal" if output.has_proposal else "recommendation",
                "proposal_action": change.get("action", ""),
                "energy_level": output.energy_level,
                "recommended_task_type": output.recommended_task_type,
                "decision": decision,
                "edit_note": edit_note,
                "trust": trust,
                "confidence": confidence,
                "decision_time_s": round(decision_time, 2),
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            log.write(row)
            rows.append(row)
            print()
    print("Done, thank you!")
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m integration.evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preview", help="print every scenario in both conditions")
    run = sub.add_parser("run", help="run one participant's session")
    run.add_argument("--participant", type=int, required=True, help="1, 2, 3, ...")
    args = parser.parse_args(argv)

    if args.command == "preview":
        preview(PILOT_SCENARIOS)
    else:
        run_session(args.participant, PILOT_SCENARIOS)


if __name__ == "__main__":
    main()
