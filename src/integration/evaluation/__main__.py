"""Evaluation harness command line.

From the repo root:

    PYTHONPATH=src python -m integration.evaluation preview
        Print every scenario in both conditions (for checking content).

    PYTHONPATH=src python -m integration.evaluation run --participant 3
        Run one participant's session in their counterbalanced order.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

from .present import CONDITIONS, assign, decision_target, render
from .scenarios import PLACEHOLDER_SCENARIOS, Scenario
from .simulate import run_scenario

DECISIONS = {"a": "accept", "e": "edit", "r": "reject"}
RULE = "-" * 70


def ask_decision(target: str, input_fn: Callable[[str], str] = input) -> str:
    prompt = f"Do you accept, edit, or reject {target}? [a/e/r]: "
    while True:
        answer = input_fn(prompt).strip().lower()[:1]
        if answer in DECISIONS:
            return DECISIONS[answer]
        print("Please type a, e, or r.")


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
    input_fn: Callable[[str], str] = input,
) -> list[dict]:
    sequence = assign(participant, scenarios)
    results = []
    print(f"Participant {participant}: {len(sequence)} scenarios.\n")
    for i, (scenario, condition) in enumerate(sequence, start=1):
        output = run_scenario(scenario)
        print(RULE)
        print(f"Scenario {i} of {len(sequence)}")
        print(RULE)
        print(render(scenario, output, condition))
        print()
        decision = ask_decision(decision_target(output), input_fn)
        results.append(
            {
                "participant": participant,
                "position": i,
                "scenario_id": scenario.scenario_id,
                "condition": condition,
                "decision": decision,
            }
        )
        print()
    print("Done, thank you!")
    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m integration.evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preview", help="print every scenario in both conditions")
    run = sub.add_parser("run", help="run one participant's session")
    run.add_argument("--participant", type=int, required=True, help="1, 2, 3, ...")
    args = parser.parse_args(argv)

    if args.command == "preview":
        preview(PLACEHOLDER_SCENARIOS)
    else:
        run_session(args.participant, PLACEHOLDER_SCENARIOS)


if __name__ == "__main__":
    main()
