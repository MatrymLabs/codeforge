"""CARD: classroom -- Professor Codex and the Classroom of Practical Arts.

The thin game face over the AssessmentEngine: talk to Professor Codex, list
lessons, start one, get a question, answer it, ask for a hint, and check your
progress. Per-player progress lives here (in memory for now); the questions are
data (lessons/) and the scoring is the reusable engine. No AI API yet -- a local
question bank first, per the plan. A Socratic teacher: he asks better questions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parts.assessment import Lesson, Question, available_lessons, find_lesson, is_correct

CLASSROOM_ROOM = "classroom"

_GREETING = (
    "Professor Codex looks up from his ledger.\n"
    '"Welcome to the Classroom of Practical Arts. The Library can tell you what is\n'
    'true; this room tests whether you can use it."\n'
    "Choose a path: `lesson list`, then `lesson start <subject>`."
)


@dataclass
class _Learner:
    """One player's run through a lesson -- in-memory progress."""

    lesson: Lesson
    index: int = 0
    correct: int = 0
    answered: set[str] = field(default_factory=set)

    @property
    def current(self) -> Question | None:
        if self.index < len(self.lesson.questions):
            return self.lesson.questions[self.index]
        return None


_LEARNERS: dict[str, _Learner] = {}  # player_id -> run


def talk_to_codex() -> str:
    return _GREETING


def lesson_list() -> str:
    lessons = available_lessons()
    if not lessons:
        return "The lesson shelves are bare. (No lessons installed.)"
    lines = ["Professor Codex gestures at the lesson scrolls:"]
    for number, lesson in enumerate(lessons, start=1):
        lines.append(f"  {number}. {lesson.title}   (start: lesson start {lesson.subject})")
    return "\n".join(lines)


def lesson_start(player_id: str, subject: str) -> str:
    subject = subject.strip()
    if not subject:
        return "Start which lesson? Try: lesson list"
    lesson = find_lesson(subject)
    if lesson is None:
        return f"No lesson '{subject}'. Try: lesson list"
    _LEARNERS[player_id] = _Learner(lesson=lesson)
    return (
        "Professor Codex opens a worn notebook.\n"
        f'"{lesson.title}. {len(lesson.questions)} questions. '
        'Type `question` to begin."'
    )


def _render_question(learner: _Learner) -> str:
    question = learner.current
    assert question is not None  # callers check learner is mid-lesson
    total = len(learner.lesson.questions)
    lines = [f"Question {learner.index + 1} of {total}:", question.prompt, ""]
    lines += [f"  {letter}. {question.choices[letter]}" for letter in ("A", "B", "C", "D")]
    lines.append("\nAnswer with:  answer <A-D>    (or `hint`)")
    return "\n".join(lines)


def _score_line(learner: _Learner) -> str:
    total = len(learner.lesson.questions)
    return (
        f'Professor Codex closes his ledger. "{learner.lesson.title} complete - '
        f'{learner.correct} of {total} correct."'
    )


def ask_question(player_id: str) -> str:
    learner = _LEARNERS.get(player_id)
    if learner is None:
        return "No lesson in progress. Try: lesson list"
    if learner.current is None:
        return _score_line(learner)
    return _render_question(learner)


def submit_answer(player_id: str, choice: str) -> str:
    learner = _LEARNERS.get(player_id)
    if learner is None:
        return "No lesson in progress. Try: lesson start python"
    question = learner.current
    if question is None:
        return _score_line(learner)
    choice = choice.strip().upper()
    if choice not in ("A", "B", "C", "D"):
        return "Answer with a letter: answer A / B / C / D"
    right = is_correct(question, choice)
    learner.answered.add(question.id)
    if right:
        learner.correct += 1
    learner.index += 1
    verdict = (
        'Professor Codex nods. "Correct."'
        if right
        else f'Professor Codex taps the chalk. "Not quite - the answer was {question.correct}."'
    )
    body = f"{verdict}\n{question.explanation}"
    if learner.current is None:
        return f"{body}\n\n{_score_line(learner)}"
    return f"{body}\n\nType `question` for the next one."


def hint(player_id: str) -> str:
    learner = _LEARNERS.get(player_id)
    if learner is None or learner.current is None:
        return "No question waiting. Try: question"
    return f"Hint: {learner.current.hint}"


def progress(player_id: str) -> str:
    learner = _LEARNERS.get(player_id)
    if learner is None:
        return "No lesson in progress. Try: lesson list"
    total = len(learner.lesson.questions)
    return (
        f"{learner.lesson.title}: {len(learner.answered)} / {total} answered · "
        f"{learner.correct} correct"
    )
