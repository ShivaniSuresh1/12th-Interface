import math

import pytest

from domain_model import StudentTaskMapping, Task, TaskType, recommend_task, recommend_task_type
from domain_model.mapping import HIGH_ENERGY, LOW_ENERGY, PRIOR_STRENGTH

LOW, MEDIUM, HIGH = 0.2, 0.5, 0.8


# -- cold start: default rule ------------------------------------------------


@pytest.mark.parametrize(
    ("energy", "expected"),
    [(HIGH, TaskType.PROBLEM_SET), (MEDIUM, TaskType.REVIEW), (LOW, TaskType.READING)],
)
def test_cold_start_uses_default_rule(energy, expected):
    task_type, why = recommend_task_type(StudentTaskMapping("s1"), energy)
    assert task_type is expected
    assert why.startswith("because")
    assert "default" in why


@pytest.mark.parametrize(
    ("energy", "bucket_type"),
    [
        (0.0, TaskType.READING),
        (LOW_ENERGY - 0.001, TaskType.READING),
        (LOW_ENERGY, TaskType.REVIEW),
        (HIGH_ENERGY - 0.001, TaskType.REVIEW),
        (HIGH_ENERGY, TaskType.PROBLEM_SET),
        (1.0, TaskType.PROBLEM_SET),
    ],
)
def test_bucket_edges(energy, bucket_type):
    assert recommend_task_type(StudentTaskMapping("s1"), energy)[0] is bucket_type


@pytest.mark.parametrize("bad", [-0.01, 1.01, math.nan, math.inf])
def test_out_of_range_energy_rejected(bad):
    with pytest.raises(ValueError):
        recommend_task_type(StudentTaskMapping("s1"), bad)


def test_non_numeric_energy_rejected():
    with pytest.raises(TypeError):
        recommend_task_type(StudentTaskMapping("s1"), "0.5")


# -- survey prior --------------------------------------------------------------


def test_survey_answer_replaces_default():
    mapping = StudentTaskMapping.from_survey("s1", {"low": "problem_set"})
    task_type, why = recommend_task_type(mapping, LOW)
    assert task_type is TaskType.PROBLEM_SET
    assert why == "because you said you prefer problem sets when you're tired"
    # Buckets the survey skipped still use the default rule.
    assert recommend_task_type(mapping, HIGH)[0] is TaskType.PROBLEM_SET
    assert recommend_task_type(mapping, MEDIUM)[0] is TaskType.REVIEW


def test_survey_rejects_unknown_bucket_or_type():
    with pytest.raises(ValueError):
        StudentTaskMapping.from_survey("s1", {"sleepy": "reading"})
    with pytest.raises(ValueError):
        StudentTaskMapping.from_survey("s1", {"low": "napping"})


# -- learning + decaying blend ---------------------------------------------------


def test_record_choice_updates_preferences_and_weight():
    mapping = StudentTaskMapping("s1")
    mapping.record_choice(LOW, TaskType.PROBLEM_SET)
    assert mapping.preferences["low"] is TaskType.PROBLEM_SET
    assert mapping.learned_weight == pytest.approx(1 / (1 + PRIOR_STRENGTH))


def test_learned_weight_follows_n_over_n_plus_k():
    mapping = StudentTaskMapping("s1")
    for n in range(1, 21):
        mapping.record_choice(MEDIUM, TaskType.REVIEW)
        assert mapping.learned_weight == pytest.approx(n / (n + PRIOR_STRENGTH))
    assert mapping.learned_weight < 1.0


def test_one_choice_does_not_override_the_prior():
    mapping = StudentTaskMapping("s1")
    mapping.record_choice(LOW, TaskType.PROBLEM_SET)
    task_type, why = recommend_task_type(mapping, LOW)
    assert task_type is TaskType.READING
    assert why == (
        "because reading is the starting default when you're tired, until I learn what "
        "you prefer (your 1 choice so far isn't enough to change that yet)"
    )


def test_repeated_choices_eventually_override_the_default():
    mapping = StudentTaskMapping("s1")
    flipped_at = None
    for n in range(1, 11):
        mapping.record_choice(LOW, TaskType.PROBLEM_SET)
        if recommend_task_type(mapping, LOW)[0] is TaskType.PROBLEM_SET:
            flipped_at = n
            break
    # learned_weight >= 0.5 at n = PRIOR_STRENGTH, so it flips by then.
    assert flipped_at == PRIOR_STRENGTH
    _, why = recommend_task_type(mapping, LOW)
    assert why == (
        f"because you picked problem sets in {PRIOR_STRENGTH} of your {PRIOR_STRENGTH} "
        "choices when you're tired, which now outweighs the starting default"
    )


def test_learning_overrides_survey_too():
    mapping = StudentTaskMapping.from_survey("s1", {"low": "reading"})
    for _ in range(PRIOR_STRENGTH):
        mapping.record_choice(LOW, TaskType.MEMORIZATION)
    task_type, why = recommend_task_type(mapping, LOW)
    assert task_type is TaskType.MEMORIZATION
    assert "your survey answer" in why


def test_agreeing_choices_explained_as_habit():
    mapping = StudentTaskMapping("s1")
    mapping.record_choice(LOW, TaskType.READING)
    assert recommend_task_type(mapping, LOW) == (
        TaskType.READING,
        "because you usually pick reading when you're tired",
    )


def test_learning_is_per_bucket():
    mapping = StudentTaskMapping("s1")
    for _ in range(10):
        mapping.record_choice(LOW, TaskType.PROBLEM_SET)
    assert recommend_task_type(mapping, LOW)[0] is TaskType.PROBLEM_SET
    # No choices recorded at high energy -> still the prior there.
    assert recommend_task_type(mapping, HIGH)[0] is TaskType.PROBLEM_SET
    assert recommend_task_type(mapping, MEDIUM)[0] is TaskType.REVIEW


def test_mixed_choices_follow_majority():
    mapping = StudentTaskMapping("s1")
    for t in [TaskType.REVIEW] * 6 + [TaskType.MEMORIZATION] * 3:
        mapping.record_choice(MEDIUM, t)
    assert mapping.preferences["medium"] is TaskType.REVIEW
    assert mapping.choice_counts("medium") == {TaskType.REVIEW: 6, TaskType.MEMORIZATION: 3}


def test_preference_tie_goes_to_most_recent_choice():
    mapping = StudentTaskMapping("s1")
    mapping.record_choice(MEDIUM, TaskType.REVIEW)
    mapping.record_choice(MEDIUM, TaskType.MEMORIZATION)
    assert mapping.preferences["medium"] is TaskType.MEMORIZATION


def test_record_choice_accepts_string_type():
    mapping = StudentTaskMapping("s1")
    mapping.record_choice(LOW, "review")
    assert mapping.preferences["low"] is TaskType.REVIEW


def test_record_choice_rejects_bad_energy():
    with pytest.raises(ValueError):
        StudentTaskMapping("s1").record_choice(1.5, TaskType.REVIEW)


def test_mapping_built_from_fields_only():
    # e.g. restored from storage, or built by hand in another module's test.
    mapping = StudentTaskMapping(
        "s1", learned_weight=1.0, preferences={"low": TaskType.PROBLEM_SET}
    )
    assert recommend_task_type(mapping, LOW)[0] is TaskType.PROBLEM_SET
    mapping.record_choice(LOW, TaskType.PROBLEM_SET)
    assert mapping.learned_weight == 1.0

    half = StudentTaskMapping("s2", learned_weight=0.5)
    half.record_choice(LOW, TaskType.REVIEW)
    # 0.5 corresponds to n = PRIOR_STRENGTH; one more choice -> n + 1.
    assert half.learned_weight == pytest.approx(
        (PRIOR_STRENGTH + 1) / (2 * PRIOR_STRENGTH + 1)
    )


def test_mapping_validates_fields():
    with pytest.raises(ValueError):
        StudentTaskMapping("s1", learned_weight=1.5)
    with pytest.raises(ValueError):
        StudentTaskMapping("s1", preferences={"sleepy": TaskType.READING})


# -- explainability ---------------------------------------------------------------


def _all_explanations():
    mappings = [StudentTaskMapping("a"), StudentTaskMapping.from_survey("b", {"low": "review"})]
    learner = StudentTaskMapping("c")
    for _ in range(3):
        learner.record_choice(LOW, TaskType.MEMORIZATION)
        learner.record_choice(HIGH, TaskType.PROBLEM_SET)
        mappings.append(learner)
    for mapping in mappings:
        for energy in (LOW, MEDIUM, HIGH):
            yield recommend_task_type(mapping, energy)[1]


def test_explanations_are_one_because_sentence():
    for why in _all_explanations():
        assert why.startswith("because ")
        assert "." not in why.rstrip(".")  # one sentence
        assert "\n" not in why


def test_blend_summary_shows_the_shift():
    mapping = StudentTaskMapping.from_survey("s1", {"low": "reading"})
    assert "survey" in mapping.blend_summary()
    for _ in range(PRIOR_STRENGTH):
        mapping.record_choice(LOW, TaskType.READING)
    assert mapping.blend_summary() == (
        "Your recommendations are now 50% based on your own choices "
        "and 50% on your survey answers."
    )


# -- picking a concrete task --------------------------------------------------------


def test_recommend_task_prefers_type_then_difficulty():
    tasks = [
        Task("a", "Hard reading", TaskType.READING, difficulty=5),
        Task("b", "Light reading", TaskType.READING, difficulty=1),
        Task("c", "Problem set", TaskType.PROBLEM_SET),
    ]
    task, why = recommend_task(StudentTaskMapping("s1"), 0.1, tasks)
    assert task.task_id == "b"
    assert why.startswith("because")


def test_recommend_task_falls_back_when_type_missing():
    tasks = [Task("c", "Ch. 4 problems", TaskType.PROBLEM_SET)]
    task, why = recommend_task(StudentTaskMapping("s1"), LOW, tasks)
    assert task.task_id == "c"
    assert "no reading tasks left" in why


def test_recommend_task_with_no_tasks():
    assert recommend_task(StudentTaskMapping("s1"), LOW, [])[0] is None
    with pytest.raises(ValueError):
        recommend_task(StudentTaskMapping("s1"), 2.0, [])
