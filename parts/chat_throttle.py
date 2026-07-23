"""CARD: chat_throttle -- the game adapter for the token bucket: anti-spam on a player's shout.

A player may `shout` a message to everyone in the room, but only so often: each shout costs a token
from a per-player bucket (a burst of 3, refilling one every 20 seconds). Over-shouting is refused
with the exact wait, never silently dropped. The SAME `TokenBucket` core (parts/token_bucket)
throttles login attempts in a practical app (parts/login_guard); only the adapter differs.
"""

from __future__ import annotations

from parts.shelf.token_bucket import Clock, TokenBucket
from parts.world.events import announce
from parts.world.session import Session, display_name

_RATE = 1 / 20  # one shout refills every 20 seconds
_CAPACITY = 3.0  # a burst of three
_BUCKETS: dict[str, TokenBucket] = {}
_clock_override: Clock | None = None


def _bucket(player_id: str) -> TokenBucket:
    if player_id not in _BUCKETS:
        _BUCKETS[player_id] = TokenBucket(_RATE, _CAPACITY, clock=_clock_override)
    return _BUCKETS[player_id]


def shout(session: Session, message: str) -> str:
    """The `shout` verb: broadcast to the room, rate-limited per player."""
    message = message.strip()
    if not message:
        return "Shout what?"
    decision = _bucket(session.player_id).consume()
    if not decision.allowed:
        return f"Your voice is hoarse. You can shout again in {decision.retry_after:.0f}s."
    announce(
        session.location,
        f'{display_name(session.player_id)} shouts, "{message}"',
        exclude=session.player_id,
    )
    return f'You shout, "{message}"'


def reset_throttles(clock: Clock | None = None) -> None:
    """Test hook: clear all per-player buckets and optionally inject a clock for new ones."""
    global _clock_override
    _clock_override = clock
    _BUCKETS.clear()
