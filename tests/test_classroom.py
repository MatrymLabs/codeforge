"""Test twin for parts/classroom.py -- Professor Codex and the lesson loop.

The whole loop is proven through the engine tick: talk (room-gated), list, start,
question, hint, answer (right and wrong), progress."""

import pytest

from forge import handle_command
from parts.assessment import find_lesson
from parts.classroom import _ACHIEVEMENTS, _LEARNERS, demonstrated
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh():
    SESSIONS.clear()
    _LEARNERS.clear()
    _ACHIEVEMENTS.clear()
    yield
    SESSIONS.clear()
    _LEARNERS.clear()
    _ACHIEVEMENTS.clear()


def _student(location: str = "classroom") -> Session:
    session = Session(player_id="student")
    session.location = location
    SESSIONS["student"] = session
    return session


def test_talk_codex_requires_being_in_the_classroom():
    session = _student(location="forge")  # Codex isn't here
    assert "no one" in handle_command(session, "talk codex").lower()
    session.location = "classroom"
    assert "Professor Codex" in handle_command(session, "talk codex")


def test_full_lesson_loop_through_the_tick():
    session = _student()
    assert "Python Basics" in handle_command(session, "lesson list")
    assert "question" in handle_command(session, "lesson start python").lower()
    assert "Question 1 of 10" in handle_command(session, "question")
    assert "hint" in handle_command(session, "hint").lower()
    feedback = handle_command(session, "answer B")  # q01's correct answer is B
    assert "Correct" in feedback
    prog = handle_command(session, "progress")
    assert "1 / 10 answered" in prog and "1 correct" in prog


def test_a_wrong_answer_is_marked_with_the_right_one():
    session = _student()
    handle_command(session, "lesson start python")
    handle_command(session, "question")
    feedback = handle_command(session, "answer A")  # wrong; correct is B
    assert "Not quite" in feedback
    assert "answer was B" in feedback


def test_answering_without_a_lesson_is_guided():
    session = _student()
    assert "No lesson" in handle_command(session, "answer A")


def _run_lesson(session: Session, correct: bool) -> str:
    """Drive the whole python lesson through the tick; return the final answer's feedback.
    `correct=True` answers every question right (a pass); False answers every one wrong."""
    lesson = find_lesson("python")
    assert lesson is not None
    handle_command(session, "lesson start python")
    feedback = ""
    for question in lesson.questions:
        handle_command(session, "question")
        pick = question.correct if correct else ("A" if question.correct != "A" else "B")
        feedback = handle_command(session, f"answer {pick}")
    return feedback


def test_passing_a_bound_lesson_unlocks_the_skill():
    # The achievement: a full pass on a skill-bound lesson unlocks demonstrated ownership.
    session = _student()
    final = _run_lesson(session, correct=True)
    assert "ACHIEVEMENT UNLOCKED" in final
    assert demonstrated("student") == {"entry.python.basics": 2}


def test_failing_a_lesson_earns_no_unlock():
    # A below-threshold run earns nothing -- the unlock must be honest, not a participation prize.
    session = _student()
    final = _run_lesson(session, correct=False)
    assert "ACHIEVEMENT UNLOCKED" not in final
    assert demonstrated("student") == {}


def test_a_lesson_can_never_grant_above_the_cap():
    # Even a lesson declaring earns_level 5 unlocks at most DEMONSTRATED_CAP -- a lesson never
    # grants level 4 (defendable); that needs a written keel record (KeelGate).
    from parts.assessment import Lesson, Question
    from parts.classroom import DEMONSTRATED_CAP, _award_on_completion, _Learner

    q = Question("q", "p", {"A": "a", "B": "b", "C": "c", "D": "d"}, "A", "h", "e")
    greedy = Lesson("L", "x", "X", [q], proves_skill="entry.python.basics", earns_level=5)
    learner = _Learner(lesson=greedy, correct=1, index=1)
    _award_on_completion("capped", learner)
    assert demonstrated("capped")["entry.python.basics"] == DEMONSTRATED_CAP


def test_achievements_view_starts_empty_and_is_reachable():
    session = _student()
    assert "No achievements yet" in handle_command(session, "achievements")


def test_achievements_view_lists_an_unlocked_skill():
    session = _student()
    _run_lesson(session, correct=True)
    board = handle_command(session, "achievements")
    assert "Show solid Python understanding" in board
    assert "1 skill(s) demonstrated" in board


def test_re_passing_a_lesson_does_not_repeat_the_achievement():
    # Once a skill is demonstrated at a level, re-passing the same lesson does not re-award
    # (no duplicate ceremony); the demonstrated level is unchanged.
    session = _student()
    _run_lesson(session, correct=True)
    second = _run_lesson(session, correct=True)
    assert "ACHIEVEMENT UNLOCKED" not in second
    assert demonstrated("student") == {"entry.python.basics": 2}
