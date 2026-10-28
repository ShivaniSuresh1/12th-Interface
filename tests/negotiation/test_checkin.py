from datetime import UTC, timedelta, timezone

from negotiation import (
    CheckinLog,
    CheckinWindow,
    ReplanProposal,
    compose_checkin_message,
    find_boundary,
    is_session_boundary,
    next_boundary,
    should_check_in,
)

from .conftest import at


def test_session_start_is_a_boundary(schedule):
    assert is_session_boundary(at(14), schedule)
    window = find_boundary(at(14), schedule)
    assert window.boundary_type == "start"
    assert window.student_id == "stu-1"


def test_within_tolerance_counts(schedule):
    assert is_session_boundary(at(14, 4), schedule)
    assert is_session_boundary(at(13, 56), schedule)
    assert not is_session_boundary(at(14, 6), schedule)


def test_mid_session_is_not_a_boundary(schedule):
    assert not is_session_boundary(at(14, 30), schedule)


def test_break_edges_are_break_boundaries(schedule):
    assert find_boundary(at(15, 9), schedule).boundary_type == "break"
    # 15:00 is both the end of s1 and the start of the break.
    assert find_boundary(at(15), schedule).boundary_type in {"end", "break"}


def test_session_end_is_a_boundary(schedule):
    assert find_boundary(at(16), schedule).boundary_type == "end"


def test_non_study_events_are_not_boundaries(schedule):
    assert not is_session_boundary(at(9), schedule)  # class start
    assert not is_session_boundary(at(17), schedule)  # meeting start


def test_accepts_list_dict_and_iso_strings(events):
    assert is_session_boundary(at(14), events)
    assert is_session_boundary(at(14), {"events": events})
    iso = [{"start": at(14).isoformat(), "end": at(15).isoformat(), "kind": "study"}]
    assert is_session_boundary(at(14), iso)


def test_events_without_kind_are_skipped():
    untagged = [{"start": at(14), "end": at(15)}, {"start": at(16), "end": at(17), "kind": ""}]
    assert not is_session_boundary(at(14), untagged)
    assert not is_session_boundary(at(16), untagged)


def test_mixed_timezones_keep_every_boundary():
    naive_local = at(14)
    aware = (at(16)).astimezone(UTC)  # 16:00 local, expressed in UTC
    events = [
        {"start": naive_local, "end": naive_local + timedelta(hours=1), "kind": "study"},
        {"start": aware, "end": aware + timedelta(hours=1), "kind": "study"},
    ]
    assert is_session_boundary(at(14), events)
    assert is_session_boundary(at(16), events)
    assert is_session_boundary(at(16).astimezone(UTC), events)


def test_unreadable_schedules_are_never_boundaries():
    assert not is_session_boundary(at(14), None)
    assert not is_session_boundary(at(14), object())
    assert not is_session_boundary(
        at(14), [{"start": "x", "kind": "study"}, "junk", {"end": at(15), "kind": "study"}]
    )
    # end before start is skipped
    assert not is_session_boundary(at(14), [{"start": at(15), "end": at(14), "kind": "study"}])


def test_timezone_aware_schedule():
    events = [
        {"start": at(14).replace(tzinfo=UTC), "end": at(15).replace(tzinfo=UTC), "kind": "study"}
    ]
    now_elsewhere = at(9).replace(tzinfo=timezone(timedelta(hours=-5)))  # == 14:00 UTC
    assert is_session_boundary(now_elsewhere, events)


def test_next_boundary(schedule):
    assert next_boundary(at(14, 30), schedule) == at(15)
    assert next_boundary(at(16, 30), schedule) is None


def test_daily_cap_is_enforced(schedule):
    log = CheckinLog(max_per_day=2)
    assert should_check_in(at(14), schedule, log) is not None
    assert should_check_in(at(15), schedule, log) is not None
    assert should_check_in(at(16), schedule, log) is None
    assert log.remaining_today("stu-1", at(16)) == 0


def test_same_boundary_only_checks_in_once(schedule):
    log = CheckinLog()
    assert should_check_in(at(14), schedule, log) is not None
    assert should_check_in(at(14, 3), schedule, log) is None
    assert log.count_on("stu-1", at(14).date()) == 1


def test_cap_resets_next_day(events):
    log = CheckinLog(max_per_day=1)
    assert should_check_in(at(14), events, log, student_id="stu-1") is not None
    tomorrow = [
        {**e, "start": e["start"] + timedelta(days=1), "end": e["end"] + timedelta(days=1)}
        for e in events
    ]
    assert should_check_in(at(14) + timedelta(days=1), tomorrow, log, "stu-1") is not None


def test_cap_is_per_student(events):
    log = CheckinLog(max_per_day=1)
    assert should_check_in(at(14), events, log, student_id="a") is not None
    assert should_check_in(at(14), events, log, student_id="b") is not None


def test_no_window_off_boundary_and_nothing_recorded(schedule):
    log = CheckinLog()
    assert should_check_in(at(14, 30), schedule, log) is None
    assert log.count_on("stu-1", at(14).date()) == 0


def test_message_batches_checkin_and_replan():
    window = CheckinWindow("stu-1", "break", at(15))
    alone = compose_checkin_message(window)
    assert "energy" in alone

    proposal = ReplanProposal("stu-1", "fatigue", "I'd shorten your next session.", {})
    batched = compose_checkin_message(window, proposal)
    assert alone in batched
    assert proposal.message in batched
