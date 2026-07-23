"""Test twin for parts/architect.py -- the advisory Architect NPC.

It navigates: given a question, it points at the right command or catalog part.
The brain is a swappable seam, so a fake proves the interface without a network."""

import pytest

from forge import handle_command
from parts.architect import (
    ArchitectError,
    ClaudeAdvisor,
    build_claude_advisor,
    consult,
)
from parts.world.session import SESSIONS, Session

# --- a fake Anthropic client: the same shape the SDK exposes, no network -----


class _FakeBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self.content = [_FakeBlock(text)]


class _FakeMessages:
    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.seen: dict = {}

    def create(self, **kwargs):
        self.seen = kwargs
        return _FakeMessage(self._reply)


class _FakeClient:
    def __init__(self, reply: str = "Run `diagnostics`.") -> None:
        self.messages = _FakeMessages(reply)


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


# --- the Claude-backed brain: architecture in place, proven with a fake ------


def test_claude_advisor_calls_the_messages_api_with_the_right_model():
    client = _FakeClient(reply="Try `reuse audit`.")
    out = ClaudeAdvisor(client).advise("how do I find an audit part?")
    assert "Try `reuse audit`." in out
    assert client.messages.seen["model"] == "claude-opus-4-8"
    assert client.messages.seen["system"].startswith("You are the Architect")


def test_claude_advisor_redacts_secrets_before_sending():
    client = _FakeClient()
    ClaudeAdvisor(client).advise("my password=hunter2 and api_key=sk-abcdef123")
    sent = client.messages.seen["messages"][0]["content"]
    assert "hunter2" not in sent
    assert "sk-abcdef123" not in sent
    assert "[redacted]" in sent


def test_claude_advisor_empty_prompt_never_calls_the_api():
    client = _FakeClient()
    assert "waits" in ClaudeAdvisor(client).advise("   ").lower()
    assert client.messages.seen == {}  # no network call for an empty question


def test_claude_advisor_handles_an_empty_reply():
    assert "no counsel" in ClaudeAdvisor(_FakeClient(reply="")).advise("hello").lower()


def test_claude_advisor_is_a_valid_advisor_through_consult():
    # The seam holds: a Claude brain can be injected exactly like the local one.
    out = consult("anything", advisor=ClaudeAdvisor(_FakeClient(reply="ok")))
    assert "ok" in out


def test_build_claude_advisor_refuses_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ArchitectError) as err:
        build_claude_advisor()
    assert "ANTHROPIC_API_KEY" in str(err.value)


def test_default_brain_stays_local_and_offline(monkeypatch):
    # With Claude requested but no key, consult falls back to the local guide, and says so.
    monkeypatch.setenv("CODEFORGE_ARCHITECT", "claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = consult("how do I run the tests?")
    assert "local guide" in out  # honest note: the gap is surfaced, not hidden
    assert "diagnostics" in out or "run tests" in out


def test_no_env_uses_local_silently(monkeypatch):
    monkeypatch.delenv("CODEFORGE_ARCHITECT", raising=False)
    out = consult("how do I run the tests?")
    assert "local guide" not in out  # no note when Claude was never requested
