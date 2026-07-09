"""Test twin for parts/assessment.py -- the AssessmentEngine.

Acceptance: the shipped Python lesson loads and scores. Refusal: a malformed
bank fails loud rather than serving a broken question."""

import pytest

from parts.assessment import (
    LessonError,
    available_lessons,
    find_lesson,
    is_correct,
    load_lesson,
)

_GOOD = """
title: Demo Lesson
subject: demo
questions:
  - id: q1
    prompt: What is 2 + 2?
    choices: {A: "3", B: "4", C: "5", D: "22"}
    correct: B
    hint: add them
    explanation: two and two make four
"""


def _write(tmp_path, text: str):
    path = tmp_path / "demo.yaml"
    path.write_text(text)
    return path


def test_loads_the_shipped_python_lesson():
    lesson = find_lesson("python")  # lessons/python_basics.yaml
    assert lesson is not None
    assert len(lesson.questions) == 10
    assert all(q.correct in ("A", "B", "C", "D") for q in lesson.questions)
    assert all(set(q.choices) == {"A", "B", "C", "D"} for q in lesson.questions)


def test_load_and_check_an_answer(tmp_path):
    lesson = load_lesson(_write(tmp_path, _GOOD))
    assert lesson.title == "Demo Lesson" and lesson.subject == "demo"
    question = lesson.questions[0]
    assert is_correct(question, "b")  # case-insensitive
    assert not is_correct(question, "A")


def test_available_lessons_reads_a_directory(tmp_path):
    _write(tmp_path, _GOOD)
    lessons = available_lessons(tmp_path)
    assert len(lessons) == 1 and lessons[0].subject == "demo"


def test_missing_field_fails_loud(tmp_path):
    bad = _write(tmp_path, "title: X\nquestions:\n  - id: q1\n    prompt: p\n")
    with pytest.raises(LessonError):
        load_lesson(bad)


def test_wrong_choice_set_fails_loud(tmp_path):
    bad = _write(
        tmp_path,
        "title: X\nquestions:\n  - id: q1\n    prompt: p\n"
        "    choices: {A: a, B: b}\n    correct: A\n    hint: h\n    explanation: e\n",
    )
    with pytest.raises(LessonError):
        load_lesson(bad)
