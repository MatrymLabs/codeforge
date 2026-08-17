"""Test twin for kernel/world/reward_ledger.py -- a reward is paid at most once per grant.

Acceptance: a fresh grant is payable; a repeat OCCURRENCE of the same source is payable, because
a farmable foe legitimately pays again; the ledger records what it paid.

Refusal (fail loud): the SAME grant identity is never payable twice, not after a retry, not after
a reconnect, and not after the process restarts. The record outlives the process.

The trap this file exists to catch: keying the ledger on (character, source) alone makes the
training dummy pay once per lifetime. It is farmable by design. The occurrence is part of identity.
"""

from __future__ import annotations

from kernel.world.reward_ledger import already_granted, record_grant


def test_a_fresh_grant_is_payable() -> None:
    assert not already_granted("hero", "npc:training_dummy", 1)


def test_recording_a_grant_makes_it_unpayable_again() -> None:
    record_grant("hero", "npc:training_dummy", 1)
    assert already_granted("hero", "npc:training_dummy", 1)


def test_a_later_occurrence_of_the_same_source_is_payable() -> None:
    """A farmable foe pays every time it is killed. This is the trap."""
    record_grant("hero", "npc:training_dummy", 1)
    assert not already_granted("hero", "npc:training_dummy", 2)


def test_two_characters_do_not_share_a_grant() -> None:
    record_grant("hero", "npc:training_dummy", 1)
    assert not already_granted("rival", "npc:training_dummy", 1)


def test_two_sources_do_not_share_an_occurrence() -> None:
    record_grant("hero", "npc:training_dummy", 1)
    assert not already_granted("hero", "npc:cinder_wight", 1)


def test_recording_the_same_grant_twice_is_not_an_error() -> None:
    """Idempotent WRITE. A retry that re-records must not raise, or the retry becomes the bug."""
    record_grant("hero", "npc:training_dummy", 1)
    record_grant("hero", "npc:training_dummy", 1)
    assert already_granted("hero", "npc:training_dummy", 1)


def test_the_record_outlives_the_process() -> None:
    """The whole point. In-memory exactly-once is not exactly-once across a restart.

    Reload the module's durable view the way a fresh process would and assert the grant is still
    known. If the ledger is in-memory only, this test cannot pass, which is the intended pressure.
    """
    import importlib  # noqa: PLC0415

    from kernel.world import reward_ledger  # noqa: PLC0415

    record_grant("hero", "npc:training_dummy", 99)
    importlib.reload(reward_ledger)
    assert reward_ledger.already_granted("hero", "npc:training_dummy", 99)


# --- ADDED beyond the packet. No assertion above was weakened, deleted or rewritten. -----------
# The packet's tests pin the ledger's answers. These pin the two things that would let a correct
# ledger still rob a player or accept an unmatchable row.

import pytest  # noqa: E402

from kernel.world.reward_ledger import grants_for, next_occurrence  # noqa: E402


def test_the_first_occurrence_is_one() -> None:
    assert next_occurrence("hero", "npc:training_dummy") == 1


def test_the_occurrence_advances_past_every_grant_already_paid() -> None:
    """A farmable foe must keep paying, so the next occurrence is never one already recorded."""
    for expected in (1, 2, 3):
        occurrence = next_occurrence("hero", "npc:training_dummy")
        assert occurrence == expected
        assert not already_granted("hero", "npc:training_dummy", occurrence)
        record_grant("hero", "npc:training_dummy", occurrence)
        assert already_granted("hero", "npc:training_dummy", occurrence)


def test_the_occurrence_does_not_rewind_when_a_fresh_process_starts() -> None:
    """The defect this design exists to avoid.

    `climate.now()` documents itself as "a fresh boot starts at 0" and is not persisted. Minting
    the occurrence from the world beat would rewind it on restart, so a legitimate second kill
    would reuse an occurrence already on disk and the ledger would REFUSE a payout the player had
    earned. Robbing the player is worse than paying twice, so the count comes from the record.
    """
    import importlib  # noqa: PLC0415

    from kernel.world import reward_ledger  # noqa: PLC0415

    for _ in range(3):
        record_grant("hero", "npc:training_dummy", next_occurrence("hero", "npc:training_dummy"))

    importlib.reload(reward_ledger)  # a fresh process, with the beat back at 0

    assert reward_ledger.next_occurrence("hero", "npc:training_dummy") == 4
    assert not reward_ledger.already_granted("hero", "npc:training_dummy", 4)


def test_occurrences_are_counted_per_source_not_per_character() -> None:
    record_grant("hero", "npc:training_dummy", next_occurrence("hero", "npc:training_dummy"))
    assert next_occurrence("hero", "npc:training_dummy") == 2
    assert next_occurrence("hero", "npc:cinder_wight") == 1  # a different foe starts its own count


@pytest.mark.parametrize(
    ("character", "source", "occurrence"),
    [
        ("", "npc:x", 1),  # no recipient
        ("   ", "npc:x", 1),  # whitespace is not a name
        ("hero", "", 1),  # no source
        ("hero", "   ", 1),
        ("hero", "npc:x", -1),  # an occurrence that cannot be counted to
        ("hero", "npc:x", "1"),  # a string that looks like a number
        ("hero", "npc:x", True),  # bool is an int in Python, and is not an occurrence
        (None, "npc:x", 1),
    ],
)
def test_an_unusable_grant_identity_is_refused_loudly(character, source, occurrence) -> None:
    """A row nobody can look up again is the same as no record, except it looks like one.

    Resolved through the MODULE rather than the names imported at the top of this file, on
    purpose. `test_the_record_outlives_the_process` calls `importlib.reload`, which rebinds
    `GrantIdentityError` to a new class object; a bare `pytest.raises(GrantIdentityError)` here
    would then fail to match the very error it just provoked. Import identity is not stable across
    a reload, and this file reloads.
    """
    from kernel.world import reward_ledger  # noqa: PLC0415

    with pytest.raises(reward_ledger.GrantIdentityError):
        reward_ledger.record_grant(character, source, occurrence)
    with pytest.raises(reward_ledger.GrantIdentityError):
        reward_ledger.already_granted(character, source, occurrence)


def test_an_identity_is_matched_after_surrounding_whitespace_is_trimmed() -> None:
    record_grant("  hero  ", "  npc:training_dummy  ", 1)
    assert already_granted("hero", "npc:training_dummy", 1)


def test_the_ledger_reports_what_it_paid() -> None:
    record_grant("hero", "npc:training_dummy", 1)
    record_grant("hero", "npc:cinder_wight", 1)
    assert sorted(grants_for("hero")) == [("npc:cinder_wight", 1), ("npc:training_dummy", 1)]
    assert grants_for("rival") == []


def test_claiming_a_grant_returns_true_once_and_false_after() -> None:
    """The claim IS the insert, so the primary key picks the winner rather than a prior read."""
    from kernel.world import reward_ledger  # noqa: PLC0415

    assert reward_ledger.claim_grant("hero", "npc:training_dummy", 1) is True
    assert reward_ledger.claim_grant("hero", "npc:training_dummy", 1) is False
    assert reward_ledger.already_granted("hero", "npc:training_dummy", 1)


def test_a_lost_claim_does_not_disturb_the_grant_that_won() -> None:
    from kernel.world import reward_ledger  # noqa: PLC0415

    reward_ledger.claim_grant("hero", "npc:training_dummy", 1)
    reward_ledger.claim_grant("hero", "npc:training_dummy", 1)
    assert reward_ledger.grants_for("hero") == [("npc:training_dummy", 1)]


def test_every_occurrence_of_a_farmable_foe_can_be_claimed() -> None:
    """Three kills, three claims, three payouts. A ledger that breaks the dummy is the worse bug."""
    from kernel.world import reward_ledger  # noqa: PLC0415

    for _ in range(3):
        occurrence = reward_ledger.next_occurrence("hero", "npc:training_dummy")
        assert reward_ledger.claim_grant("hero", "npc:training_dummy", occurrence) is True
    assert reward_ledger.next_occurrence("hero", "npc:training_dummy") == 4
