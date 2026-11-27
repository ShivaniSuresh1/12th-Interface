"""Evaluation harness: deterministic output, fair conditions, counterbalancing."""

import csv
from collections import Counter
from datetime import datetime

import pytest

from domain_model import TaskType
from domain_model.mapping import HIGH_ENERGY, LOW_ENERGY
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


# How close a scenario's energy may sit to a bucket cut point. Closer than this and a
# small change to the energy curve or check-in blend could flip its bucket, which
# changes the recommendation and explanation participants see.
CUT_POINT_MARGIN = 0.03


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.scenario_id)
def test_energy_is_not_near_a_bucket_cut_point(scenario):
    energy = run_scenario(scenario).energy_level
    for cut in (LOW_ENERGY, HIGH_ENERGY):
        assert abs(energy - cut) >= CUT_POINT_MARGIN, (
            f"{scenario.scenario_id}: energy {energy:.3f} is within {CUT_POINT_MARGIN} of {cut}"
        )


def test_survey_scenario_uses_the_survey_explanation():
    # s2 exists to show a survey-based explanation.
    (s2,) = [s for s in SCENARIOS if s.scenario_id == "s2_survey_preference"]
    out = run_scenario(s2)
    assert "you said you prefer" in out.why


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.scenario_id)
def test_energy_comes_from_shivanis_scenario(scenario):
    # Each harness scenario reuses one of user_model's fixed energy scenarios, so
    # participants see exactly the energy those scenarios pin down.
    from tests.user_model.scenarios import SCENARIOS as ENERGY_SCENARIOS

    (energy,) = [e for e in ENERGY_SCENARIOS if e.number == scenario.user_model_scenario]
    assert scenario.now.time() == energy.time_of_day
    assert scenario.sleep_hours == energy.sleep_hours
    assert scenario.checkin == energy.checkin_response
    out = run_scenario(scenario)
    assert out.energy_level == round(energy.energy_level, 3)
    assert out.energy_source == energy.source


def test_every_energy_scenario_is_used_once():
    from tests.user_model.scenarios import SCENARIOS as ENERGY_SCENARIOS

    used = sorted(s.user_model_scenario for s in SCENARIOS)
    assert used == sorted(e.number for e in ENERGY_SCENARIOS)


def _session_task_type(scenario, title):
    (event,) = [e for e in scenario.events if e.get("title") == title]
    return event["task_type"]


@pytest.mark.parametrize(
    "scenario", [s for s in SCENARIOS if s.disruption], ids=lambda s: s.scenario_id
)
def test_recommendation_matches_the_session_being_changed(scenario):
    # Found in the Phase 2 dry pass: s5/s6 recommended one task type while
    # rescheduling a session of another type, which reads as a contradiction.
    out = run_scenario(scenario)
    change = out.proposed_change
    if change["action"] == "ask":
        return  # no session is changed
    assert out.recommended_task_type == _session_task_type(scenario, change["title"])


def test_every_explanation_source_is_shown():
    whys = [run_scenario(s).why for s in SCENARIOS]
    assert any("starting default" in w and "outweighs" not in w for w in whys)  # default rule
    assert any("you said you prefer" in w for w in whys)  # survey answer
    assert any("outweighs the starting default" in w for w in whys)  # learned choices


def test_learned_history_matches_domain_models_learned_student():
    from integration.evaluation.scenarios import LEARNED_HISTORY
    from integration.evaluation.simulate import build_planner
    from tests.domain_model.pilot_recommendations import learned_student

    (s6,) = [s for s in SCENARIOS if s.scenario_id == "s6_missed_session"]
    ours, theirs = build_planner(s6).task_mapping, learned_student()
    for bucket in ("low", "medium", "high"):
        assert ours.choice_counts(bucket) == theirs.choice_counts(bucket)
    assert s6.history == LEARNED_HISTORY


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


# Participant 2 sees s2, s4 (ask), s6, s1, s3, s5. Per scenario: decision,
# [note after edit/reject, or after "y" on an ask], trust, confidence.
SESSION_ANSWERS = (
    "x", "a", "5", "6",                                  # s2: "x" is invalid and gets re-asked
    "e", "y", "my meeting ran late", "9", "3", "4",      # s4 ask: a/e/r keys aren't valid; "9" re-asked
    "r", "a shorter session", "2", "6",                  # s6: reject note
    "e", "make it shorter", "7", "7",                    # s1: edit note
    "a", "6", "5",                                       # s3
    "r", "", "1", "7",                                   # s5: reject note skipped with Enter
)


def _by_prompt(prompt):
    """Answer any session prompt sensibly, whatever order the scenarios come in."""
    if "[y/n]" in prompt:
        return "n"
    if "[a/e/r]" in prompt:
        return "a"
    if "1 = not at all" in prompt:
        return "4"
    return ""


def _fake_clock():
    ticks = iter(range(0, 1000, 2))  # each call is 2 "seconds" later
    return lambda: float(next(ticks))


def test_session_logs_every_answer(tmp_path, capsys):
    rows = run_session(
        2, SCENARIOS, input_fn=_answers(*SESSION_ANSWERS), log_dir=tmp_path, clock=_fake_clock(),
        with_survey=False,
    )
    assert [r["scenario_id"][:2] for r in rows] == ["s2", "s4", "s6", "s1", "s3", "s5"]
    assert [r["decision"] for r in rows] == ["accept", "accept", "reject", "edit", "accept", "reject"]
    assert [r["trust"] for r in rows] == [5, 3, 2, 7, 6, 1]
    assert [r["confidence"] for r in rows] == [6, 4, 6, 7, 5, 7]
    assert [r["note"] for r in rows] == [
        "", "my meeting ran late", "a shorter session", "make it shorter", "", "",
    ]
    assert all(r["decision_time_s"] == 2.0 for r in rows)
    out = capsys.readouterr().out
    assert "Please type a, e, or r." in out
    assert "Please type y or n." in out
    assert "Please type a whole number from 1 to 7." in out

    with log_path(2, tmp_path).open(newline="") as f:
        saved = list(csv.DictReader(f))
    assert len(saved) == 6
    assert set(saved[0]) == set(FIELDS)
    assert [r["scenario_id"] for r in saved] == [r["scenario_id"] for r in rows]


def test_log_records_what_was_decided_on(tmp_path):
    by_id = {s.scenario_id: s for s in SCENARIOS}
    rows = run_session(
        1, SCENARIOS, input_fn=_by_prompt,
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


def _same_answer_everywhere(participant, decision, trust, confidence):
    """Session answers for one participant who gives the same decision every time.

    "a" / "r" become "y" / "n" on the ask scenario; optional notes are skipped.
    """
    answers = []
    for scenario, _condition in assign(participant, SCENARIOS):
        is_ask = (run_scenario(scenario).proposed_change or {}).get("action") == "ask"
        if is_ask:
            answers.append({"a": "y", "r": "n"}[decision])
            if decision == "a":
                answers.append("")
        else:
            answers.append(decision)
            if decision == "r":
                answers.append("")
        answers += [trust, confidence]
    return tuple(answers)


def test_full_session_ends_with_the_survey(tmp_path):
    scenario_answers = _same_answer_everywhere(6, "a", "5", "5")
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


# -- analyze (Phase 2, step 7) ---------------------------------------------------


def _four_participants(log_dir):
    # One full counterbalancing cycle. Odd participants accept everything with
    # trust 6; even participants reject everything with trust 2.
    for participant in (1, 2, 3, 4):
        decision, trust = ("a", "6") if participant % 2 else ("r", "2")
        answers = _same_answer_everywhere(participant, decision, trust, "4")
        run_session(
            participant, SCENARIOS, input_fn=_answers(*answers, *SURVEY_ANSWERS),
            log_dir=log_dir, clock=_fake_clock(),
        )


def test_analyze_summarizes_conditions_and_survey(tmp_path, capsys):
    from integration.evaluation.analyze import load_rows, report, summarize

    _four_participants(tmp_path)
    rows = load_rows(tmp_path)
    assert len(rows) == 4 * len(SCENARIOS)  # survey files are not read as sessions

    for condition in ("explanation", "plain"):
        s = summarize(r for r in rows if r["condition"] == condition)
        assert s["n"] == 2 * len(SCENARIOS)  # each participant: half explained, half plain
        assert s["accept"] == s["reject"] == 0.5
        assert s["trust"] == 4.0
        assert s["time_median"] == 2.0

    text = report(tmp_path)
    assert "Participants: 4 (1, 2, 3, 4)" in text
    assert "| explanation | 12 | 50% | 0% | 50% | 4.00 |" in text
    for scenario in SCENARIOS:
        assert f"{scenario.scenario_id} / explanation" in text
    assert "## Exit survey" in text


def test_analyze_cli_reads_a_separate_log_dir(tmp_path, capsys):
    from integration.evaluation.__main__ import main

    _four_participants(tmp_path / "dry_run")
    capsys.readouterr()
    out = tmp_path / "report.md"
    main(["analyze", "--log-dir", str(tmp_path / "dry_run"), "--out", str(out)])
    assert "Participants: 4" in out.read_text()


def test_analyze_with_no_logs(tmp_path):
    from integration.evaluation.analyze import report

    assert "No session logs found yet." in report(tmp_path)


# -- dry-run fixes ---------------------------------------------------------------


def test_ask_scenario_never_asks_to_accept_a_change(tmp_path):
    prompts = []

    def record(prompt):
        prompts.append((len(prompts), prompt))
        return _by_prompt(prompt)

    rows = run_session(2, SCENARIOS, input_fn=record, log_dir=tmp_path, with_survey=False)
    ask_row = next(r for r in rows if r["proposal_action"] == "ask")
    assert ask_row["decision"] == "reject"  # "n": would rather the planner just decided
    decision_prompts = [p for _, p in prompts if "[a/e/r]" in p or "[y/n]" in p]
    assert sum("[y/n]" in p for p in decision_prompts) == 1
    assert not any("proposed change" in p and "[y/n]" in p for p in decision_prompts)


def test_trust_question_covers_rejected_suggestions():
    from integration.evaluation.__main__ import TRUST_QUESTION

    assert "even if you didn't go with it" in TRUST_QUESTION


def test_analyze_reads_old_edit_note_column(tmp_path):
    from integration.evaluation.analyze import report

    old_fields = [f if f != "note" else "edit_note" for f in FIELDS]
    path = log_path(1, tmp_path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=old_fields)
        writer.writeheader()
        writer.writerow({
            "participant": 1, "position": 1, "scenario_id": SCENARIOS[0].scenario_id,
            "condition": "plain", "decided_on": "recommendation", "proposal_action": "",
            "energy_level": 0.7, "recommended_task_type": "reading", "decision": "edit",
            "edit_note": "later please", "trust": 4, "confidence": 5,
            "decision_time_s": 3.0, "timestamp": "2026-11-25T20:00:00-06:00",
        })
    assert "later please" in report(tmp_path)


# -- simulated participants --------------------------------------------------------


def test_simulated_logs_are_marked_and_bannered(tmp_path):
    from integration.evaluation.analyze import load_rows, report
    from integration.evaluation.simulated import simulate

    simulate(4, seed=1, log_dir=tmp_path)
    assert (tmp_path / "SIMULATED.md").exists()
    assert len(load_rows(tmp_path)) == 4 * len(SCENARIOS)
    text = report(tmp_path)
    assert text.startswith("# SIMULATED results (not real participants)")
    assert "SIMULATED DATA" in text


def test_simulation_is_reproducible(tmp_path):
    from integration.evaluation.analyze import load_rows
    from integration.evaluation.simulated import simulate

    simulate(4, seed=7, log_dir=tmp_path / "a")
    simulate(4, seed=7, log_dir=tmp_path / "b")
    keep = ("scenario_id", "condition", "decision", "trust", "confidence", "decision_time_s")
    a = [[r[k] for k in keep] for r in load_rows(tmp_path / "a")]
    b = [[r[k] for k in keep] for r in load_rows(tmp_path / "b")]
    assert a == b


def test_real_logs_get_no_simulated_banner(tmp_path):
    from integration.evaluation.analyze import report

    _four_participants(tmp_path)
    assert "SIMULATED" not in report(tmp_path)
