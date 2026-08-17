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

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from kernel.world.session import display_name


class Frame:
    """Marker base for a typed event frame. Subclasses are frozen dataclasses that
    carry structured fields and know how to render themselves for one viewer.

    Kept a plain marker (like kernel.shelf.signal_bus.Signal) rather than an ABC so the
    contract is one method, tested directly."""

    def render_for(self, viewer_id: str) -> str:
        """Project this frame to the single line `viewer_id` should see."""
        raise NotImplementedError("a Frame subclass must implement render_for")


# --- the wire registry: a frame crosses the message bus as JSON, then renders per recipient -------
# When room delivery rides the bus (Phase 5), a Frame must survive a broker hop, which only carries
# JSON. A frame serialises to {type, fields}; the receiving process rebuilds it (re-validating on
# build) and renders it for ITS OWN local viewers, so per-recipient projection is preserved across
# processes, not flattened to one pre-baked line.
_WIRE_REGISTRY: dict[str, type[Frame]] = {}


def register_frame(cls: type[Frame]) -> type[Frame]:
    """Register a Frame subclass so it can round-trip over the bus. Decorate each wire type."""
    _WIRE_REGISTRY[cls.__name__] = cls
    return cls


def to_wire(frame: Frame) -> dict[str, Any]:
    """Serialise a frame to a JSON-safe dict for the bus. A non-dataclass or unregistered frame
    fails loud rather than crossing the wire half-formed."""
    if not is_dataclass(frame) or type(frame).__name__ not in _WIRE_REGISTRY:
        raise ValueError(f"frame {type(frame).__name__} is not registered for the wire")
    return {"type": type(frame).__name__, "fields": asdict(frame)}


def from_wire(payload: dict[str, Any]) -> Frame:
    """Reconstruct a frame from its wire dict, re-running the subclass validation. An unknown type
    or a malformed field set fails loud (ValueError), so a garbled frame never renders as noise."""
    cls = _WIRE_REGISTRY.get(payload.get("type", ""))
    if cls is None:
        raise ValueError(f"unknown frame type {payload.get('type')!r}")
    fields = payload.get("fields")
    if not isinstance(fields, dict):
        raise ValueError("frame wire payload missing its fields") # noqa: TRY004
    return cls(**fields)


@register_frame
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

    def render_for(self, viewer_id: str) -> str:  # noqa: ARG002
        # The per-recipient seam: today every bystander sees the same third-person
        # line, but the projection now happens HERE, at delivery, so a viewer's own
        # perspective (name, tense, locale) can diverge later without touching the
        # bus or the call site. viewer_id is unused for now, by design.
        return f'{display_name(self.speaker_id)} says, "{self.words}"'


@register_frame
@dataclass(frozen=True)
class StrikeFrame(Frame):
    """An NPC landed a blow on a player -- a counter or an unprovoked opening strike.

    The second consumer of the typed bus (after SpeechFrame): combat broadcasts a
    strike as structured data (who hit whom, how, for how much) so a bystander could
    later see it from their own vantage, without combat re-rendering per viewer."""

    attacker_name: str  # already display-cased, e.g. "The brawler"
    verb: str  # the opening phrase: "strikes back", "lunges"
    target_id: str
    amount: int

    def __post_init__(self) -> None:
        if not self.attacker_name.strip():
            raise ValueError("StrikeFrame needs an attacker_name")
        if not self.verb.strip():
            raise ValueError("StrikeFrame needs a verb")
        if not self.target_id:
            raise ValueError("StrikeFrame needs a target_id")
        if self.amount <= 0:
            raise ValueError("StrikeFrame amount must be a positive blow")

    def render_for(self, viewer_id: str) -> str:  # noqa: ARG002
        # Same seam as SpeechFrame: one third-person line today, per-viewer later.
        return (
            f"{self.attacker_name} {self.verb} at {display_name(self.target_id)} for {self.amount}."
        )
