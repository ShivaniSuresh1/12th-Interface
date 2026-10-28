# Domain Model — owner: Vyshnavi Pamidi

Owns design questions **Q3** (task taxonomy) and **Q4** (energy→task
mapping). See `docs/design-decisions.md` for the full rationale.

## Responsibilities

- Define the fixed task taxonomy: problem sets, reading, review,
  memorization — each with a default difficulty, adjustable by the student (Q3).
- Maintain the **per-student** energy-to-task mapping: a weighted
  rule/lookup table blending the Q2 onboarding survey and learned choices,
  with a decaying weight as real sessions accumulate (Q4, PTIME-style).
- Expose a one-sentence "because" explanation for any recommendation
  (explainability requirement tying Q3/Q4/Q5 together).
- Define what data this component shares with the User Model (energy
  reports in, task recommendations + explanations out).

## Interface (frozen — see `docs/CONTRACTS.md`)

Signatures below are locked so the other modules (and whatever AI
assistant each person is using) can build against them right now.
Rewrite bodies freely; don't rename things or reorder/rename parameters
without updating `docs/CONTRACTS.md` and `tests/test_contracts.py` too.

```python
from domain_model import TaskType, Task, recommend_task_type, StudentTaskMapping

mapping = StudentTaskMapping(student_id="s1")
task_type, why = recommend_task_type(mapping, energy_level=0.3)
# task_type -> TaskType.READING, why -> "because you usually prefer reading when tired"
```

## How it works

- **Taxonomy (Q3, `taxonomy.py`):** four fixed `TaskType`s, each with a
  default difficulty on a 1–5 scale (`DEFAULT_DIFFICULTY`). A student can
  override a task's difficulty with `task.set_difficulty(n)` (or `None` to
  reset); `task.effective_difficulty()` returns the override or the default.
- **Energy buckets:** `low` < 0.33 ≤ `medium` < 0.66 ≤ `high`
  (`LOW_ENERGY` / `HIGH_ENERGY` in `mapping.py`; `negotiation` mirrors these).
- **Prior (Q2):** the student's onboarding-survey answer for that bucket, or
  the default rule (high → problem sets, medium → review, low → reading).
- **Learning (Q4/Q5):** `record_choice(energy_level, chosen_type)` counts
  each accepted/edited choice per bucket. `preferences[bucket]` is the type
  the student has picked most often there.
- **Decaying blend (Q4, PTIME-style):** `learned_weight = n / (n + 5)` after
  `n` recorded choices, so the survey/default fades out — after 5 choices
  (= user_model's `COLD_START_MIN_CHECKINS`) learned data counts as much as
  the prior. Per bucket, each type scores
  `(1 - learned_weight) * [is the prior] + learned_weight * (its share of choices)`.
- **Explanations:** `recommend_task_type` always returns one "because …"
  sentence saying whether the pick comes from the default, the survey, or the
  student's own choices. `mapping.blend_summary()` makes the survey → learned
  shift visible ("now 50% based on your own choices …").

Additive helpers (no contract change):

```python
from domain_model import StudentTaskMapping, recommend_task

mapping = StudentTaskMapping.from_survey("s1", {"low": "problem_set"})  # Q2 survey answers
mapping.blend_summary()        # one sentence showing the survey -> learned shift
task, why = recommend_task(mapping, energy_level=0.3, tasks=todays_tasks)
# picks a concrete Task: recommended type first, then difficulty closest to the energy
```

## Works closely with

- **User Model** (Shivani) — consumes `EnergyReport.energy_level` to
  produce task recommendations.
- **Negotiation & Replanning** (Soumyadip) — every accept/edit/reject of a
  proposed task is a labeled example that updates `StudentTaskMapping`.

## TODO

- [x] Finalize the fixed taxonomy (`TaskType` enum) — problem sets, reading,
      review, memorization (unchanged from the proposal)
- [x] Implement default difficulty per type + student override
      (`DEFAULT_DIFFICULTY`, `Task.set_difficulty`, validated 1–5)
- [x] Implement the per-student weighted lookup / decaying blend (Q4)
- [x] Implement the default energy→task rule used during cold start (Q2)
- [x] Implement the one-sentence explanation generator
- [ ] Agree with Shivani on the bucket cut points (a well-rested student sits
      around 0.62–0.69, so "high" mostly fires in the morning) — any change
      must also update `negotiation.replanning.LOW_ENERGY` / `HIGH_ENERGY`
- [ ] Agree with Shivani where the onboarding survey runs; task-preference
      answers plug in here via `StudentTaskMapping.from_survey(...)`
- [ ] Persist survey answers and choice counts (they are plain attributes, not
      contract fields, so they aren't saved with the dataclass yet)
- [ ] Tune `PRIOR_STRENGTH` against real study-scenario data (Nov 20 milestone)

## Prompt for your AI assistant

Paste this (with whatever LLM you're using — Claude, ChatGPT, Copilot,
etc.; nothing here is tool-specific) to get output that stays compatible
with the other three modules.

```
I'm implementing the "domain_model" module of a student study-planner app.
I am ONE of four people independently implementing different modules with
different AI assistants, so the only thing holding the project together is
a frozen interface contract — do not deviate from it.

Context: the module lives at src/domain_model/ in a Python 3.11 repo. Read
(or I will paste) docs/CONTRACTS.md's "domain_model" section and this
module's own README.md before writing anything.

Rules you must follow:
1. Only edit files inside src/domain_model/ and add/extend tests under
   tests/ (e.g. tests/domain_model/). Do not touch src/user_model,
   src/negotiation, src/integration, or docs/CONTRACTS.md.
2. Keep these exact signatures unchanged (names, parameter names/order,
   dataclass field names, enum values) — rewrite bodies freely, but not
   these shapes:
   - TaskType enum with values: problem_set, reading, review, memorization
   - Task(task_id, title, task_type, difficulty)
   - StudentTaskMapping(student_id, learned_weight, preferences)
   - recommend_task_type(mapping, energy_level) -> tuple[TaskType, str]
     (the str is a one-sentence human-readable "because ..." explanation)
3. energy_level passed in is always a float in [0.0, 1.0] — this comes
   from user_model.EnergyReport.energy_level, you don't own that type.
4. My actual task: [DESCRIBE WHAT YOU WANT IMPLEMENTED, e.g. "implement
   the real per-student decaying blend in mapping.py between the cold-start
   default rule and StudentTaskMapping.preferences, replacing the
   threshold placeholder" or "add a record_choice-driven learning rule"].
5. When done, tell me to run from the repo root:
     pip install -r requirements.txt -r requirements-dev.txt
     ruff check . && pytest
   All tests must pass, including tests/test_contracts.py and
   tests/test_smoke.py — those catch anything that broke the shared
   contract with the other three modules.
```
