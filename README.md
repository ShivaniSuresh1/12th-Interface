# The 12th Interface — Sleep/Energy-Aware Study Session Planner

CSCE 634 (Intelligent User Interfaces) group project. An app that plans *when*
to study *what*, based on a student's real energy patterns and schedule —
not just a to-do list.

**Team:** Shivani Suresh · Vyshnavi Pamidi · Soumyadip Sarkar · Harshini Kondepudi

## What this is

A hybrid sleep-based energy estimate, corrected by a short conversational
check-in at each session boundary, drives a per-student learned mapping from
energy state to preferred task type. When something changes (fatigue, a
meeting running late), the system negotiates a replan with the student
instead of silently rescheduling.

See [`docs/design-decisions.md`](docs/design-decisions.md) for the six
design questions the team worked through (energy estimation, cold start,
task taxonomy, energy→task mapping, replanning, check-in cadence) and why
we landed where we did.

## Repo layout

```
src/
  user_model/      Shivani   — schedules, deadlines, energy reports; refines
                               energy estimates from completed sessions
  domain_model/    Vyshnavi  — task taxonomy, difficulty, energy→task mapping
  negotiation/     Soumyadip — replanning, disruption handling, check-in cadence
  integration/     Harshini  — wires components together, evaluation harness
tests/             Unit tests, mirrors src/ layout
docs/              Design rationale, architecture notes, meeting notes
```

Each module owner's responsibilities and interfaces are documented in that
module's own `README.md` (see `src/*/README.md`).

## Working independently — and still ending up compatible

Each of the four of us can build our module with a different AI assistant
(Claude, ChatGPT, Copilot, whatever) and it will still fit together, as
long as everyone works against the **same frozen interface contract**
instead of inventing their own shapes:

1. Read [`docs/CONTRACTS.md`](docs/CONTRACTS.md) — it's the single source
   of truth for every function signature and data shape that crosses a
   module boundary.
2. Your own module's `README.md` has a ready-to-paste **"Prompt for your
   AI assistant"** section that already includes the relevant slice of
   that contract plus the guardrails (stay in your folder, don't rename
   things, run the tests before you're done).
3. `tests/test_contracts.py` checks the contract mechanically in CI —
   if your assistant (or anyone else's) drifts from it, the build goes
   red instead of silently breaking integration later.

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

pytest
```

Python 3.11+ assumed. No external services required yet — everything runs
locally against the stub in-memory data in each module.

## Workflow / conventions

- One branch per feature/task, PR into `main`. Please don't push directly to `main`.
- Keep PRs scoped to one module where possible — the four `src/` packages are
  intentionally decoupled behind the interfaces described in each module's
  `README.md`, so most work shouldn't need cross-module changes.
- Run `pytest` and `ruff check .` before opening a PR (see `.github/workflows/ci.yml`
  for what CI will check).
- Add/extend tests under `tests/` alongside new code.

## Target milestones

| Date | Milestone |
|---|---|
| Oct 16 | Initial user and domain models |
| Oct 30 | Dialogue flow and replanning rules |
| Nov 6  | First working version of the planner |
| Nov 20 | Test with study scenarios, collect feedback |
| Nov 27 | Revise planner based on results |
| Dec 3  | Final prototype and evaluation report |

## License

Class project — not currently licensed for reuse outside the team.
