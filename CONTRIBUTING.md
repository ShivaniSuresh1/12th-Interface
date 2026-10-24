# Contributing (team-internal)

1. Clone the repo, create a venv, `pip install -r requirements.txt -r requirements-dev.txt`.
2. Create a branch off `main`: `git checkout -b <name>/<short-description>`.
3. Work inside your owned module (see README.md's "Repo layout") unless a
   change genuinely needs to cross module boundaries — if it does, flag it
   in the PR description so the other owner can review the interface change.
4. Before opening a PR:
   ```bash
   ruff check .
   pytest
   ```
5. Open a PR into `main`. One approval from another team member before merging.
6. Update the module's own `README.md` TODO list as you knock items off —
   it's the fastest way for everyone else to see what's actually done vs.
   still stubbed.

## Where things live

- Design rationale / the six design questions: `docs/design-decisions.md`
- Module responsibilities + TODOs: `src/<module>/README.md`
- Meeting / activity notes: add them under `docs/` as they happen
