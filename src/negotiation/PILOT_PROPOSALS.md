# Pilot replan proposals

Generated from `integration.evaluation.PILOT_SCENARIOS` by
`tests/negotiation/pilot_proposals.py`. Every message below is the real
output of `propose_replan()` for that scenario, not hand-written.
Regenerate after changing negotiation or the scenarios:

```bash
PYTHONPATH=src python -m tests.negotiation.pilot_proposals
```

| Scenario | Trigger | Energy | Action | Session | Change |
|---|---|---|---|---|---|
| `s3_short_night_fatigue` | `fatigue` | 0.25 (checkin_corrected) | shorten | Biology reading | 2:00 PM-3:00 PM -> 2:00 PM-2:25 PM |
| `s4_signals_disagree_ask` | `fatigue` | 0.72 (checkin_corrected) | ask | - | asks the student |
| `s5_meeting_ran_late` | `meeting_ran_late:20` | 0.61 (checkin_corrected) | move | Data structures problem set | 4:00 PM-5:00 PM -> 4:20 PM-5:20 PM |
| `s6_missed_session` | `missed_session` | 0.76 (baseline) | defer | Spanish vocab flashcards | 10:00 AM-11:00 AM -> 1:00 PM-2:00 PM |

## `s3_short_night_fatigue`

**Story:** It's 2:00 PM. You only slept about 5 hours (2:30 AM to 7:30 AM). You're about to start a 2:00-3:00 PM biology reading session and tell the app "I'm exhausted, I can't focus".

**Proposal shown to the student:** Since you're feeling tired, I'd cut "Biology reading" down to a 25-minute session ending at 2:25 PM, because a short focused block beats pushing through exhausted. Sound good? (accept / edit / skip)

## `s4_signals_disagree_ask`

**Story:** It's 4:00 PM. You slept about 8.5 hours. At the start of your exam review session you told the app you feel "good", but 10 minutes in you tap "I'm tired".

**Proposal shown to the student:** Your energy estimate looked good, but you're telling me you're tired, so I'm not sure how to change "Exam review". Want to just tell me what changed?

## `s5_meeting_ran_late`

**Story:** It's 4:20 PM. Your group project meeting was supposed to end at 4:00 but ran 20 minutes late. You had a data structures problem set planned for 4:00-5:00, and an evening lecture at 6:00. You check in as "fine".

**Proposal shown to the student:** Since things ran 20 minutes late, I'd push "Data structures problem set" from 4:00 PM to 4:20 PM. Sound good? (accept / edit / skip)

## `s6_missed_session`

**Story:** It's 1:00 PM. You slept about 8 hours. You missed this morning's 10:00-11:00 Spanish vocab flashcards session because an errand took longer than expected, and you have a lecture from 2:00-3:30.

**Proposal shown to the student:** No worries about missing "Spanish vocab flashcards" -- I'd make it up at 1:00 PM today, because that's the next open slot that fits it. Sound good? (accept / edit / skip)
