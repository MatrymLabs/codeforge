"""Test twin for kernel/domains/education.py -- the first real domain module (Education / lessons).

Acceptance: the module declares its identity + capabilities honestly and carries a working lesson
book (add + list, insertion order preserved).

Refusal (fail loud): a duplicate lesson id, a non-snake_case id, and a blank title are refused.
"""

from __future__ import annotations

import pytest

from kernel.domains.education import EducationError, EducationModule, Lesson, LessonBook

# --- acceptance --------------------------------------------------------------------------------


def test_the_module_declares_its_identity_and_capabilities() -> None:
    module = EducationModule()
    assert module.name == "education"
    assert module.title == "Education"
    assert module.capabilities == ("lessons",)
    assert len(module.lessons) == 0


def test_lessons_add_and_list_in_order() -> None:
    book = LessonBook()
    book.add("cells_intro", "Intro to Cells")
    book.add("photosynthesis", "Photosynthesis")
    assert [lesson.lesson_id for lesson in book.all()] == ["cells_intro", "photosynthesis"]
    assert len(book) == 2
    assert book.all()[0] == Lesson("cells_intro", "Intro to Cells")


# --- refusal: fail loud ------------------------------------------------------------------------


def test_a_duplicate_lesson_is_refused() -> None:
    book = LessonBook()
    book.add("cells_intro", "Intro to Cells")
    with pytest.raises(EducationError, match="already exists"):
        book.add("cells_intro", "A different title")


def test_a_non_snake_case_lesson_id_is_refused() -> None:
    with pytest.raises(EducationError, match="snake_case"):
        Lesson("Cells Intro!", "Intro")


def test_a_blank_lesson_title_is_refused() -> None:
    with pytest.raises(EducationError, match="non-empty title"):
        Lesson("cells_intro", "  ")
