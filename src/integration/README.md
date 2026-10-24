# Integration & Evaluation — owner: Harshini Kondepudi

Cross-cutting: combines the other three components into a working
prototype, tests scheduling/replanning scenarios end-to-end, and plans how
to measure whether students find it useful.

## Responsibilities

- Wire `user_model`, `domain_model`, and `negotiation` together into one
  planner (`StudySessionPlanner`, see `planner.py`).
- Write end-to-end scenario tests (a student's day, a disruption, a
  negotiated replan, and the resulting learning update) — see `tests/`.
- Define and run the evaluation plan (how we'll test with real study
  scenarios around Nov 20, what "useful" means for this project).

## Interface (frozen — see `docs/CONTRACTS.md`)

Signature below is locked the same way the other three modules' are —
rewrite the body freely, don't rename methods or reorder/rename
parameters without updating `docs/CONTRACTS.md` and
`tests/test_contracts.py` too.

```python
from integration import StudySessionPlanner

planner = StudySessionPlanner(student_id="s1")
plan = planner.plan_day()
planner.handle_checkin(response="tired")
planner.handle_disruption(trigger="meeting_ran_late")
```

`StudySessionPlanner` is intentionally a thin orchestrator — it should not
contain its own energy-estimation, taxonomy, or replanning logic; those
stay in their owning modules. This is the **one** module allowed to
import from the other three (`user_model`, `domain_model`, `negotiation`)
— they should never import from each other or from here.

## Works closely with

Everyone — this is the integration seam for `user_model`, `domain_model`,
and `negotiation`.

## TODO

- [ ] Flesh out `StudySessionPlanner` once the other three modules'
      real implementations land
- [ ] Write the first end-to-end scenario test
- [ ] Draft the evaluation plan / metrics for the Nov 20 feedback milestone

## Prompt for your AI assistant

Paste this (with whatever LLM you're using — Claude, ChatGPT, Copilot,
etc.; nothing here is tool-specific). Your job is special: you're the one
person whose code touches everyone else's, so your assistant needs the
*whole* contract, not just one slice.

```
I'm implementing the "integration" module of a student study-planner app
— the component that wires together three other modules (user_model,
domain_model, negotiation), each being built independently by a teammate,
possibly with a different AI assistant than you. The only thing that lets
four independently-built modules fit together is a frozen interface
contract, defined in docs/CONTRACTS.md — treat every signature in it as
fixed; do not invent different ones.

Context: this module lives at src/integration/ in a Python 3.11 repo.
Read (or I will paste) the FULL docs/CONTRACTS.md (all four sections, not
just "integration") plus this module's own README.md before writing
anything, since StudySessionPlanner calls into all three other modules.

Rules you must follow:
1. Only edit files inside src/integration/ and add/extend tests under
   tests/ (e.g. tests/integration/, or end-to-end scenario tests at
   tests/test_*.py). You may import from user_model, domain_model, and
   negotiation — but do not edit files inside those directories, and do
   not edit docs/CONTRACTS.md.
2. Keep StudySessionPlanner's public methods exactly as specified:
   plan_day(self), handle_checkin(self, response),
   handle_disruption(self, trigger), handle_resolution(self, proposal,
   student_response). Rewrite bodies freely.
3. Treat the other three modules as the ground truth for their own types
   (EnergyReport, TaskType, StudentTaskMapping, ReplanProposal, etc.) —
   don't redefine or duplicate them here, import them.
4. My actual task: [DESCRIBE WHAT YOU WANT IMPLEMENTED, e.g. "wire
   handle_resolution so an accepted/edited replan actually calls
   StudentTaskMapping.record_choice(...) on the domain_model side" or
   "write the first end-to-end scenario test covering a full day"].
5. When done, tell me to run from the repo root:
     pip install -r requirements.txt -r requirements-dev.txt
     ruff check . && pytest
   All tests must pass, including tests/test_contracts.py and
   tests/test_smoke.py.
```
