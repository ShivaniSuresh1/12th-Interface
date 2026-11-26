import pytest

from negotiation import (
    confirmation_message,
    interpret_answer,
    propose_replan,
    resolve_answer,
    run_ask_flow,
    training_example,
)
from negotiation.replanning import ASK_PROMPT, ReplanProposal

from .conftest import at, make_profile


@pytest.fixture
def ask_proposal():
    return ReplanProposal(
        "stu-1",
        "fatigue",
        f"I'm not sure what's best. {ASK_PROMPT}",
        {"action": "ask", "confidence": 0.3, "energy_level": 0.72},
    )


# --- reading the answer ------------------------------------------------


@pytest.mark.parametrize(
    "answer, action, minutes, when",
    [
        ("I'm exhausted, can't focus", "shorten", 25, None),
        ("tired, just 15 minutes please", "shorten", 15, None),
        ("only half an hour", "shorten", 30, None),
        ("my meeting ran 20 min late", "move", 20, None),
        ("running late", "move", None, None),
        ("I missed it, had an errand", "defer", None, "later"),
        ("move it to tomorrow", "defer", None, "tomorrow"),
        ("I'm tired, let's do it tomorrow", "defer", None, "tomorrow"),
        ("can we push it later", "defer", None, "later"),
        ("no energy today", "shorten", 25, None),
        ("tired after the gym", "shorten", 25, None),
        ("honestly I'm wiped, 20 minutes max", "shorten", 20, None),
        ("20 minutes", "shorten", 20, None),
    ],
)
def test_interpret_answer_actions(answer, action, minutes, when):
    change = interpret_answer(answer)
    assert change["action"] == action
    assert change["minutes"] == minutes
    assert change["when"] == when
    assert change["answer"] == answer


@pytest.mark.parametrize(
    "answer, task_type",
    [
        ("tired, switch to flashcards", "memorization"),
        ("I'd rather do some reading", "reading"),
        ("let me review my notes instead", "review"),
        ("do the problem set instead", "problem_set"),
        ("homework", "problem_set"),
    ],
)
def test_interpret_answer_task_types(answer, task_type):
    assert interpret_answer(answer)["task_type"] == task_type


def test_named_task_alone_is_a_swap():
    assert interpret_answer("flashcards instead")["action"] == "swap"


def test_already_does_not_count_as_reading():
    assert interpret_answer("I already finished, I'm exhausted")["task_type"] is None


@pytest.mark.parametrize("answer", ["", "   ", "never mind", "Nope.", "nothing", "all good!"])
def test_nothing_to_act_on(answer):
    assert interpret_answer(answer) is None


def test_unreadable_answer_is_kept_as_a_note():
    change = interpret_answer("my roommate is having a party")
    assert change["action"] == "note"
    assert change["answer"] == "my roommate is having a party"


# --- resolving ---------------------------------------------------------


def test_answer_becomes_an_edited_resolution(ask_proposal):
    resolution = resolve_answer(ask_proposal, "exhausted, switch to reading")
    assert resolution.outcome == "edited"
    assert resolution.edited_change["action"] == "shorten"
    assert resolution.edited_change["task_type"] == "reading"
    assert resolution.proposal is ask_proposal


def test_never_mind_leaves_the_plan_alone(ask_proposal):
    resolution = resolve_answer(ask_proposal, "never mind")
    assert resolution.outcome == "rejected"
    assert resolution.edited_change is None


def test_answer_feeds_learning(ask_proposal):
    example = training_example(resolve_answer(ask_proposal, "tired, flashcards instead"))
    assert example["chosen_task_type"] == "memorization"
    assert example["energy_level"] == 0.72
    assert example["outcome"] == "edited"


# --- telling the student what happens ----------------------------------


@pytest.mark.parametrize(
    "answer, expected",
    [
        ("exhausted", "keep your session to 25 minutes"),
        ("tired, switch to flashcards", "25 minutes and switch to memorization"),
        ("meeting ran 20 min late", "push your session back 20 minutes"),
        ("running late", "until you're ready"),
        ("do it tomorrow", "move it to tomorrow"),
        ("I missed it", "move it to later today"),
        ("problem set instead", "switch your session to a problem set"),
        ("my roommate is having a party", "leave your plan as it is"),
        ("never mind", "leave your plan as it is"),
    ],
)
def test_confirmation_is_always_narrated(ask_proposal, answer, expected):
    message = confirmation_message(resolve_answer(ask_proposal, answer))
    assert expected in message


# --- interactive flow --------------------------------------------------


def test_run_ask_flow_asks_resolves_and_confirms(ask_proposal):
    said = []
    resolution = run_ask_flow(ask_proposal, ask=lambda prompt: "exhausted", say=said.append)
    assert said[0] == ask_proposal.message
    assert "25 minutes" in said[1]
    assert resolution.outcome == "edited"


def test_run_ask_flow_cancel_changes_nothing(ask_proposal):
    def cancel(prompt):
        raise EOFError

    with pytest.raises(EOFError):
        run_ask_flow(ask_proposal, ask=cancel, say=lambda *a: None)


def test_run_ask_flow_rejects_concrete_proposals():
    proposal = ReplanProposal("s", "fatigue", "I'd shorten it.", {"action": "shorten"})
    with pytest.raises(ValueError):
        run_ask_flow(proposal, ask=lambda p: "ok", say=lambda *a: None)


def test_end_to_end_from_a_real_ask_proposal(schedule, freeze_now):
    freeze_now(at(14, 10))
    proposal = propose_replan(make_profile(schedule, energy=0.9), "fatigue")
    assert proposal.proposed_change["action"] == "ask"  # confidence logic unchanged

    said = []
    resolution = run_ask_flow(
        proposal, ask=lambda p: "honestly I'm wiped, 20 minutes max", say=said.append
    )
    assert resolution.outcome == "edited"
    assert resolution.edited_change["action"] == "shorten"
    assert resolution.edited_change["minutes"] == 20
    assert "20 minutes" in said[-1]


def test_pilot_ask_scenario_works_with_the_flow():
    from integration.evaluation.scenarios import PILOT_SCENARIOS
    from integration.evaluation.simulate import run_scenario

    scenario = next(s for s in PILOT_SCENARIOS if s.scenario_id == "s4_signals_disagree_ask")
    out = run_scenario(scenario)
    proposal = ReplanProposal(
        scenario.scenario_id, scenario.disruption, out.proposal_message, out.proposed_change
    )
    resolution = run_ask_flow(
        proposal, ask=lambda p: "I'm tired, switch to review", say=lambda *a: None
    )
    assert resolution.edited_change["task_type"] == "review"
