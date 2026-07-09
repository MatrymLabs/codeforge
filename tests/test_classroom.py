"""Test twin for parts/classroom.py -- Professor Codex and the lesson loop.

The whole loop is proven through the engine tick: talk (room-gated), list, start,
question, hint, answer (right and wrong), progress."""

import pytest

from forge import handle_command
from parts.classroom import _LEARNERS
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh():
    SESSIONS.clear()
    _LEARNERS.clear()
    yield
    SESSIONS.clear()
    _LEARNERS.clear()


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
