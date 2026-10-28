# Negotiation & Replanning — owner: Soumyadip Sarkar

Owns design questions **Q5** (replanning) and **Q6** (check-in cadence).
See `docs/design-decisions.md` for the full rationale.

## Responsibilities

- Decide when to move, shorten, or defer a session when something changes
  (fatigue, a meeting running late, a missed session) (Q5).
- Propose and **narrate** replans; student accepts or edits with one tap —
  never a silent automatic reschedule (Q5).
- Run check-ins only at session boundaries (start/end/break), capped per
  day, and batch the energy check-in with any proposed replan into a
  single message (Q6).
- Every accept/edit/reject is a labeled example — hand it back to the
  Domain Model's `StudentTaskMapping.record_choice(...)` so the learned
  mapping improves (Q4/Q5 interaction).

## Interface (frozen — see `docs/CONTRACTS.md`)

Signatures below are locked so the other modules (and whatever AI
assistant each person is using) can build against them right now.
Rewrite bodies freely; don't rename things or reorder/rename parameters
without updating `docs/CONTRACTS.md` and `tests/test_contracts.py` too.

```python
from negotiation import is_session_boundary, propose_replan, resolve_proposal

if is_session_boundary(now, student_schedule):
    proposal = propose_replan(student_profile, trigger="fatigue")
    # proposal.message -> narrated, single batched message (check-in + proposed change)
    resolution = resolve_proposal(proposal, student_response="accept")
```

## Works closely with

- **User Model** (Shivani) — triggers the check-in that corrects the
  energy estimate (Q1 x Q6).
- **Harshini** (Integration) — this is the component most exercised by
  end-to-end scenario tests.

## For Integration (Harshini)

Beyond the frozen contract, the module also exports helpers the planner
can use (none of them change the contract):

```python
from negotiation import (
    CheckinLog,
    should_check_in,
    compose_checkin_message,  # Q6 cadence + batching
    next_boundary,  # when to raise a mid-session disruption
    training_example,  # resolution -> record_choice() input
)

log = CheckinLog()  # one per planner; enforces the daily cap
window = should_check_in(now, profile.schedule, log)
if window:
    proposal = propose_replan(profile, trigger)  # or None if nothing changed
    send(compose_checkin_message(window, proposal))  # ONE message, not two

resolution = resolve_proposal(proposal, "accept")
ex = training_example(resolution)
if ex["chosen_task_type"] and ex["energy_level"] is not None:
    task_mapping.record_choice(ex["energy_level"], TaskType(ex["chosen_task_type"]))
```

**Schedule events** are read leniently from `StudentSchedule.events`:
`"kind"` (`"study"`, `"break"`, or anything else like `"class"`) and
`"start"`/`"end"` (datetime or ISO string) are required -- events without
a kind are skipped, never guessed to be study. `"session_id"`, `"title"`
and `"task_type"` are optional. Naive times are read as the student's
local time. This matches `user_model.models.Event`; see `_schedule.py`.

**Triggers** are free-form; `fatigue`, `meeting_ran_late[:<minutes>]`
and `missed_session` (plus aliases) get specific proposals, anything else
gets the "tell me what changed" fallback. `proposed_change`'s shape is
documented at the top of `replanning.py`.

## TODO

- [x] Define what counts as a "session boundary" precisely (see `checkin.py`)
- [x] Implement the daily check-in cap
- [x] Implement replan proposal generation + narration text
- [x] Provide resolution -> labeled example hand-off (`training_example`);
      the actual `record_choice(...)` call lives in `integration`
- [x] Implement the "not sure, want to just tell me what changed?" fallback
      (Calendar.help-style graceful fallback when the system isn't confident)
- [x] Agree on the schedule event shape with User Model (Shivani)
- [ ] Make `MAX_CHECKINS_PER_DAY` configurable per student
- [ ] Parse the free-text answer to the "tell me what changed" fallback
- [ ] Tune thresholds/durations after the Nov 20 scenario testing

## Prompt for your AI assistant

Paste this (with whatever LLM you're using — Claude, ChatGPT, Copilot,
etc.; nothing here is tool-specific) to get output that stays compatible
with the other three modules.

```
I'm implementing the "negotiation" module of a student study-planner app.
I am ONE of four people independently implementing different modules with
different AI assistants, so the only thing holding the project together is
a frozen interface contract — do not deviate from it.

Context: the module lives at src/negotiation/ in a Python 3.11 repo. Read
(or I will paste) docs/CONTRACTS.md's "negotiation" section and this
module's own README.md before writing anything.

Rules you must follow:
1. Only edit files inside src/negotiation/ and add/extend tests under
   tests/ (e.g. tests/negotiation/). Do not touch src/user_model,
   src/domain_model, src/integration, or docs/CONTRACTS.md.
2. Keep these exact signatures unchanged (names, parameter names/order,
   dataclass field names) — rewrite bodies freely, but not these shapes:
   - CheckinWindow(student_id, boundary_type, timestamp)
   - ReplanProposal(student_id, trigger, message, proposed_change)
   - ReplanResolution(proposal, outcome, edited_change)
   - is_session_boundary(now, schedule) -> bool
   - propose_replan(student_profile, trigger) -> ReplanProposal
   - resolve_proposal(proposal, student_response, edited_change=None) -> ReplanResolution
3. outcome is always one of "accepted" | "edited" | "rejected". A replan
   must always be proposed and narrated (message is non-empty human text)
   — never applied silently.
4. My actual task: [DESCRIBE WHAT YOU WANT IMPLEMENTED, e.g. "implement
   real session-boundary detection in checkin.py against a student's
   schedule" or "implement the daily check-in cap and the narration text
   in replanning.py"].
5. When done, tell me to run from the repo root:
     pip install -r requirements.txt -r requirements-dev.txt
     ruff check . && pytest
   All tests must pass, including tests/test_contracts.py and
   tests/test_smoke.py — those catch anything that broke the shared
   contract with the other three modules.
```
