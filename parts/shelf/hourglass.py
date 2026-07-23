"""CARD: hourglass -- deferred actions that fire on the world's beat (a beat-driven delay queue).

The classic MUD engines carried a "delayed action" mechanism -- Diku/Merc call it the event
queue, and Erwin Andreasen's public-domain event snippet was reused across the tradition
(Aardwolf and many others). The idea: register a payload to fire after N game beats, advance
the queue once per beat, and let due payloads come out. This is an ORIGINAL Python
implementation studied clean-room from that public behavior
(research/legacy_muds/behavior_specs/delayed_event_queue.md, license class A / public-domain
lineage); no historical code, names, or structure was copied.

It honors CodeForge's clock law: an Hourglass never runs itself. Something advances it -- in
the engine, the world beat (the player's command is the only clock; parts.forge advances the
shared WORLD_SANDS after each tick, no background thread). Off the game it advances on whatever
logical cycle the caller owns.

One mechanism, many jobs:
- game: fire a deferred effect (a door recloses, a status wears off, an area resets) N beats on.
- general: a tick-driven timer wheel / delay queue -- run deferred work off one logical clock,
  with no threads and no wall-clock timers (retry-after, timeouts, TTL expiry, debounce).
- records/finance: decrement a review or retention countdown each processing cycle, fire on due.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Bound the queue so a crafted world (or a runaway caller) cannot schedule unboundedly and
# exhaust memory. A delay queue with no ceiling is a denial-of-service waiting to happen.
MAX_TIMERS = 4096


class HourglassError(ValueError):
    """A bad schedule: fail loud, never queue a nonsensical timer."""


@dataclass
class _Grain:
    """One pending timer: how many beats remain, its repeat period (0 = one-shot), its payload."""

    label: str
    remaining: int
    period: int
    payload: Any


@dataclass
class Hourglass:
    """A delay queue measured in beats. Schedule a labelled payload to fire after N beats (or
    every N beats), advance one beat at a time, and collect what came due. Deterministic:
    timers fire in insertion order, and the same schedule advanced the same way fires the same."""

    _grains: dict[str, _Grain] = field(default_factory=dict)

    def schedule(self, label: str, after: int, *, every: int = 0, payload: Any = None) -> None:
        """Fire `payload` (or `label` if no payload) after `after` beats. `every > 0` rearms the
        timer to repeat on that period. Scheduling an existing label REPLACES it (reschedule)."""
        if not isinstance(after, int) or isinstance(after, bool) or after <= 0:
            raise HourglassError(f"'after' must be a positive whole number of beats, got {after!r}")
        if not isinstance(every, int) or isinstance(every, bool) or every < 0:
            raise HourglassError(
                f"'every' must be a non-negative whole number of beats, got {every!r}"
            )
        if label not in self._grains and len(self._grains) >= MAX_TIMERS:
            raise HourglassError(
                f"hourglass is full ({MAX_TIMERS} timers); cannot schedule '{label}'"
            )
        self._grains[label] = _Grain(label=label, remaining=after, period=every, payload=payload)

    def cancel(self, label: str) -> bool:
        """Drop a pending timer. Returns True if one was removed, False if it wasn't scheduled."""
        return self._grains.pop(label, None) is not None

    def pending(self) -> int:
        """How many timers are waiting."""
        return len(self._grains)

    def clear(self) -> None:
        """Drop every pending timer (a fresh queue). Used to reset the shared world timer."""
        self._grains.clear()

    def remaining(self, label: str) -> int | None:
        """Beats left before `label` fires, or None if it isn't scheduled."""
        grain = self._grains.get(label)
        return grain.remaining if grain else None

    def advance(self) -> list[Any]:
        """Take one beat: decrement every timer, then fire and RETURN the payloads that reached
        zero (in insertion order). A repeating timer rearms to its period; a one-shot is removed.
        The Hourglass only reports what fired -- applying the effect is the caller's job (state
        stays canonical, mutated by validated logic, never by the queue itself)."""
        fired: list[Any] = []
        for label in list(self._grains):
            grain = self._grains[label]
            grain.remaining -= 1
            if grain.remaining <= 0:
                fired.append(grain.payload if grain.payload is not None else grain.label)
                if grain.period > 0:
                    grain.remaining = grain.period
                else:
                    del self._grains[label]
        return fired


# The engine's shared world timer: parts.forge advances this once per world beat (after the
# tick's response), so any part can schedule a deferred world effect without owning a clock.
WORLD_SANDS = Hourglass()
