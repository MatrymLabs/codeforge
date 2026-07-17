"""CARD: frames -- typed, per-recipient event frames for the room bus.

A Frame is a validated, STRUCTURED happening, not pre-rendered text: who did what,
in data form. A bare broadcast string is baked once for the whole room; a Frame
carries its fields so each sink can render it PER RECIPIENT -- the viewer's own
name, tense, or locale decided at delivery, not frozen at the call site. This is
the typed successor the events bus docstring promised; `events.announce_frame`
delivers it, asking each frame to `render_for` the player about to see it.

Frames are frozen and validate on construction: a malformed frame fails loud at
the call site (`ValueError`) rather than silently broadcasting a half-formed event.
State stays canonical; a Frame is a projection request, never a mutation.
"""

from __future__ import annotations

from dataclasses import dataclass

from parts.session import display_name


class Frame:
    """Marker base for a typed event frame. Subclasses are frozen dataclasses that
    carry structured fields and know how to render themselves for one viewer.

    Kept a plain marker (like parts.signal_bus.Signal) rather than an ABC so the
    contract is one method, tested directly."""

    def render_for(self, viewer_id: str) -> str:
        """Project this frame to the single line `viewer_id` should see."""
        raise NotImplementedError("a Frame subclass must implement render_for")


@dataclass(frozen=True)
class SpeechFrame(Frame):
    """Someone spoke a line aloud in a room."""

    speaker_id: str
    words: str

    def __post_init__(self) -> None:
        if not self.speaker_id:
            raise ValueError("SpeechFrame needs a speaker_id")
        if not self.words.strip():
            raise ValueError("SpeechFrame needs non-empty words")

    def render_for(self, viewer_id: str) -> str:
        # The per-recipient seam: today every bystander sees the same third-person
        # line, but the projection now happens HERE, at delivery, so a viewer's own
        # perspective (name, tense, locale) can diverge later without touching the
        # bus or the call site. viewer_id is unused for now, by design.
        return f'{display_name(self.speaker_id)} says, "{self.words}"'
