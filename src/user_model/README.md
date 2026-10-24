# User Model — owner: Shivani Suresh

Owns design questions **Q1** (energy estimation) and **Q2** (cold start).
See `docs/design-decisions.md` for the full rationale.

## Responsibilities

- Track a student's schedule, deadlines, and reported sleep/energy.
- Produce a **baseline energy estimate** for the day from sleep/schedule
  data (Q1, sleep-based half of the hybrid).
- Apply a **conversational check-in correction** to that baseline at each
  session boundary (Q1, conversational half of the hybrid).
- Handle **cold start**: run the short onboarding survey and expose a
  default-rule flag until enough real sessions exist (Q2).
- Feed completed-session outcomes back in so estimates improve over time.

## Interface (frozen — see `docs/CONTRACTS.md`)

The function/class *signatures* below are locked so other modules (and
whatever AI assistant they're using) can build against them right now.
Implementations are stubs — rewrite the bodies freely, just don't rename
things or reorder/rename parameters without updating `docs/CONTRACTS.md`
and `tests/test_contracts.py` too.

```python
from user_model import StudentProfile, estimate_baseline_energy, apply_checkin_correction

profile = StudentProfile(student_id="s1", sleep_hours=6.5, schedule=[...])
baseline = estimate_baseline_energy(profile)          # -> EnergyReport
corrected = apply_checkin_correction(baseline, checkin_response="tired")
```

## Works closely with

- **Domain Model** (Vyshnavi) — consumes `EnergyReport` for the
  energy→task mapping (Q4).
- **Negotiation & Replanning** (Soumyadip) — supplies/receives check-in
  data at session boundaries (Q6).

## TODO

- [ ] Define `StudentProfile` / `EnergyReport` fields for real (see `models.py` stub)
- [ ] Implement sleep-based baseline estimate (RISE-style curve)
- [ ] Implement check-in correction + weighting rule between the two signals
- [ ] Implement cold-start default rule and the decay as real data accumulates
- [ ] Persist energy history per student (storage TBD — SQLite suggested, not finalized)

## Prompt for your AI assistant

Paste this (with whatever LLM you're using) to get consistent, team-safe
output. It works with Claude, ChatGPT, Copilot, etc. — nothing here is
tool-specific.

```
I'm implementing the "user_model" module of a student study-planner app.
I am ONE of four people independently implementing different modules with
different AI assistants, so the only thing holding the project together is
a frozen interface contract — do not deviate from it.

Context: the module lives at src/user_model/ in a Python 3.11 repo. Read
(or I will paste) docs/CONTRACTS.md's "user_model" section and this
module's own README.md before writing anything.

Rules you must follow:
1. Only edit files inside src/user_model/ and add/extend tests under
   tests/ (e.g. tests/user_model/). Do not touch src/domain_model,
   src/negotiation, src/integration, or docs/CONTRACTS.md.
2. Keep these exact signatures unchanged (names, parameter names/order,
   dataclass field names) — rewrite bodies freely, but not these shapes:
   - StudentSchedule(student_id, events)
   - EnergyReport(student_id, timestamp, energy_level, source)
   - StudentProfile(student_id, sleep_hours, schedule, cold_start, energy_history)
   - estimate_baseline_energy(profile) -> EnergyReport
   - apply_checkin_correction(baseline, checkin_response) -> EnergyReport
3. energy_level is always a float in [0.0, 1.0]. source is either
   "baseline" or "checkin_corrected".
4. My actual task: [DESCRIBE WHAT YOU WANT IMPLEMENTED, e.g. "implement a
   real sleep-based baseline curve instead of the flat 0.5 placeholder in
   energy_estimate.py, informed by RISE-style sleep debt / circadian
   modeling" or "implement the cold-start default-rule logic in models.py"].
5. When done, tell me to run from the repo root:
     pip install -r requirements.txt -r requirements-dev.txt
     ruff check . && pytest
   All tests must pass, including tests/test_contracts.py and
   tests/test_smoke.py — those catch anything that broke the shared
   contract with the other three modules.
```
