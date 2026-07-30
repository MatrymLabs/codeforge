"""Test twin for parts/world/presence.py -- the live roster carried on the bus (Phase 4).

Acceptance: marking a hero online adds them, offline removes them, and the roster reflects it across
the bus; count() matches. Cross-process readiness: a SECOND subscriber on the same bus sees the same
announcements, which is the whole point (another process reading one true roster). Refusal: a
malformed frame never corrupts the roster; a double-online does not double-count; reconnect after a
bus swap keeps the roster fed by a fake, no network touched.
"""

from __future__ import annotations

from typing import Any

import pytest

from parts.world import bus, presence


@pytest.fixture(autouse=True)
def _fresh() -> Any:
    bus.reset_bus()
    presence._reset()  # clear the roster + re-subscribe to the clean bus
    yield
    bus.reset_bus()
    presence._reset()


def test_mark_online_puts_a_hero_on_the_roster() -> None:
    presence.mark_online("bram")
    assert presence.online() == {"bram"}
    assert presence.count() == 1


def test_mark_offline_removes_a_hero() -> None:
    presence.mark_online("bram")
    presence.mark_offline("bram")
    assert presence.online() == set()
    assert presence.count() == 0


def test_the_roster_holds_many_heroes() -> None:
    presence.mark_online("bram")
    presence.mark_online("mira")
    assert presence.online() == {"bram", "mira"}


def test_double_online_does_not_double_count() -> None:
    presence.mark_online("bram")
    presence.mark_online("bram")  # a reconnect race must not inflate the count
    assert presence.count() == 1


def test_offline_of_an_absent_hero_is_harmless() -> None:
    presence.mark_offline("ghost")  # never online -> no error, roster stays empty
    assert presence.online() == set()


def test_online_returns_a_snapshot_not_the_live_set() -> None:
    presence.mark_online("bram")
    snap = presence.online()
    snap.add("intruder")  # mutating the copy must not touch the roster
    assert presence.online() == {"bram"}


def test_a_second_subscriber_sees_the_same_announcements() -> None:
    # The cross-process payoff, proven in one process: any other subscriber on the bus (a second
    # gateway, the admin surface) receives the same presence frames and can build the same roster.
    heard: list[dict[str, Any]] = []
    bus.get_bus().subscribe("presence", heard.append)
    presence.mark_online("bram")
    presence.mark_offline("bram")
    assert heard == [
        {"event": "online", "player": "bram"},
        {"event": "offline", "player": "bram"},
    ]


def test_a_malformed_frame_never_corrupts_the_roster() -> None:
    bus.get_bus().publish("presence", {"event": "online"})  # no player
    bus.get_bus().publish("presence", {"event": "online", "player": 42})  # not a str
    bus.get_bus().publish("presence", {"player": "bram"})  # no event
    assert presence.online() == set()


def test_reconnect_keeps_the_roster_fed_after_a_bus_swap() -> None:
    # Swap in a real InProcessBus (standing for a broker) and reconnect: presence must follow the
    # new bus, or a production broker injection would silently stop feeding the roster.
    presence.mark_online("old")  # on the first bus
    bus.set_bus(bus.InProcessBus())
    presence.reconnect()
    presence.mark_online("new")  # only reaches the roster if presence re-subscribed
    assert "new" in presence.online()


# --- Phase 5: the roster also carries WHERE each hero stands ------------------------------------


def test_mark_online_with_a_room_places_the_hero():
    presence.mark_online("bram", "forge")
    assert presence.in_room("forge") == {"bram"}
    assert presence.online() == {"bram"}


def test_mark_at_moves_a_hero_between_rooms():
    presence.mark_online("bram", "forge")
    presence.mark_at("bram", "library")
    assert presence.in_room("forge") == set()
    assert presence.in_room("library") == {"bram"}


def test_mark_offline_clears_the_location():
    presence.mark_online("bram", "forge")
    presence.mark_offline("bram")
    assert presence.in_room("forge") == set()


def test_in_room_gathers_everyone_in_that_room():
    presence.mark_online("bram", "forge")
    presence.mark_online("mira", "forge")
    presence.mark_online("cass", "library")
    assert presence.in_room("forge") == {"bram", "mira"}


def test_mark_at_ignores_an_offline_hero():
    # a moved event for someone not online must not resurrect them onto the roster
    presence.mark_at("ghost", "forge")
    assert presence.in_room("forge") == set()
    assert presence.online() == set()


def test_mark_online_without_a_room_leaves_them_placeless():
    presence.mark_online("bram")  # no room -> online but not placed
    assert presence.online() == {"bram"}
    assert presence.in_room("forge") == set()
