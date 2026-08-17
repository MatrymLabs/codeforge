"""CARD: target_disambig -- parse a numbered target token ("2-sword") and pick the Nth match.

Clean-room harvest of the numbered-target idea from Evennia's
commands/cmdparser.py (BSD-3-Clause). No Evennia source was copied; only the
"leading/trailing ordinal disambiguates identical names" behavior is reproduced
here in stdlib-only frameless Python.

Why this exists: codeforge's trace_item / trace_npc return the FIRST keyword
match, so a room holding N identical swords is un-targetable past the first.
This part splits an ordinal off a token so a caller can pick one of many.
"""

from __future__ import annotations

__all__ = ["TargetError", "parse_target", "pick", "resolve"]


class TargetError(ValueError):
    """Raised loud when a target token or ordinal is malformed or out of range."""


def parse_target(token: str) -> tuple[int, str]:
    """Split a leading or trailing 1-based ordinal off a target token.

    Inputs: token like "2-sword", "sword-2", or a bare "sword".
    Output: (ordinal, name) where ordinal >= 1 (bare name -> ordinal 1).

    Refuses (TargetError): empty/blank token, ordinal < 1 ("0-sword"),
    an empty name once the ordinal is stripped.
    """
    if not isinstance(token, str):
        raise TargetError(f"target token must be a string, got {type(token).__name__}")  # noqa: TRY003

    cleaned = token.strip()
    if not cleaned:
        raise TargetError("target token is empty")  # noqa: TRY003

    ordinal, name = _split_ordinal(cleaned)

    if not name:
        raise TargetError(f"target token {token!r} has no name")  # noqa: TRY003
    if ordinal < 1:
        raise TargetError(f"target ordinal must be >= 1 (1-based), got {ordinal} from {token!r}")  # noqa: TRY003
    return ordinal, name


def _split_ordinal(cleaned: str) -> tuple[int, str]:
    """Pull a leading "N-name" or trailing "name-N" ordinal; default 1 if neither."""
    head, sep, tail = cleaned.partition("-")
    if sep:
        if head.isdigit() and tail:
            return int(head), tail
        rhead, _rsep, rtail = cleaned.rpartition("-")
        if rtail.isdigit() and rhead:
            return int(rtail), rhead
    return 1, cleaned


def pick[T](matches: list[T], ordinal: int) -> T:
    """Return the ordinal-th (1-based) element of matches.

    Refuses (TargetError): ordinal < 1, or ordinal beyond the number of matches
    (the message names how many are actually here).
    """
    if ordinal < 1:
        raise TargetError(f"target ordinal must be >= 1 (1-based), got {ordinal}")  # noqa: TRY003
    count = len(matches)
    if ordinal > count:
        raise TargetError(f"no target #{ordinal}: only {count} here")  # noqa: TRY003
    return matches[ordinal - 1]


def resolve[T](token: str, matches: list[T]) -> T:
    """Parse an ordinal off token, then pick that match from a pre-filtered list.

    The caller pre-filters `matches` to those sharing the parsed name; this part
    only splits the ordinal off and indexes. Returns the chosen match.
    """
    ordinal, _name = parse_target(token)
    return pick(matches, ordinal)
