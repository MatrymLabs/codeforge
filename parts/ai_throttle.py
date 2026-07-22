"""CARD: ai_throttle -- the game adapter that rate-limits the `ai` verb's calls to the Architect.

Consulting the Architect can reach a live Claude brain (`CODEFORGE_ARCHITECT=claude` +
`ANTHROPIC_API_KEY`), so an un-capped `ai` verb at player rank is a token-cost DoS the day the
public demo runs a real model: any player could spam paid API calls. The SAME `TokenBucket` core
(parts/token_bucket) that throttles shouts (parts/chat_throttle) and login attempts
(parts/login_guard) caps a player's consultations: a small burst, refilling slowly. Over-asking is
refused loud with the exact wait, never a silent drop. The cap applies to the free local guide too,
so behavior is uniform and the gate is already armed before the brain ever goes live.
"""

from __future__ import annotations

from parts.session import Session
from parts.shelf.token_bucket import Clock, TokenBucket

# A consultation is expensive (a live model call), so the bucket is stingier than chat: a burst of
# three questions, then one back every 30 seconds. A reader digesting a paragraph of advice never
# feels it; a rapid-fire abuser is capped.
_RATE = 1 / 30  # one consultation refills every 30 seconds
_CAPACITY = 3.0  # a burst of three
_BUCKETS: dict[str, TokenBucket] = {}
_clock_override: Clock | None = None


def _bucket(player_id: str) -> TokenBucket:
    if player_id not in _BUCKETS:
        _BUCKETS[player_id] = TokenBucket(_RATE, _CAPACITY, clock=_clock_override)
    return _BUCKETS[player_id]


def ask_architect(session: Session, prompt: str) -> str:
    """The `ai` verb: consult the Architect, rate-limited per player. The prompt is passed through
    unchanged (the spine preserves its case, prose not a label); only the CADENCE is gated."""
    decision = _bucket(session.player_id).consume()
    if not decision.allowed:
        return f"The Architect is still thinking. Ask again in {decision.retry_after:.0f}s."
    from parts.architect import consult

    return consult(prompt)


def reset_ai_throttle(clock: Clock | None = None) -> None:
    """Test hook: clear all per-player buckets and optionally inject a clock for new ones."""
    global _clock_override
    _clock_override = clock
    _BUCKETS.clear()
