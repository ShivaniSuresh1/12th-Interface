# Interface Contracts (read this before prompting any AI assistant)

Four people are implementing four modules, likely using **different AI
assistants** (Claude, ChatGPT, Copilot, whatever). The only thing that
guarantees the pieces fit back together at the end is: **everyone codes
against the same frozen function signatures and data shapes**, and nobody
changes them without telling the other three.

This file is the single source of truth for those shapes. `tests/test_contracts.py`
checks them automatically in CI — if your change breaks the contract, CI
turns red on your PR, which is the point.

**Rule: you may freely rewrite the *body* of any function below. You may
NOT rename it, remove it, change its parameter names/order, or change what
a dataclass field is called, without raising it with the team first.**
If you genuinely need to change a contract, update it here in the same PR
and say so in the PR description — don't change it silently.

---

## `user_model` (owner: Shivani) — Q1, Q2

```python
@dataclass
class StudentSchedule:
    student_id: str
    events: list[dict]

@dataclass
class EnergyReport:
    student_id: str
    timestamp: datetime
    energy_level: float   # 0.0 (exhausted) .. 1.0 (fully energized)
    source: str            # "baseline" | "checkin_corrected"

@dataclass
class StudentProfile:
    student_id: str
    sleep_hours: float | None
    schedule: StudentSchedule | None
    cold_start: bool
    energy_history: list[EnergyReport]

def estimate_baseline_energy(profile: StudentProfile) -> EnergyReport: ...
def apply_checkin_correction(baseline: EnergyReport, checkin_response: str) -> EnergyReport: ...
```

**Consumed by:** `domain_model.recommend_task_type` (needs `EnergyReport.energy_level`),
`integration.StudySessionPlanner`.

## `domain_model` (owner: Vyshnavi) — Q3, Q4

```python
class TaskType(str, Enum):
    PROBLEM_SET = "problem_set"
    READING = "reading"
    REVIEW = "review"
    MEMORIZATION = "memorization"

@dataclass
class Task:
    task_id: str
    title: str
    task_type: TaskType
    difficulty: int | None

@dataclass
class StudentTaskMapping:
    student_id: str
    learned_weight: float
    preferences: dict[str, TaskType]

def recommend_task_type(mapping: StudentTaskMapping, energy_level: float) -> tuple[TaskType, str]: ...
    # returns (recommended TaskType, one-sentence human-readable "because ..." explanation)
```

**Consumes:** `EnergyReport.energy_level` (a `float` 0.0-1.0 — don't assume
any other range or type). **Consumed by:** `negotiation` (proposals
reference a `TaskType`), `integration.StudySessionPlanner`.

## `negotiation` (owner: Soumyadip) — Q5, Q6

```python
@dataclass
class CheckinWindow:
    student_id: str
    boundary_type: str   # "start" | "end" | "break"
    timestamp: datetime

def is_session_boundary(now: datetime, schedule: object) -> bool: ...

@dataclass
class ReplanProposal:
    student_id: str
    trigger: str          # free-form reason string, e.g. "fatigue", "meeting_ran_late"
    message: str           # human-readable, narrated — never silent
    proposed_change: dict  # shape TBD; treat as opaque payload for now

@dataclass
class ReplanResolution:
    proposal: ReplanProposal
    outcome: str            # "accepted" | "edited" | "rejected"
    edited_change: dict | None

def propose_replan(student_profile: object, trigger: str) -> ReplanProposal: ...
def resolve_proposal(proposal: ReplanProposal, student_response: str, edited_change: dict | None = None) -> ReplanResolution: ...
```

**Consumes:** a `StudentProfile`-shaped object (don't need every field —
just `student_id` at minimum). **Produces:** resolutions that should
eventually call `domain_model.StudentTaskMapping.record_choice(...)` —
that wiring point is `integration`'s job, not yours directly.

## `integration` (owner: Harshini) — cross-cutting

```python
@dataclass
class StudySessionPlanner:
    student_id: str

    def plan_day(self) -> dict: ...
    def handle_checkin(self, response: str) -> EnergyReport: ...
    def handle_disruption(self, trigger: str) -> ReplanProposal: ...
    def handle_resolution(self, proposal: ReplanProposal, student_response: str, edited_change: dict | None = None) -> ReplanResolution: ...
```

This is the one module allowed to import from the other three. The other
three should **never** import from each other directly or from
`integration` — if you think you need to, that's a sign the interface
above needs to grow, which means a team conversation first.

---

## If you're pasting this project into an AI assistant

Use the ready-made prompt in your own module's `README.md` ("Prompt for
your AI assistant" section) rather than describing the task from scratch —
it already includes the relevant slice of this contract and the guardrails
below. In any case, tell your assistant:

1. Only edit files inside your own `src/<your_module>/` directory (plus
   adding tests under `tests/`). Don't touch other modules' files.
2. Keep every function/class signature in the contract above byte-for-byte
   identical — same name, same parameter names and order, same field
   names. Implementation details are yours to change freely.
3. Don't add new third-party dependencies without adding them to
   `requirements.txt` and flagging it in the PR.
4. Before considering it done, run from the repo root:
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ruff check .
   pytest
   ```
   All of `tests/test_contracts.py` and `tests/test_smoke.py` must still
   pass — those are the tests that catch a different AI assistant's code
   not fitting together with yours.
