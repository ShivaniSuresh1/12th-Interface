"""Evaluation harness: deterministic output, fair conditions, counterbalancing."""

import csv
from collections import Counter
from datetime import datetime

import pytest

from domain_model import TaskType
from integration.evaluation.__main__ import run_session
from integration.evaluation.log import FIELDS, SessionLog, log_path
from integration.evaluation.present import assign, plain_change, render
from integration.evaluation.scenarios import PILOT_SCENARIOS
from integration.evaluation.simulate import run_scenario
from integration.evaluation.survey import QUESTIONS, run_survey, survey_path

SCENARIOS = PILOT_SCENARIOS


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


def _answers(*values):
    it = iter(values)
    return lambda _prompt: next(it)


# Per scenario: decision, [edit note if "e"], trust, confidence.
SESSION_ANSWERS = (
    "x", "a", "5", "6",            # "x" is invalid and gets re-asked
    "e", "make it shorter", "9", "3", "4",  # "9" is out of range and gets re-asked
    "r", "2", "6",
    "a", "7", "7",
    "a", "6", "5",
    "r", "1", "7",
)


def _fake_clock():
    ticks = iter(range(0, 1000, 2))  # each call is 2 "seconds" later
    return lambda: float(next(ticks))


def test_session_logs_every_answer(tmp_path, capsys):
    rows = run_session(
        2, SCENARIOS, input_fn=_answers(*SESSION_ANSWERS), log_dir=tmp_path, clock=_fake_clock(),
        with_survey=False,
    )
    assert [r["decision"] for r in rows] == ["accept", "edit", "reject", "accept", "accept", "reject"]
    assert [r["trust"] for r in rows] == [5, 3, 2, 7, 6, 1]
    assert [r["confidence"] for r in rows] == [6, 4, 6, 7, 5, 7]
    assert rows[1]["edit_note"] == "make it shorter"
    assert all(r["decision_time_s"] == 2.0 for r in rows)
    out = capsys.readouterr().out
    assert "Please type a, e, or r." in out
    assert "Please type a whole number from 1 to 7." in out

    with log_path(2, tmp_path).open(newline="") as f:
        saved = list(csv.DictReader(f))
    assert len(saved) == 6
    assert set(saved[0]) == set(FIELDS)
    assert [r["scenario_id"] for r in saved] == [r["scenario_id"] for r in rows]


def test_log_records_what_was_decided_on(tmp_path):
    by_id = {s.scenario_id: s for s in SCENARIOS}
    rows = run_session(
        1, SCENARIOS, input_fn=_answers(*SESSION_ANSWERS),
        log_dir=tmp_path, clock=_fake_clock(), with_survey=False,
    )
    for r in rows:
        has_disruption = by_id[r["scenario_id"]].disruption is not None
        assert r["decided_on"] == ("proposal" if has_disruption else "recommendation")
        assert (r["proposal_action"] != "") == has_disruption


def test_rows_survive_a_session_that_quits_early(tmp_path):
    def quit_on_second_scenario(prompt):
        if quit_on_second_scenario.calls == 3:
            raise KeyboardInterrupt
        quit_on_second_scenario.calls += 1
        return ["a", "5", "5"][quit_on_second_scenario.calls - 1]

    quit_on_second_scenario.calls = 0
    with pytest.raises(KeyboardInterrupt):
        run_session(3, SCENARIOS, input_fn=quit_on_second_scenario, log_dir=tmp_path)
    with log_path(3, tmp_path).open(newline="") as f:
        assert len(list(csv.DictReader(f))) == 1


def test_refuses_to_overwrite_an_existing_participant(tmp_path):
    SessionLog(4, tmp_path).close()
    with pytest.raises(FileExistsError):
        SessionLog(4, tmp_path)


# One valid answer per survey question: 6 Likert, 1 choice, 2 free text.
SURVEY_ANSWERS = ("6", "5", "7", "6", "8", "7", "4", "1", "the 41% felt odd", "")


def test_survey_saves_one_row_per_question(tmp_path, capsys):
    answers = run_survey(5, input_fn=_answers(*SURVEY_ANSWERS), log_dir=tmp_path)
    assert answers["trust_with_why"] == "7"  # "8" was out of range and re-asked
    assert answers["preferred_version"] == "with explanation"
    assert answers["confusing"] == "the 41% felt odd"
    assert answers["change_one_thing"] == ""  # Enter skips a free-text question
    assert "Please type a whole number from 1 to 7." in capsys.readouterr().out

    with survey_path(5, tmp_path).open(newline="") as f:
        saved = list(csv.DictReader(f))
    assert [r["question_id"] for r in saved] == [q.question_id for q in QUESTIONS]


def test_full_session_ends_with_the_survey(tmp_path):
    scenario_answers = ("a", "5", "5") * len(SCENARIOS)
    run_session(
        6, SCENARIOS, input_fn=_answers(*scenario_answers, *SURVEY_ANSWERS),
        log_dir=tmp_path, clock=_fake_clock(),
    )
    assert log_path(6, tmp_path).exists()
    assert survey_path(6, tmp_path).exists()


def test_survey_refuses_to_overwrite(tmp_path):
    run_survey(7, input_fn=_answers(*SURVEY_ANSWERS), log_dir=tmp_path)
    with pytest.raises(FileExistsError):
        run_survey(7, input_fn=_answers(*SURVEY_ANSWERS), log_dir=tmp_path)
