"""CARD: chat -- the world channel: one line heard by every hero online right now.

The social layer's widest voice. Party reaches your band, guild reaches your order, mail reaches a
single offline hero; this reaches EVERYONE currently playing, the town square of the whole world. It
is transient by nature (a live channel, nothing persisted) and moves no world state: it only carries
a line of text from one hero to every other hero connected at that moment.

A speaker must be a named hero already in the world (the login desk does not chat), and a message
must not be empty. This is deliberately the smallest useful version: a per-speaker rate limit and an
opt-out mute are documented extension points, not built, until a crowd is large enough to need them.
"""

from __future__ import annotations

from parts.world.events import announce_to
from parts.world.session import Session, display_name, roster


def world_say(session: Session, message: str) -> str:
    """`chat <message>`: speak on the world channel, heard by every other hero online. Fails loud on
    a speaker not yet in the world, or an empty message. The spine preserves the message's case."""
    if not session.named:
        return "Enter the world before you speak to it."
    text = message.strip()
    if not text:
        return "Say what to the world? (chat <message>)"
    announce_to(
        roster(),
        f"\n[World] {display_name(session.player_id)}: {text}",
        exclude=session.player_id,
    )
    return f"[World] You: {text}"
