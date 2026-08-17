"""CARD: reward_ledger -- a reward is paid at most once per grant, and the record outlives it.

In-memory exactly-once is not exactly-once. It holds only while one process holds the object graph,
and the flight's own destination crosses a process boundary: leg 1G restarts the services and
replays the slice. This module puts the record on disk, so a retry, a reconnect, or a restart
cannot pay the same grant twice.

A grant identity is `(character, source, occurrence)`:

    character    the recipient
    source       what paid out, e.g. "npc:training_dummy"
    occurrence   which payout from that source this was

The occurrence is the part that matters and the part that is easy to get wrong. Keying on
`(character, source)` alone would make the training dummy pay once per lifetime, and the dummy is
farmable BY DESIGN. A repeat kill is a new occurrence and must still pay.

WHY THE LEDGER MINTS THE OCCURRENCE. The obvious source for one is the world beat, and it is a
trap. `climate.now()` documents itself as "a fresh boot starts at 0" and is not persisted, so
after a restart the beat rewinds and a legitimate second kill would reuse an occurrence already on
disk. The ledger would then refuse a payout the player had earned. Robbing the player is a worse
failure than paying twice, so the occurrence is minted here, from the durable record itself.

This is a RECORD, not a lock, and not a wallet. The purse remains authoritative about what a
player owns. The only question this module answers is "was this grant already applied".

Consume-first, logged: `Idempotency Key Store` (`kernel/shelf/idempotency.py`, Working Shelf) is
the same shape and was NOT consumed, because its own card records the reason: "Traded away (v1):
durability and cross-process atomicity, keeping a pure single-process core." Durability across a
process boundary is the entire requirement here. The two should converge; see the RETURN's
extraction block.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from kernel.world.db import RewardGrantRow, open_archive_session


class GrantIdentityError(ValueError):
    """A grant identity that could never be looked up again. Refused at the door."""


def _checked(character: str, source: str, occurrence: int) -> tuple[str, str, int]:
    """Refuse an unusable identity loudly, here, rather than writing a row nobody can match.

    A blank character or source, or a negative occurrence, is a caller bug. Silently accepting one
    would put a row in the ledger that no later lookup reproduces, which is the same as no record
    at all, except it looks like one.
    """
    if not isinstance(character, str) or not character.strip():
        raise GrantIdentityError(f"character must be a non-empty string, got {character!r}")
    if not isinstance(source, str) or not source.strip():
        raise GrantIdentityError(f"source must be a non-empty string, got {source!r}")
    if isinstance(occurrence, bool) or not isinstance(occurrence, int):
        raise GrantIdentityError(f"occurrence must be an int, got {occurrence!r}")
    if occurrence < 0:
        raise GrantIdentityError(f"occurrence must not be negative, got {occurrence!r}")
    return character.strip(), source.strip(), occurrence


def already_granted(character: str, source: str, occurrence: int) -> bool:
    """True when this exact grant has already been paid, according to the durable record."""
    character, source, occurrence = _checked(character, source, occurrence)
    with open_archive_session() as archive:
        row = archive.get(RewardGrantRow, (character, source, occurrence))
        return row is not None


def record_grant(character: str, source: str, occurrence: int) -> None:
    """Record that this grant has been paid. Idempotent: re-recording is not an error.

    The write has to tolerate repetition, because the caller that repeats it is a retry, and a
    retry that raises turns the safety net into the failure.
    """
    character, source, occurrence = _checked(character, source, occurrence)
    with open_archive_session() as archive:
        if archive.get(RewardGrantRow, (character, source, occurrence)) is None:
            archive.add(
                RewardGrantRow(
                    character=character,
                    source=source,
                    occurrence=occurrence,
                    granted_utc=datetime.now(UTC).isoformat(timespec="seconds"),
                )
            )
            archive.commit()


def claim_grant(character: str, source: str, occurrence: int) -> bool:
    """Claim this grant. True when THIS caller won it and must pay, False when it was paid already.

    Check-then-pay is not enough. Two processes can both read "not yet granted" and both pay, which
    is the exact failure this module exists to prevent. The claim is therefore the INSERT itself:
    the table's primary key decides the winner, atomically, and the loser is told to pay nothing.

    Callers that pay should use this. `record_grant` remains the plain idempotent write for a
    caller that has already decided.
    """
    character, source, occurrence = _checked(character, source, occurrence)
    with open_archive_session() as archive:
        archive.add(
            RewardGrantRow(
                character=character,
                source=source,
                occurrence=occurrence,
                granted_utc=datetime.now(UTC).isoformat(timespec="seconds"),
            )
        )
        try:
            archive.commit()
        except IntegrityError:
            archive.rollback()  # somebody else already holds this grant; they paid, we do not
            return False
        return True


def next_occurrence(character: str, source: str) -> int:
    """The next unused occurrence for this character and source, from the durable record.

    Monotonic and restart-proof, which the world beat is not. First payout is 1; the Nth is N,
    counted from what is actually on disk rather than from anything a fresh process resets.
    """
    character, source, _ = _checked(character, source, 0)
    with open_archive_session() as archive:
        highest = archive.execute(
            select(func.max(RewardGrantRow.occurrence)).where(
                RewardGrantRow.character == character, RewardGrantRow.source == source
            )
        ).scalar()
        return int(highest or 0) + 1


def grants_for(character: str) -> list[tuple[str, int]]:
    """Every (source, occurrence) already paid to this character, oldest first. Audit only."""
    character, _, _ = _checked(character, "audit", 0)
    with open_archive_session() as archive:
        rows = archive.execute(
            select(RewardGrantRow.source, RewardGrantRow.occurrence)
            .where(RewardGrantRow.character == character)
            .order_by(RewardGrantRow.granted_utc, RewardGrantRow.occurrence)
        ).all()
        return [(source, occurrence) for source, occurrence in rows]


# --- the Hardware Store contract this ledger satisfies ------------------------------------------
# PRT-0007 `applied-once`. The Part was extracted FROM this module and saas-starter's WebhookEvent,
# which built the same mechanism independently. The engine consumes its CONTRACT, not its sqlite
# reference implementation: the invariant is already met here with SQLAlchemy and the engine's own
# archive, and vendoring a second persistence mechanism would buy nothing. Proof that the claim is
# not decorative lives in tests/test_reward_ledger_conforms.py, which runs the Part's own contract
# suite against this ledger on every `make check`.

_KEY_SEPARATOR = "|"


def grant_key(character: str, source: str, occurrence: int) -> str:
    """This ledger's grant identity, flattened to the Part's single opaque key."""
    character, source, occurrence = _checked(character, source, occurrence)
    return f"{character}{_KEY_SEPARATOR}{source}{_KEY_SEPARATOR}{occurrence}"


class GrantLedger:
    """`kernel/world/reward_ledger` presented as an `AppliedOnce` (PRT-0007).

    A thin projection, deliberately holding no state of its own: the durable record stays in
    RewardGrantRow, where the combat seam already writes it. This exists so the engine's conformance
    to the Part is TESTED rather than asserted.

    The Part's keys are opaque, and a conforming implementation must accept any non-empty string.
    This ledger's own identities flatten to `character|source|occurrence`; any other shape is a
    single identity taken whole, stored under a reserved source so it can never collide with a
    real grant.
    """

    OPAQUE_SOURCE = "opaque"

    def _split(self, key: str) -> tuple[str, str, int]:
        if not isinstance(key, str) or not key.strip():
            raise GrantIdentityError(f"key must be a non-empty string, got {key!r}")
        parts = key.split(_KEY_SEPARATOR)
        if len(parts) == 3 and parts[2].isdigit():  # noqa: PLR2004
            return parts[0], parts[1], int(parts[2])
        return key, self.OPAQUE_SOURCE, 0

    def seen(self, key: str) -> bool:
        return already_granted(*self._split(key))

    def claim(self, key: str) -> bool:
        return claim_grant(*self._split(key))
