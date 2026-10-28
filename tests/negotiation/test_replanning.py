from datetime import datetime

import pytest

from negotiation import propose_replan, resolve_proposal, training_example
from negotiation.replanning import ASK_PROMPT, ReplanProposal

from .conftest import at, make_profile


def _times(proposal):
    change = proposal.proposed_change
    return datetime.fromisoformat(change["new_start"]), datetime.fromisoformat(change["new_end"])


# --- fatigue -----------------------------------------------------------


def test_low_energy_shortens_current_session(schedule, freeze_now):
    freeze_now(at(14, 10))
    proposal = propose_replan(make_profile(schedule, energy=0.25), "fatigue")
    assert proposal.proposed_change["action"] == "shorten"
    assert proposal.proposed_change["session_id"] == "s1"
    assert _times(proposal) == (at(14, 10), at(14, 35))
    assert "Linear algebra problem set" in proposal.message


def test_medium_energy_takes_a_break_first(schedule, freeze_now):
    freeze_now(at(14, 10))
    proposal = propose_replan(make_profile(schedule, energy=0.5), "tired")
    assert proposal.proposed_change["action"] == "move"
    assert _times(proposal) == (at(14, 20), at(15, 10))


def test_very_low_energy_defers_to_a_later_free_slot(schedule, freeze_now):
    freeze_now(at(14, 10))
    proposal = propose_replan(make_profile(schedule, energy=0.1), "fatigue")
    assert proposal.proposed_change["action"] == "defer"
    # 50 minutes left; first gap that fits after resting is 16:00-17:00.
    assert _times(proposal) == (at(16), at(16, 50))


def test_fatigue_with_high_energy_estimate_asks(schedule, freeze_now):
    freeze_now(at(14, 10))
    proposal = propose_replan(make_profile(schedule, energy=0.9), "fatigue")
    assert proposal.proposed_change["action"] == "ask"
    assert ASK_PROMPT in proposal.message


def test_fatigue_without_estimate_trusts_the_report(schedule, freeze_now):
    freeze_now(at(14, 10))
    proposal = propose_replan(make_profile(schedule), "fatigue")
    assert proposal.proposed_change["action"] == "shorten"
    assert proposal.proposed_change["confidence"] < 0.8


# --- running late ------------------------------------------------------


def test_running_late_moves_session(schedule, freeze_now):
    freeze_now(at(15, 5))
    proposal = propose_replan(make_profile(schedule), "running_late:10")
    assert proposal.proposed_change["action"] == "move"
    assert proposal.proposed_change["session_id"] == "s2"
    assert _times(proposal) == (at(15, 20), at(16, 10))
    assert "10 minutes" in proposal.message


def test_running_late_shortens_when_next_event_is_in_the_way(schedule, freeze_now):
    freeze_now(at(13, 50))
    proposal = propose_replan(make_profile(schedule), "meeting_ran_late:20")
    assert proposal.proposed_change["action"] == "shorten"
    assert _times(proposal) == (at(14, 20), at(15))


def test_running_very_late_defers(schedule, freeze_now):
    freeze_now(at(13, 50))
    proposal = propose_replan(make_profile(schedule), "meeting_ran_late:50")
    assert proposal.proposed_change["action"] == "defer"
    assert _times(proposal) == (at(16), at(17))


def test_running_late_without_minutes_uses_default(schedule, freeze_now):
    freeze_now(at(15, 5))
    proposal = propose_replan(make_profile(schedule), "Meeting Ran Late")
    assert proposal.proposed_change["action"] == "move"
    assert _times(proposal) == (at(15, 25), at(16, 15))
    assert proposal.trigger == "Meeting Ran Late"  # original trigger preserved


# --- missed session ----------------------------------------------------


def test_missed_session_is_made_up_today(schedule, freeze_now):
    freeze_now(at(15, 5))
    proposal = propose_replan(make_profile(schedule), "missed_session")
    assert proposal.proposed_change["action"] == "defer"
    assert proposal.proposed_change["session_id"] == "s1"
    assert _times(proposal) == (at(16), at(17))
    assert "today" in proposal.message


def test_missed_session_goes_to_tomorrow_when_day_is_full(events, freeze_now):
    freeze_now(at(21, 30))
    proposal = propose_replan(make_profile(events), "missed")
    assert proposal.proposed_change["session_id"] == "s2"
    start, _ = _times(proposal)
    assert start.date() > at(0).date()
    assert "tomorrow" in proposal.message


# --- fallback ----------------------------------------------------------


@pytest.mark.parametrize("trigger", ["fatigue", "running_late", "missed_session", "aliens"])
def test_no_schedule_falls_back_to_asking(trigger, freeze_now):
    freeze_now(at(14))
    proposal = propose_replan(make_profile(None), trigger)
    assert proposal.proposed_change["action"] == "ask"
    assert ASK_PROMPT in proposal.message


def test_unknown_trigger_asks(schedule, freeze_now):
    freeze_now(at(14))
    proposal = propose_replan(make_profile(schedule, energy=0.5), "roommate_party")
    assert proposal.proposed_change["action"] == "ask"
    assert "roommate_party" in proposal.message


@pytest.mark.parametrize("energy", [None, 0.1, 0.25, 0.5, 0.9])
@pytest.mark.parametrize(
    "trigger", ["fatigue", "meeting_ran_late:20", "running_late", "missed_session", "???"]
)
@pytest.mark.parametrize("hour", [8, 13, 14, 15, 23])
def test_every_proposal_is_narrated(schedule, freeze_now, energy, trigger, hour):
    freeze_now(at(hour))
    proposal = propose_replan(make_profile(schedule, energy=energy), trigger)
    assert proposal.message.strip()
    assert proposal.student_id == "stu-1"
    assert proposal.proposed_change["action"] in {"move", "shorten", "defer", "ask"}


def test_works_with_real_user_model_profile(freeze_now):
    from user_model import EnergyReport, StudentProfile, StudentSchedule

    freeze_now(at(14, 10))
    profile = StudentProfile(
        student_id="real",
        schedule=StudentSchedule("real", [{"start": at(14), "end": at(15), "kind": "study"}]),
        energy_history=[EnergyReport("real", at(14), 0.2, "checkin_corrected")],
    )
    proposal = propose_replan(profile, "fatigue")
    assert proposal.student_id == "real"
    assert proposal.proposed_change["action"] in {"shorten", "defer"}


def test_profile_without_student_id():
    proposal = propose_replan(object(), "fatigue")
    assert proposal.student_id == "unknown"
    assert proposal.message


# --- resolution --------------------------------------------------------


@pytest.fixture
def proposal():
    return ReplanProposal(
        "stu-1",
        "fatigue",
        "I'd shorten it.",
        {"action": "shorten", "task_type": "problem_set", "energy_level": 0.25},
    )


@pytest.mark.parametrize("response", ["accept", "Yes", " ok ", "sounds good", "👍"])
def test_accept_synonyms(proposal, response):
    assert resolve_proposal(proposal, response).outcome == "accepted"


@pytest.mark.parametrize("response", ["reject", "no", "Skip", "keep"])
def test_reject_synonyms(proposal, response):
    assert resolve_proposal(proposal, response).outcome == "rejected"


def test_edit(proposal):
    change = {"task_type": "reading"}
    resolution = resolve_proposal(proposal, "edit", change)
    assert resolution.outcome == "edited"
    assert resolution.edited_change == change


def test_supplying_a_change_counts_as_edit(proposal):
    assert resolve_proposal(proposal, "accept", {"minutes": 40}).outcome == "edited"


def test_rejection_drops_edited_change(proposal):
    resolution = resolve_proposal(proposal, "no", {"minutes": 40})
    assert resolution.outcome == "rejected"
    assert resolution.edited_change is None


@pytest.mark.parametrize("response", ["", "maybe?", "asdf"])
def test_unclear_response_never_applies_a_change(proposal, response):
    assert resolve_proposal(proposal, response).outcome == "rejected"


# --- learning hand-off -------------------------------------------------


def test_training_example_on_accept(proposal):
    example = training_example(resolve_proposal(proposal, "accept"))
    assert example["chosen_task_type"] == "problem_set"
    assert example["energy_level"] == 0.25
    assert example["outcome"] == "accepted"


def test_training_example_on_edit_uses_edited_type(proposal):
    example = training_example(resolve_proposal(proposal, "edit", {"task_type": "reading"}))
    assert example["chosen_task_type"] == "reading"


def test_training_example_on_reject_has_no_choice(proposal):
    example = training_example(resolve_proposal(proposal, "reject"))
    assert example["chosen_task_type"] is None
    assert example["outcome"] == "rejected"


def test_training_example_feeds_domain_model(proposal):
    from domain_model import StudentTaskMapping, TaskType

    mapping = StudentTaskMapping("stu-1")
    example = training_example(resolve_proposal(proposal, "accept"))
    mapping.record_choice(example["energy_level"], TaskType(example["chosen_task_type"]))
    assert mapping.preferences["low"] == TaskType.PROBLEM_SET
