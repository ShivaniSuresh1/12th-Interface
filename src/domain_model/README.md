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

## Works closely with

- **User Model** (Shivani) — consumes `EnergyReport.energy_level` to
  produce task recommendations.
- **Negotiation & Replanning** (Soumyadip) — every accept/edit/reject of a
  proposed task is a labeled example that updates `StudentTaskMapping`.

## TODO

- [ ] Finalize the fixed taxonomy (`TaskType` enum) — problem sets, reading,
      review, memorization is the starting proposal
- [ ] Implement default difficulty per type + student override
- [ ] Implement the per-student weighted lookup / decaying blend (Q4)
- [ ] Implement the default energy→task rule used during cold start (Q2)
- [ ] Implement the one-sentence explanation generator

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
