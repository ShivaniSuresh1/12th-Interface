"""Guards the pilot scenarios: they must keep spanning all three energy buckets."""

from __future__ import annotations

from tests.user_model.scenarios import SCENARIOS, build_scenarios


def test_scenarios_span_all_buckets():
    assert {s.bucket for s in SCENARIOS} == {"low", "medium", "high"}


def test_scenarios_are_deterministic():
    assert [s.as_dict() for s in build_scenarios()] == [s.as_dict() for s in SCENARIOS]


def test_no_checkin_scenario_stays_baseline():
    skipped = [s for s in SCENARIOS if s.checkin_response is None]
    assert skipped and all(s.source == "baseline" for s in skipped)
