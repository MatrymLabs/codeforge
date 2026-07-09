"""Test twin for parts/architect.py -- the advisory Architect NPC.

It navigates: given a question, it points at the right command or catalog part.
The brain is a swappable seam, so a fake proves the interface without a network."""

import pytest

from forge import handle_command
from parts.architect import consult
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def test_navigates_to_the_diagnostic_commands():
    out = consult("how do I run the tests?")
    assert "diagnostics" in out or "run tests" in out


def test_points_at_a_matching_catalog_part():
    out = consult("I need audit logging for a records system")
    assert "event-ledger" in out.lower()  # the Event Ledger's audit-trail reuse


def test_empty_prompt_asks_for_a_question():
    assert "waits" in consult("").lower() or "ask" in consult("").lower()


def test_orients_a_lost_newcomer():
    out = consult("I'm new here, where do I start?")
    assert "workshop" in out.lower()


def test_brain_is_a_swappable_seam():
    class FakeAdvisor:
        def advise(self, prompt: str) -> str:
            return f"FAKE:{prompt}"

    assert consult("hello", advisor=FakeAdvisor()) == "FAKE:hello"


def test_ai_command_reachable_through_the_tick():
    session = Session(player_id="builder")
    SESSIONS["builder"] = session
    reply = handle_command(session, "ai how do I run tests")
    assert "Architect" in reply
    assert "diagnostics" in reply or "run tests" in reply
