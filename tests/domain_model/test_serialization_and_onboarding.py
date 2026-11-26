import json

import pytest

from domain_model import StudentTaskMapping, TaskType, recommend_task_type
from domain_model.mapping import SCHEMA_VERSION
from domain_model.onboarding import main, parse_task_choice, run_onboarding

LOW, MEDIUM, HIGH = 0.2, 0.5, 0.8


def _learned() -> StudentTaskMapping:
    mapping = StudentTaskMapping.from_survey("s1", {"low": "problem_set"})
    for energy, chosen in [(LOW, TaskType.MEMORIZATION)] * 4 + [(MEDIUM, TaskType.READING)] * 2:
        mapping.record_choice(energy, chosen)
    mapping.record_choice(MEDIUM, TaskType.REVIEW)
    return mapping


def _round_trip(mapping: StudentTaskMapping) -> StudentTaskMapping:
    return StudentTaskMapping.from_dict(json.loads(json.dumps(mapping.to_dict())))


def scripted(*answers):
    it = iter(answers)
    return lambda _prompt: next(it)


# -- serialization -----------------------------------------------------------


def test_mapping_round_trips_through_json():
    original = _learned()
    restored = _round_trip(original)
    assert restored == original  # dataclass fields
    assert restored.to_dict() == original.to_dict()  # plus survey and counts
    for bucket in ("low", "medium", "high"):
        assert restored.prior(bucket) == original.prior(bucket)
        assert restored.choice_counts(bucket) == original.choice_counts(bucket)


def test_to_dict_is_plain_json_with_a_version():
    data = _learned().to_dict()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["survey"] == {"low": "problem_set"}
    assert data["choice_counts"]["low"] == {"memorization": 4}
    assert data["choice_counts"]["high"] == {}
    assert json.loads(json.dumps(data)) == data


@pytest.mark.parametrize("energy", [0.0, LOW, 0.4, MEDIUM, HIGH, 1.0])
def test_round_trip_keeps_recommendations_and_explanations(energy):
    original = _learned()
    assert recommend_task_type(_round_trip(original), energy) == recommend_task_type(
        original, energy
    )


def test_round_trip_keeps_learning_the_same_way():
    original, restored = _learned(), _round_trip(_learned())
    for mapping in (original, restored):
        mapping.record_choice(MEDIUM, TaskType.REVIEW)
        mapping.record_choice(MEDIUM, TaskType.REVIEW)
    assert restored.to_dict() == original.to_dict()
    assert restored.blend_summary() == original.blend_summary()


def test_minimal_dict_gets_new_mapping_defaults():
    restored = StudentTaskMapping.from_dict({"student_id": "s2"})
    assert restored.to_dict() == StudentTaskMapping("s2").to_dict()


def test_dict_without_counts_behaves_like_fields_only_mapping():
    data = {"student_id": "s3", "learned_weight": 0.5, "preferences": {"low": "review"}}
    restored = StudentTaskMapping.from_dict(data)
    built = StudentTaskMapping("s3", learned_weight=0.5, preferences={"low": TaskType.REVIEW})
    assert restored.to_dict() == built.to_dict()


def test_other_schema_version_is_rejected():
    data = _learned().to_dict() | {"schema_version": SCHEMA_VERSION + 1}
    with pytest.raises(ValueError, match="schema_version"):
        StudentTaskMapping.from_dict(data)


@pytest.mark.parametrize(
    "change",
    [
        {"learned_weight": 1.5},
        {"learned_weight": "lots"},
        {"preferences": {"sleepy": "reading"}},
        {"preferences": {"low": "napping"}},
        {"survey": {"low": "napping"}},
        {"choice_counts": {"low": {"reading": -1}}},
        {"choice_counts": {"low": {"reading": 1.5}}},
        {"choice_counts": {"low": {"napping": 2}}},
        {"choice_counts": {"sleepy": {"reading": 2}}},
    ],
)
def test_invalid_stored_mapping_is_rejected(change):
    with pytest.raises(ValueError):
        StudentTaskMapping.from_dict(_learned().to_dict() | change)


# -- onboarding --------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1", TaskType.PROBLEM_SET),
        (" 4 ", TaskType.MEMORIZATION),
        ("reading", TaskType.READING),
        ("Problem Sets", TaskType.PROBLEM_SET),
        ("problem_set", TaskType.PROBLEM_SET),
        ("flashcards", TaskType.MEMORIZATION),
        ("", None),
        ("skip", None),
        ("no preference", None),
    ],
)
def test_parse_task_choice(text, expected):
    assert parse_task_choice(text) == expected


@pytest.mark.parametrize("text", ["0", "5", "naps", "1 2"])
def test_parse_task_choice_rejects(text):
    with pytest.raises(ValueError):
        parse_task_choice(text)


def test_onboarding_applies_answers_and_reasks_on_bad_input():
    mapping, said = StudentTaskMapping("s1"), []
    answers = run_onboarding(mapping, ask=scripted("naps", "1", "", "problem sets"), say=said.append)
    assert answers == {"low": TaskType.PROBLEM_SET, "high": TaskType.PROBLEM_SET}
    assert mapping.prior("low") == (TaskType.PROBLEM_SET, "survey")
    assert mapping.prior("medium") == (TaskType.REVIEW, "default")  # skipped
    assert any("number from 1 to 4" in line for line in said)  # re-asked after "naps"
    assert any("because you said you prefer problem sets when you're tired" in line for line in said)


def test_cli_saves_a_loadable_mapping(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", scripted("2", "3", "4"))
    out = tmp_path / "profiles" / "s9_tasks.json"
    assert main(["--student-id", "s9", "--out", str(out)]) == 0
    restored = StudentTaskMapping.from_dict(json.loads(out.read_text(encoding="utf-8")))
    assert restored.student_id == "s9"
    assert recommend_task_type(restored, LOW)[0] is TaskType.READING
    assert recommend_task_type(restored, HIGH)[0] is TaskType.MEMORIZATION
    assert "saved to" in capsys.readouterr().out


def test_cli_refuses_to_overwrite(tmp_path):
    out = tmp_path / "s1_tasks.json"
    out.write_text("{}", encoding="utf-8")
    assert main(["--student-id", "s1", "--out", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "{}"


def test_cli_cancel_saves_nothing(tmp_path, monkeypatch):
    def cancel(_prompt):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", cancel)
    out = tmp_path / "s1_tasks.json"
    assert main(["--student-id", "s1", "--out", str(out)]) == 1
    assert not out.exists()
