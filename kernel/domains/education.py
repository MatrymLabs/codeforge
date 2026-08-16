"""CARD: education -- the first real domain module: a minimal Education module (lessons).

This is the first concrete proof that a Seed can LOAD a domain module, not just record that it
selected one. It satisfies the neutral `kernel.seedlab.domain.DomainModule` contract (name / title /
capabilities) and carries one honest, working capability -- a lesson book -- so an education Seed
provisions and resolves to something real. Deliberately small: lessons are the seed of the education
module (assessments, learning paths, roles come later, each their own honest slice).

Grammar before worlds, from the other side: this module is stdlib-only and imports NO game world; an
education Seed loads exactly this and never combat. It lives in kernel/domains/ (a domain layer),
which the domain-neutral platform is forbidden to import -- the composition root registers it.

Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_LABEL = re.compile(r"^[a-z0-9_]+$")


class EducationError(Exception):
    """An education-module operation was refused (bad lesson id, duplicate). Fails loud."""


@dataclass(frozen=True)
class Lesson:
    """One lesson: a stable lowercase_snake_case id and a human title. Frozen -- a lesson's identity
    does not change once added."""

    lesson_id: str
    title: str

    def __post_init__(self) -> None:
        if not _LABEL.match(self.lesson_id or ""):
            raise EducationError(f"lesson id {self.lesson_id!r} must be lowercase_snake_case")
        if not self.title or not self.title.strip():
            raise EducationError("a lesson needs a non-empty title")


@dataclass
class LessonBook:
    """The education module's one capability: an ordered, unique set of lessons. Add fails loud on a
    duplicate id; listing preserves insertion order (a curriculum is a sequence, not a set)."""

    _lessons: dict[str, Lesson] = field(default_factory=dict)

    def add(self, lesson_id: str, title: str) -> Lesson:
        if lesson_id in self._lessons:
            raise EducationError(f"lesson {lesson_id!r} already exists")
        lesson = Lesson(lesson_id, title)
        self._lessons[lesson_id] = lesson
        return lesson

    def all(self) -> list[Lesson]:
        return list(self._lessons.values())

    def __len__(self) -> int:
        return len(self._lessons)


@dataclass
class EducationModule:
    """The Education domain module. Satisfies DomainModule (name / title / capabilities) and exposes
        a lesson book. `name` is the key an education BlueprintSpec selects; it is FROZEN as
    "education"."""

    name: str = "education"
    title: str = "Education"
    capabilities: tuple[str, ...] = ("lessons",)
    lessons: LessonBook = field(default_factory=LessonBook)
