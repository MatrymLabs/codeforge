"""Test twin for parts/world/party_loot.py -- shared combat's loot half (round-robin drops).

Acceptance: a party fells a foe and each drop is awarded to a co-located mate in rotation, moved
into their hands; wired through combat's _spawn_loot seam. Refusal (unchanged solo behavior): a solo
kill, or a partied hero with no co-located mate, leaves the drop on the floor to be taken.
"""

from __future__ import annotations

from parts.world import combat, events, items, party, party_loot
from parts.world.items import carrier
from parts.world.session import SESSIONS, Session


def _hero(name: str, room: str = "arena") -> Session:
    return SESSIONS.setdefault(name, Session(player_id=name, location=room))


def _band(*names: str) -> None:
    lead, rest = names[0], names[1:]
    for other in rest:
        party.invite(lead, other)
        party.join(other, lead)


def _drop_in(room: str, iid: str, name: str) -> str:
    items.ITEMS[iid] = {
        "name": name,
        "keywords": [name.split()[-1]],
        "location": f"room:{room}",
        "slot": "",
        "mods": {},
    }
    return iid


def _teardown() -> None:
    party._reset()
    party_loot._reset()
    for name in list(SESSIONS):
        events.unbind_echo(name)
        SESSIONS.pop(name, None)
    for iid in ("gemA", "gemB", "forge_wrench"):
        items.ITEMS.pop(iid, None)


# --- acceptance --------------------------------------------------------------------------------
def test_a_party_drop_is_awarded_to_a_co_located_mate():
    try:
        _hero("alia")
        _hero("bram")
        _band("alia", "bram")
        _drop_in("arena", "gemA", "a gem")
        line = party_loot.assign_drop("alia", "arena", "gemA")
        assert line is not None and "awarded to" in line
        # the drop moved off the floor into a party member's hands (alia is turn 0)
        assert items.ITEMS["gemA"]["location"] == carrier("alia")
    finally:
        _teardown()


def test_round_robin_rotates_the_winner():
    try:
        _hero("alia")
        _hero("bram")
        _band("alia", "bram")  # members order: alia (leader), bram
        _drop_in("arena", "gemA", "a gem")
        _drop_in("arena", "gemB", "a jewel")
        party_loot.assign_drop("alia", "arena", "gemA")  # turn 0 -> alia
        party_loot.assign_drop("alia", "arena", "gemB")  # turn 1 -> bram
        assert items.ITEMS["gemA"]["location"] == carrier("alia")
        assert items.ITEMS["gemB"]["location"] == carrier("bram")
    finally:
        _teardown()


def test_the_loot_share_is_wired_through_combat_spawn():
    try:
        _hero("alia")
        _hero("bram")
        _band("alia", "bram")
        # _spawn_loot mints a real prototype into the world, then party_loot reassigns it
        line = combat._spawn_loot(SESSIONS["alia"], "forge_wrench")
        assert "awarded to" in line
        held = items.items_in(carrier("alia")) + items.items_in(carrier("bram"))
        assert any(items.prototype_of(i) == "forge_wrench" for i in held)  # a mate now holds it
    finally:
        _teardown()


# --- refusal: solo behavior is unchanged (loot falls to the floor) -----------------------------
def test_a_solo_kill_leaves_the_drop_on_the_floor():
    try:
        _hero("alia")
        _drop_in("arena", "gemA", "a gem")
        assert party_loot.assign_drop("alia", "arena", "gemA") is None  # not shared
        assert items.ITEMS["gemA"]["location"] == "room:arena"  # still on the floor
    finally:
        _teardown()


def test_a_partied_hero_alone_here_leaves_the_drop_on_the_floor():
    try:
        _hero("alia", "arena")
        _hero("bram", "the-deep")  # a mate, but elsewhere
        _band("alia", "bram")
        _drop_in("arena", "gemA", "a gem")
        assert party_loot.assign_drop("alia", "arena", "gemA") is None
        assert items.ITEMS["gemA"]["location"] == "room:arena"
    finally:
        _teardown()
