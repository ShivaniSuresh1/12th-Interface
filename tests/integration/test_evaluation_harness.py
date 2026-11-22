"""Evaluation harness: deterministic output, fair conditions, counterbalancing."""

from collections import Counter
from datetime import datetime

import pytest

from domain_model import TaskType
from integration.evaluation.__main__ import run_session
from integration.evaluation.present import assign, plain_change, render
from integration.evaluation.scenarios import PLACEHOLDER_SCENARIOS
from integration.evaluation.simulate import run_scenario

SCENARIOS = PLACEHOLDER_SCENARIOS


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.scenario_id)
def test_every_scenario_runs_through_the_planner(scenario):
    out = run_scenario(scenario)
    assert 0.0 <= out.energy_level <= 1.0
    TaskType(out.recommended_task_type)  # a valid task type
    assert out.why
    assert out.has_proposal == (scenario.disruption is not None)
    if scenario.checkin:
        assert out.energy_source == "checkin_corrected"


def test_output_does_not_depend_on_the_real_clock():
    # Same scenario, run twice: identical output (clock is frozen at scenario.now).
    assert run_scenario(SCENARIOS[1]) == run_scenario(SCENARIOS[1])


def test_clock_is_restored_after_a_run():
    import user_model.energy_estimate as ee

    run_scenario(SCENARIOS[0])
    assert ee.datetime is datetime


def test_plain_condition_hides_every_explanation():
    for scenario in SCENARIOS:
        out = run_scenario(scenario)
        plain = render(scenario, out, "plain")
        explained = render(scenario, out, "explanation")
        assert out.why not in plain
        assert out.why in explained
        if out.has_proposal:
            assert out.proposal_message in explained
            assert out.proposal_message not in plain
            assert plain_change(out.proposed_change) in plain


def test_both_conditions_show_the_same_recommendation():
    scenario = SCENARIOS[0]
    out = run_scenario(scenario)
    label = TaskType(out.recommended_task_type).label
    for condition in ("explanation", "plain"):
        assert f"Recommended next task type: {label}" in render(scenario, out, condition)


def test_everyone_sees_every_scenario_once_in_both_conditions():
    for participant in range(1, 9):
        seq = assign(participant, SCENARIOS)
        assert sorted(s.scenario_id for s, _ in seq) == sorted(s.scenario_id for s in SCENARIOS)
        assert Counter(c for _, c in seq) == {"explanation": 3, "plain": 3}


def test_counterbalancing_over_four_participants():
    first_conditions = Counter()
    explained = Counter()
    for participant in range(1, 5):
        seq = assign(participant, SCENARIOS)
        first_conditions[seq[0][1]] += 1
        explained.update(s.scenario_id for s, c in seq if c == "explanation")
    assert first_conditions == {"explanation": 2, "plain": 2}
    # every scenario is explained for exactly half of the participants
    assert set(explained.values()) == {2}


def test_session_records_one_decision_per_scenario(capsys):
    answers = iter(["x", "a", "e", "r", "a", "a", "r"])  # "x" is invalid, re-asked
    results = run_session(2, SCENARIOS, input_fn=lambda _prompt: next(answers))
    assert [r["decision"] for r in results] == ["accept", "edit", "reject", "accept", "accept", "reject"]
    assert [r["position"] for r in results] == list(range(1, 7))
    assert "Please type a, e, or r." in capsys.readouterr().out
