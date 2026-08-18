"""A save you cannot verify is a save you cannot trust.

The Seed backup path checksums its bytes and reports INTACT / CORRUPT / MISSING. The character
record, which is the thing a player actually loses, carried no checksum at all: corruption was read
back as truth because nothing asked whether the record was intact.

RD-2026-0119, from documented SNES-era SRAM discipline: checksum the save, treat a failed checksum
as empty rather than as data. The medium changed; the reason did not.
"""

from __future__ import annotations

import pytest

from kernel.world.save_integrity import IntegrityVerdict, checksum_of, verify_record


def test_a_record_checksums_to_a_stable_value() -> None:
    """Same fields in, same checksum out, or nothing downstream can rely on it."""
    record = {"name": "hero", "level": 7, "xp": 824}
    assert checksum_of(record) == checksum_of(dict(record))


def test_a_changed_field_changes_the_checksum() -> None:
    """The whole point. A checksum that does not move is not a checksum."""
    base = {"name": "hero", "level": 7, "xp": 824}
    assert checksum_of(base) != checksum_of({**base, "xp": 825})


def test_field_ORDER_does_not_change_the_checksum() -> None:  # noqa: N802
    """A dict's insertion order is not part of the record. If it were, a harmless reordering
    anywhere upstream would corrupt every save in the world at once."""
    assert checksum_of({"a": 1, "b": 2}) == checksum_of({"b": 2, "a": 1})


def test_an_intact_record_verifies() -> None:
    record = {"name": "hero", "level": 7}
    assert verify_record(record, checksum_of(record)) is IntegrityVerdict.INTACT


def test_a_corrupted_record_is_CORRUPT_not_intact() -> None:  # noqa: N802
    record = {"name": "hero", "level": 7}
    stored = checksum_of(record)
    record["level"] = 70  # a single mutated field
    assert verify_record(record, stored) is IntegrityVerdict.CORRUPT


def test_a_record_with_NO_checksum_is_UNVERIFIED_not_intact() -> None:  # noqa: N802
    """A legacy row predates the column. Unknown is not intact, and this is the assertion that
    stops "we could not check" from being rounded up to "we checked and it was fine"."""
    assert verify_record({"name": "hero"}, None) is IntegrityVerdict.UNVERIFIED


def test_the_verdict_is_a_word_not_a_bool() -> None:
    """INTACT, CORRUPT and UNVERIFIED are three different answers. A bool can hold two."""
    assert (
        len({IntegrityVerdict.INTACT, IntegrityVerdict.CORRUPT, IntegrityVerdict.UNVERIFIED}) == 3
    )


def test_each_verdict_names_its_gameplay_scope() -> None:
    """No reader may mistake this for an integrity claim over credentials or account ownership."""
    assert all(verdict.value.startswith("gameplay-state:") for verdict in IntegrityVerdict)


@pytest.mark.parametrize("hostile", [{}, {"name": ""}, {"name": None}, {"name": "hero\x00"}])
def test_a_hostile_record_still_produces_a_checksum_rather_than_raising(hostile) -> None:
    """Checksumming is not validation. An empty or ugly record is still a record, and a checksum
    that raises on one turns a data problem into a crash at exactly the wrong moment."""
    assert isinstance(checksum_of(hostile), str)
