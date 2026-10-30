import pytest

from domain_model import Task, TaskType
from domain_model.taxonomy import DEFAULT_DIFFICULTY


def test_default_difficulty_used_when_not_overridden():
    task = Task("t1", "Ch. 3 problems", TaskType.PROBLEM_SET)
    assert task.effective_difficulty() == DEFAULT_DIFFICULTY[TaskType.PROBLEM_SET]


def test_every_type_has_a_default_difficulty():
    assert set(DEFAULT_DIFFICULTY) == set(TaskType)


def test_student_override_and_reset():
    task = Task("t1", "Ch. 3 reading", TaskType.READING)
    task.set_difficulty(5)
    assert task.effective_difficulty() == 5
    task.set_difficulty(None)
    assert task.effective_difficulty() == DEFAULT_DIFFICULTY[TaskType.READING]


def test_string_task_type_is_coerced():
    assert Task("t1", "Flashcards", "memorization").task_type is TaskType.MEMORIZATION


@pytest.mark.parametrize("bad", [0, 6, -1])
def test_out_of_range_difficulty_rejected(bad):
    with pytest.raises(ValueError):
        Task("t1", "x", TaskType.REVIEW, difficulty=bad)
    task = Task("t1", "x", TaskType.REVIEW)
    with pytest.raises(ValueError):
        task.set_difficulty(bad)


@pytest.mark.parametrize("bad", [2.5, "3", True])
def test_non_int_difficulty_rejected(bad):
    with pytest.raises(TypeError):
        Task("t1", "x", TaskType.REVIEW, difficulty=bad)


def test_unknown_task_type_rejected():
    with pytest.raises(ValueError):
        Task("t1", "x", "lab_report")


def test_labels_are_readable():
    assert TaskType.PROBLEM_SET.label == "problem sets"
    assert all(t.label for t in TaskType)
