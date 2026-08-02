"""Test twin for kernel/world/chat.py -- the world channel.

Acceptance: a named hero's line reaches every OTHER online hero (not an echo of itself), and the
speaker gets a 'You:' confirmation. Refusal / safety: an empty message and a speaker not yet in the
world (unnamed, still at the login desk) are both refused, and nothing is broadcast.
"""

from __future__ import annotations

from kernel.world import chat, events
from kernel.world.session import SESSIONS, Session


def _hero(name: str, *, named: bool = True) -> Session:
    return SESSIONS.setdefault(name, Session(player_id=name, location="hall", named=named))


def _listen(name: str) -> list[str]:
    """Bind a heard-lines sink for `name` and return the growing list."""
    heard: list[str] = []
    events.bind_echo(name, heard.append)
    return heard


def _teardown() -> None:
    for name in list(SESSIONS):
        events.unbind_echo(name)
        SESSIONS.pop(name, None)


# --- acceptance -------------------------------------------------------------------------------
def test_the_world_hears_a_shout_but_not_the_speaker():
    try:
        alia = _hero("alia")
        _hero("bram")
        _hero("cade")
        heard_b, heard_c = _listen("bram"), _listen("cade")
        heard_a = _listen("alia")
        out = chat.world_say(alia, "hail the world")
        assert out == "[World] You: hail the world"
        assert any("[World] Alia: hail the world" in line for line in heard_b)
        assert any("[World] Alia: hail the world" in line for line in heard_c)
        assert heard_a == []  # the speaker hears it only as the 'You:' return, not on the channel
    finally:
        _teardown()


def test_the_message_case_is_preserved():
    try:
        alia = _hero("alia")
        _hero("bram")
        heard_b = _listen("bram")
        chat.world_say(alia, "LFG Dragon NOW")
        assert any("LFG Dragon NOW" in line for line in heard_b)
    finally:
        _teardown()


# --- refusal / safety --------------------------------------------------------------------------
def test_an_empty_message_is_refused():
    try:
        alia = _hero("alia")
        heard_b = _listen("bram")
        _hero("bram")
        assert "say what to the world" in chat.world_say(alia, "   ").lower()
        assert heard_b == []  # nothing broadcast
    finally:
        _teardown()


def test_a_speaker_not_yet_in_the_world_is_refused():
    try:
        stranger = _hero("stranger", named=False)  # still at the login desk
        _hero("bram")
        heard_b = _listen("bram")
        assert "enter the world" in chat.world_say(stranger, "hello?").lower()
        assert heard_b == []
    finally:
        _teardown()


# --- the verb is reachable through the engine tick --------------------------------------------
def test_the_chat_verb_is_reachable():
    import forge

    try:
        alia = _hero("alia")
        assert forge.handle_command(alia, "chat testing") == "[World] You: testing"
    finally:
        _teardown()


def test_world_say_pushes_a_comm_channel_frame():
    frames: list = []
    try:
        alia = _hero("alia")
        _hero("bram")
        events.bind_gmcp("bram", lambda pkg, data: frames.append((pkg, data)))
        chat.world_say(alia, "LFG dragon")
        assert (
            "Comm.Channel",
            {"channel": "world", "from": "Alia", "text": "LFG dragon"},
        ) in frames
    finally:
        events.unbind_gmcp("bram")
        _teardown()
