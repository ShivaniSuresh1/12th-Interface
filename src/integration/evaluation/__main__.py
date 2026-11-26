"""Evaluation harness command line.

From the repo root:

    PYTHONPATH=src python -m integration.evaluation preview
        Print every scenario in both conditions (for checking content).

    PYTHONPATH=src python -m integration.evaluation run --participant 3
        Run one participant's session in their counterbalanced order, then
        the exit survey. Answers are saved as they go to
        eval_logs/participant_03.csv and eval_logs/participant_03_survey.csv.

    PYTHONPATH=src python -m integration.evaluation survey --participant 3
        Run only the exit survey (e.g. if a session was interrupted after
        the scenarios).

    PYTHONPATH=src python -m integration.evaluation analyze [--out FILE]
        Descriptive summary of every log so far (Markdown).

    PYTHONPATH=src python -m integration.evaluation simulate [--n 8] [--seed 634]
        SIMULATED participants (a response model, not people) written to
        eval_logs/simulated/, to demo the pipeline. See simulated.py.

Add --log-dir DIR to run/survey/analyze to keep a team dry-run out of the
real pilot data, e.g. --log-dir eval_logs/dry_run.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .analyze import report
from .log import LOG_DIR, SessionLog
from .present import CONDITIONS, assign, decision_target, render
from .scenarios import PILOT_SCENARIOS, Scenario
from .simulate import run_scenario
from .survey import run_survey

DECISIONS = {"a": "accept", "e": "edit", "r": "reject"}
# For an "ask" proposal there is no change to accept/edit/reject: the planner
# asks a question. y/n is logged as accept/reject so analysis stays the same
# ("accept" = happy to be asked, "reject" = would rather it just decided).
ASK_DECISIONS = {"y": "accept", "n": "reject"}
RULE = "-" * 70

TRUST_QUESTION = "How much do you trust the planner's suggestion here, even if you didn't go with it?"
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


def ask_answer_question(input_fn: InputFn = input) -> str:
    prompt = "The planner is asking you what changed. Would you answer its question? [y/n]: "
    while True:
        answer = input_fn(prompt).strip().lower()[:1]
        if answer in ASK_DECISIONS:
            return ASK_DECISIONS[answer]
        print("Please type y or n.")


NOTE_PROMPTS = {
    # (is_ask, decision) -> follow-up question; Enter skips the optional ones
    (False, "edit"): "What would you change? ",
    (False, "reject"): "What would you prefer instead? (optional, press Enter to skip) ",
    (True, "accept"): "What would you tell the planner? (optional, press Enter to skip) ",
}


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
    with_survey: bool = True,
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

            change = output.proposed_change or {}
            is_ask = change.get("action") == "ask"

            shown_at = clock()
            if is_ask:
                decision = ask_answer_question(input_fn)
            else:
                decision = ask_decision(decision_target(output), input_fn)
            decision_time = clock() - shown_at

            note = ""
            if (is_ask, decision) in NOTE_PROMPTS:
                note = input_fn(NOTE_PROMPTS[(is_ask, decision)]).strip()
            trust = ask_rating(TRUST_QUESTION, input_fn)
            confidence = ask_rating(CONFIDENCE_QUESTION, input_fn)

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
                "note": note,
                "trust": trust,
                "confidence": confidence,
                "decision_time_s": round(decision_time, 2),
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            log.write(row)
            rows.append(row)
            print()
    if with_survey:
        run_survey(participant, input_fn, log_dir)
    print("Done, thank you!")
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m integration.evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preview", help="print every scenario in both conditions")
    run = sub.add_parser("run", help="run one participant's session")
    run.add_argument("--participant", type=int, required=True, help="1, 2, 3, ...")
    survey = sub.add_parser("survey", help="run only the exit survey")
    survey.add_argument("--participant", type=int, required=True, help="1, 2, 3, ...")
    analyze = sub.add_parser("analyze", help="summarize the logs so far (Markdown)")
    analyze.add_argument("--out", type=Path, help="write the report here instead of printing")
    sim = sub.add_parser("simulate", help="generate SIMULATED participants (not real data)")
    sim.add_argument("--n", type=int, default=8, help="number of simulated participants")
    sim.add_argument("--seed", type=int, default=634)
    for p in (run, survey, analyze, sim):
        p.add_argument(
            "--log-dir", type=Path, default=LOG_DIR, help=f"where logs live (default {LOG_DIR})"
        )
    args = parser.parse_args(argv)

    if args.command == "simulate":
        import contextlib
        import io

        from .simulated import SIM_DIR, simulate

        log_dir = SIM_DIR if args.log_dir == LOG_DIR else args.log_dir
        with contextlib.redirect_stdout(io.StringIO()):
            simulate(args.n, args.seed, log_dir)
        print(f"wrote {args.n} SIMULATED participants to {log_dir} (not real data)")
        print(f"next: PYTHONPATH=src python -m integration.evaluation analyze --log-dir {log_dir}")
    elif args.command == "preview":
        preview(PILOT_SCENARIOS)
    elif args.command == "survey":
        run_survey(args.participant, log_dir=args.log_dir)
        print("Done, thank you!")
    elif args.command == "analyze":
        text = report(args.log_dir)
        if args.out:
            args.out.write_text(text, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(text, end="")
    else:
        run_session(args.participant, PILOT_SCENARIOS, log_dir=args.log_dir)


if __name__ == "__main__":
    main()
