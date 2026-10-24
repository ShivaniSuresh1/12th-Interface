# Design Decisions

Carried over from the team's "Design Questions Activity" (Shivani, Vyshnavi,
Harshini present). Six open questions, each resolved in favor of a hybrid /
negotiated approach over the purely automatic or purely manual extremes.

## Q1 — How do we estimate a student's energy?

**Chosen:** Hybrid — a sleep-based baseline estimate, corrected by a short
conversational check-in at every session boundary.

- Catches hidden sleep debt a self-report alone would miss, and lets the
  student correct a baseline that's wrong for that day.
- Two signals can disagree; needs a rule for weighting them (see Q4's
  decaying blend, reused here).

Owner: **Shivani** (User Model). See `src/user_model/README.md`.

## Q2 — How do we capture initial preferences (cold start)?

**Chosen:** Short survey + a fixed default rule (hard tasks at high energy)
active until enough real data exists.

- Usable from day one; survey stays short.
- Default rule fits some students poorly at first — fades out as real
  choices accumulate (see Q4).

Owner: **Shivani** (User Model).

## Q3 — How is task difficulty represented (domain model)?

**Chosen:** Small fixed taxonomy — problem sets, reading, review,
memorization — with a default difficulty per type, adjustable by the
student.

- Tractable matching, easy to explain.
- Some tasks fit no category or span several.

Owner: **Vyshnavi** (Domain Model). See `src/domain_model/README.md`.

## Q4 — How is the energy-to-task mapping represented and updated?

**Chosen:** Per-student weighted rule / lookup table, blending the Q2 survey
and learned choices with a decaying weight (PTIME-style): survey weighted
heavily at first, shifting to learned data as sessions accumulate, with the
shift itself visible to the student.

- Personal, explainable in one sentence ("because you usually do reading
  when tired"), improves over time.
- Slower to capture complex patterns; blend weights need tuning.
- Explicitly per-student, not a single fixed rule — some students prefer
  mechanical/objective tasks (problem sets) when tired because they have
  objective answers; others prefer passive tasks (reading) they can do
  while lounging.

Owner: **Vyshnavi** (Domain Model).

## Q5 — How does replanning happen when something changes?

**Chosen:** Negotiated — system proposes a change and narrates it; student
accepts or edits with one tap.

- Keeps control with the student; every accept/edit/reject is a labeled
  example of real preference, feeding back into Q4's learned mapping.
- More interaction than silent rescheduling; must be kept brief.

Owner: **Soumyadip** (Negotiation & Replanning). See `src/negotiation/README.md`.

## Q6 — When and how often should the planner check in?

**Chosen:** Check-ins at session boundaries (start, end, breaks), capped per
day, batched with any proposed replan into a single message.

- Respects focus time, aligns with Pomodoro/Flowtime-style breaks.
- Mid-session disruptions wait until the next boundary.

Owner: **Soumyadip** (Negotiation & Replanning).

## How the decisions interact

- **Q1 × Q4:** A rough, self-reported energy signal makes a complex learned
  model unreliable — the hybrid estimate is matched to a simple per-student
  lookup table, not a black box.
- **Q3 × Q4:** A learned mapping is only tractable with a small fixed task
  taxonomy; open-ended tasks would need far more examples per student.
- **Q2 × Q4:** A short survey means little initial data, hence the default
  rule and the decaying survey-to-learned blend.
- **Q5 × Q4:** Negotiated replanning is the main source of learning data;
  silent rescheduling would remove it.
- **Q5 × Q6:** Negotiation adds interaction while Q6 tries to limit
  interruptions — resolved by batching the check-in and any replan into one
  message at a session boundary.
- **Q1 × Q6:** The conversational correction to the energy estimate only
  happens at check-ins, so fewer check-ins mean a staler estimate.
- **Errors compound across the pipeline.** A wrong energy read → wrong task
  match → wrong reschedule. Mitigation: let the student edit at *each*
  stage, not just the end, so a bad estimate doesn't get a chance to train
  the mapping.
- **Explainability ties Q3, Q4, Q5 together.** A narrated reschedule needs a
  one-sentence "because", which only works with a fixed taxonomy and a
  transparent (not black-box) mapping.

## State assessment is hybrid, and state → task mapping is per-student

Per professor feedback: state assessment should combine automated signals
(sleep/schedule data) *and* conversation (the check-in), not rely on either
alone — that's exactly what Q1's hybrid estimate does. And the mapping from
state to task (Q4) is intentionally per-student rather than universal,
because students differ in what they want to do when tired: some prefer
objective/mechanical tasks like problem sets (clear right answers, less
judgment needed while fatigued), others prefer passive tasks like reading
they can do while lounging. The per-student weighted lookup table is what
lets each student's planner converge to their own answer rather than
enforcing one rule for everyone.

## Reference diagrams

- Figure 1 (Q1 hybrid energy-estimation loop) and Figure 2 (Q2–Q5 sketches)
  from the Phase 2 report are the canonical pictures for this doc — see the
  team's shared project materials / Phase 2 report for the rendered images.
