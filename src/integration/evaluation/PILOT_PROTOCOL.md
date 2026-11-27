# Pilot protocol (Phase 2, steps 6-7)

How to run the team dry-run and the outside pilot with the evaluation
harness. Owner: Harshini. Design follows the team's evaluation plan:
within-subjects, two conditions (explanation shown vs plain numbers),
condition order and scenario sets counterbalanced, 6-10 outside participants.

All commands run from the repo root with the venv active. They are written
for Mac/Linux; see "Windows" below for the PowerShell versions.

## Setup (first time on a machine)

A fresh checkout has no `.venv`, so create it first:

```bash
# Mac / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

```powershell
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
```

### Windows

`PYTHONPATH=src python ...` doesn't work in PowerShell. Set the variable once
per terminal, then run the same command without the prefix:

```powershell
$env:PYTHONPATH="src"
python -m integration.evaluation run --participant 1
```

## Before any session

1. `git checkout main && git pull`, then `pytest -q` (everything passes).
2. Write down the commit hash (`git rev-parse --short HEAD`). Every session in
   one pilot must run the same commit, so that everyone sees identical scenarios.
3. `PYTHONPATH=src python -m integration.evaluation preview` and skim the output.
   The recommendation and proposal texts should match
   `src/domain_model/PILOT_RECOMMENDATIONS.md` and `src/negotiation/PILOT_PROPOSALS.md`.
4. Make the terminal font large and the window wide (about 100 columns), so each
   scenario fits on screen without scrolling.

## Step 6: team dry-run

The goal is to check timing, wording and flow. The data is not used: the team
built the system, so their ratings don't count.

- Each teammate runs one session, using participant numbers 1-4 so that together you
  cover all four counterbalancing groups:

  ```bash
  PYTHONPATH=src python -m integration.evaluation run --participant 1 --log-dir eval_logs/dry_run
  ```

- The person running the session reads the script below aloud, exactly as it
  will be read to participants, and times the session.
- Afterwards, `PYTHONPATH=src python -m integration.evaluation analyze --log-dir eval_logs/dry_run`
  checks that the report reads correctly.
- Write down anything confusing. If you change a scenario, follow the steps in
  "If you change a scenario" below, and the dry-run then needs to be repeated.
- Delete `eval_logs/dry_run/` once you're done.

## Step 7: outside pilot

- **Participants:** 6-10 people from outside the team. Aim for **8**, because
  counterbalancing repeats every 4 participants (P1-P4, P5-P8), so a multiple of 4
  keeps both condition orders and both scenario sets balanced.
- **Numbering:** P1, P2, ... in the order people show up. Don't skip numbers.
- **Data:** logs contain only the participant number. Don't write down names
  next to numbers. If the course requires more than verbal consent for a class
  pilot, check with the instructor before the first session.
- **Time:** about 10-15 minutes each (6 scenarios plus the exit survey). Use the
  dry-run timing to set this estimate.

```bash
PYTHONPATH=src python -m integration.evaluation run --participant 1
```

### Script (read aloud, same words every time)

> Thanks for helping. This is a study planner that estimates your energy from
> your sleep and the time of day, and suggests what kind of studying to do. You'll
> read 6 short situations. In each one, imagine you are the student described.
>
> After each one, tell me whether you'd **accept**, **edit** or **reject** what the
> planner suggests, deciding as you would if you were that student. If it
> proposes a schedule change, you're deciding on that change. If it asks you a
> question instead, you'll just say whether you'd answer it. Then rate how much
> you trust its suggestion, even if you didn't go with it, and how confident
> you are in your own decision, from 1 to 7.
>
> You can't go back and change an answer, so go with your first reaction.
> Some situations show more detail than others. That's intended. There are no
> right answers, and we're testing the planner, not you. Please read each
> situation fully before you answer. You'll answer a few short questions at
> the end.

### Questions participants are likely to ask

Answer these with the same words every time (they came up in the team dry-run):

| Question | Answer |
| --- | --- |
| "Am I deciding as myself or as the student?" | "As yourself, imagining you're the student in the story." |
| "Can I go back and change an answer?" | "No, go with your first reaction." |
| "Should I rate trust even if I rejected it?" | "Yes, rate how much you trust what the planner suggested, whatever you decided." |
| "What does it mean when the planner asks me a question?" | "Just say whether you'd answer it. If yes, you can type what you'd tell it." |

Any other "what does this mean?" question: see below.

During the session:

- Don't explain or justify anything the planner says. If they ask "what does
  this mean?", say "go with how you'd read it if you were using the app", and
  write the question down. Those questions count as data on clarity.
- Don't comment on their answers. Decision time is measured from when the
  scenario appears.
- Let them type, or type exactly what they say.
- Watch for click-through. In the team dry-run, plain scenarios were answered
  in 1.6-4 seconds. If someone answers before they could have read the
  scenario, note the participant number and scenario so the report can flag it.

### If something goes wrong

- **Stopped after the scenarios, before the survey:** run
  `PYTHONPATH=src python -m integration.evaluation survey --participant N`.
- **Stopped partway through the scenarios:** the answers given so far are saved.
  Move `eval_logs/participant_NN.csv` into `eval_logs/excluded/` and write down
  why. Then give the **next** participant the **same number N**, so the
  counterbalancing cycle stays complete.
- **The harness refuses a participant number** ("already exists"): you are about
  to overwrite someone's data. Check the number before you move anything.

## After the pilot

```bash
PYTHONPATH=src python -m integration.evaluation analyze --out eval_logs/pilot_report.md
```

- The report is descriptive: decisions, trust, confidence and decision time per
  condition, per scenario and per block (an order check); each participant's
  explanation-minus-plain difference; and the exit survey. With 6-10 people,
  present it as rates and distributions, not significance tests.
- `eval_logs/` is gitignored. Back it up somewhere private (not the repo).
  Before you put any part of the report in the final writeup, read the
  free-text answers and remove anything that could identify a participant.

## If you change a scenario

`src/integration/evaluation/scenarios.py` is the single source. After an edit:

```bash
PYTHONPATH=src python -m tests.domain_model.pilot_recommendations   # regenerate Vyshnavi's doc
PYTHONPATH=src python -m tests.negotiation.pilot_proposals          # regenerate Soumyadip's doc
pytest -q
```

If a disruption scenario's replan action changes, update `EXPECTED_ACTION` in
`tests/negotiation/test_pilot_scenarios.py`. The tests also make sure that no scenario's
energy sits within 0.03 of a bucket cut point, that every concrete replan
matches the recommended task type, and that all three explanation sources
(default rule, survey, learned choices) are still shown.
