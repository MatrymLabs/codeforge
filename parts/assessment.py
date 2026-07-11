"""CARD: assessment -- the AssessmentEngine: a data-driven question engine.

Load a question bank, ask a question, check an answer, hand out a hint or an
explanation, and score a run. Domain-agnostic on purpose: the same engine drills
Python in the Classroom and, reused, powers compliance/finance/onboarding
knowledge checks. Questions are DATA (lessons/*.yaml); a malformed bank fails
loud at load, and nothing here has side effects.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CHOICES = ("A", "B", "C", "D")
_REQUIRED = ("id", "prompt", "choices", "correct", "hint", "explanation")


def _default_lessons_dir() -> Path:
    """Where lesson banks live -- resolved at call time so tests can point
    CODEFORGE_LESSONS at a fixture."""
    override = os.environ.get("CODEFORGE_LESSONS")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent.parent / "lessons"


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    choices: dict[str, str]  # {"A": "...", "B": "...", "C": "...", "D": "..."}
    correct: str  # one of CHOICES
    hint: str
    explanation: str


@dataclass(frozen=True)
class Lesson:
    id: str
    subject: str  # short key, e.g. "python"
    title: str
    questions: list[Question]
    proves_skill: str = ""  # optional: a career-board skill_id this lesson demonstrates
    earns_level: int = 0  # optional: the ownership level a pass demonstrates (capped by the caller)


class LessonError(ValueError):
    """A lesson bank is malformed -- fail loud, never load a bad question."""


def _coerce_question(raw: Any, index: int) -> Question:
    if not isinstance(raw, dict):
        raise LessonError(f"question #{index}: expected a mapping")
    missing = [key for key in _REQUIRED if key not in raw]
    if missing:
        raise LessonError(f"question #{index}: missing {', '.join(missing)}")
    choices = raw["choices"]
    if not isinstance(choices, dict) or set(choices) != set(CHOICES):
        raise LessonError(f"question {raw['id']!r}: choices must be exactly keys {CHOICES}")
    correct = str(raw["correct"]).strip().upper()
    if correct not in CHOICES:
        raise LessonError(f"question {raw['id']!r}: correct must be one of {CHOICES}")
    return Question(
        id=str(raw["id"]),
        prompt=str(raw["prompt"]).strip(),
        choices={key: str(choices[key]).strip() for key in CHOICES},
        correct=correct,
        hint=str(raw["hint"]).strip(),
        explanation=str(raw["explanation"]).strip(),
    )


def load_lesson(path: Path) -> Lesson:
    """Load and validate one lesson bank."""
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict) or "questions" not in data:
        raise LessonError(f"{path.name}: a lesson needs a 'title' and 'questions'")
    questions = [_coerce_question(q, i) for i, q in enumerate(data["questions"], start=1)]
    if not questions:
        raise LessonError(f"{path.name}: a lesson needs at least one question")
    earns_level = data.get("earns_level", 0)
    if not isinstance(earns_level, int) or isinstance(earns_level, bool) or earns_level < 0:
        raise LessonError(
            f"{path.name}: earns_level must be a non-negative int, got {earns_level!r}"
        )
    default_subject = path.stem.split("_")[0]
    return Lesson(
        id=str(data.get("id", path.stem)),
        subject=str(data.get("subject", default_subject)),
        title=str(data.get("title", path.stem.replace("_", " ").title())),
        questions=questions,
        proves_skill=str(data.get("proves_skill", "")),
        earns_level=earns_level,
    )


def available_lessons(lessons_dir: Path | None = None) -> list[Lesson]:
    """Every installed lesson, sorted by filename. Empty if none installed."""
    root = lessons_dir or _default_lessons_dir()
    if not root.is_dir():
        return []
    return [load_lesson(path) for path in sorted(root.glob("*.yaml"))]


def find_lesson(subject: str, lessons_dir: Path | None = None) -> Lesson | None:
    """Find a lesson by subject key or id (case-insensitive)."""
    key = subject.strip().lower()
    for lesson in available_lessons(lessons_dir):
        if key in (lesson.subject.lower(), lesson.id.lower()):
            return lesson
    return None


def is_correct(question: Question, choice: str) -> bool:
    """True if `choice` (a letter) is this question's correct answer."""
    return choice.strip().upper() == question.correct
