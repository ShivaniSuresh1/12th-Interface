"""Guard the replan paths the pilot scenarios rely on.

The pilot's scenario set is meant to show participants every replan path
(see integration.evaluation.scenarios). If a change in any module flips
one of these to a different action, the pilot quietly stops covering it,
so fail loudly here instead.
"""

import pytest

from integration.evaluation.scenarios import PILOT_SCENARIOS
from integration.evaluation.simulate import run_scenario
from negotiation.replanning import ASK_PROMPT, RESPONSE_HINT

EXPECTED_ACTION = {
    "s3_short_night_fatigue": "shorten",
    "s4_signals_disagree_ask": "ask",
    "s5_meeting_ran_late": "move",
    "s6_missed_session": "defer",
}

DISRUPTED = [s for s in PILOT_SCENARIOS if s.disruption]


def test_expected_actions_cover_every_disruption_scenario():
    assert {s.scenario_id for s in DISRUPTED} == set(EXPECTED_ACTION)


@pytest.mark.parametrize("scenario", DISRUPTED, ids=lambda s: s.scenario_id)
def test_pilot_scenario_gets_its_replan_path(scenario):
    out = run_scenario(scenario)
    action = out.proposed_change["action"]
    assert action == EXPECTED_ACTION[scenario.scenario_id]
    assert out.proposal_message.strip()
    if action == "ask":
        assert ASK_PROMPT in out.proposal_message
    else:
        assert RESPONSE_HINT in out.proposal_message
        assert out.proposed_change["title"] in out.proposal_message


def test_pilot_proposals_doc_is_generated():
    from .pilot_proposals import OUT

    text = OUT.read_text()
    for scenario_id in EXPECTED_ACTION:
        assert scenario_id in text
