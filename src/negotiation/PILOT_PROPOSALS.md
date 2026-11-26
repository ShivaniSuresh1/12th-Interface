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
| `s4_signals_disagree_ask` | `fatigue` | 0.70 (checkin_corrected) | ask | - | asks the student |
| `s5_meeting_ran_late` | `meeting_ran_late:20` | 0.52 (baseline) | move | History reading | 3:40 PM-4:40 PM -> 4:00 PM-5:00 PM |
| `s6_missed_session` | `missed_session` | 0.21 (checkin_corrected) | defer | Spanish vocab flashcards | 9:00 AM-10:00 AM -> 11:00 AM-11:25 AM |

## `s3_short_night_fatigue`

**Story:** It's 2:00 PM. You only slept about 5 hours (2:30 AM to 7:30 AM). You're about to start a 2:00-3:00 PM biology reading session and tell the app "I'm exhausted, I can't focus".

**Proposal shown to the student:** Since you're feeling tired, I'd cut "Biology reading" down to a 25-minute session ending at 2:25 PM, because a short, focused block works better than pushing through when you're exhausted. Sound good? (accept / edit / reject)

## `s4_signals_disagree_ask`

**Story:** It's 8:00 PM. You slept about 8 hours (11:30 PM to 7:30 AM). At the start of your exam review session you told the app you feel "good", but a few minutes in you tap "I'm tired".

**Proposal shown to the student:** Your energy estimate looked good, but you're telling me you're tired, so I'm not sure how to change "Exam review". Want to just tell me what changed?

## `s5_meeting_ran_late`

**Story:** You've used the app for about two weeks. On tired days you've usually switched to flashcards, and at medium energy you've mostly picked reading. It's 4:00 PM. You slept about 5 hours (2:30 AM to 7:30 AM) and haven't checked in today. Your group project meeting was supposed to end at 3:40 but ran 20 minutes late. You had a history reading session planned for 3:40-4:40, and an evening lecture at 6:00.

**Proposal shown to the student:** Since things ran 20 minutes late, I'd push "History reading" from 3:40 PM to 4:00 PM. Sound good? (accept / edit / reject)

## `s6_missed_session`

**Story:** You've used the app for about two weeks. On tired days you've usually switched to flashcards, and at medium energy you've mostly picked reading. It's 11:00 AM. You only slept about 4 hours (3:30 AM to 7:30 AM). You missed this morning's 9:00-10:00 Spanish vocab flashcards session because an errand took longer than expected, and you have a lecture from 12:00-1:30. You check in as "exhausted".

**Proposal shown to the student:** No worries about missing "Spanish vocab flashcards". Your energy is low, so I'd make up a shorter 25-minute version at 11:00 AM today instead of the full session. Sound good? (accept / edit / reject)
