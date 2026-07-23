"""Test twin for parts/generate.py -- @sg, the system item generator.

Acceptance (a known pattern spawns, a second spawn gets a unique instance, the
wizard command reaches it through the tick) and refusal (unknown pattern conjures
nothing, a mere player is denied) are both pinned.
"""

from collections.abc import Iterator

import pytest

from forge import handle_command
from parts.generate import generate_item, load_patterns, system_generate
from parts.world.items import ITEMS
from parts.world.session import SESSIONS, Session

_PATTERNS = {
    "excalibur": {"name": "Excalibur, the drawn blade", "keywords": ["excalibur", "sword"]},
}


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    spawned = {k for k in ITEMS if k.startswith("excalibur")}
    for k in spawned:
        ITEMS.pop(k, None)
    SESSIONS.clear()
    yield
    for k in {k for k in ITEMS if k.startswith("excalibur")}:
        ITEMS.pop(k, None)
    SESSIONS.clear()


def test_generate_spawns_a_known_pattern_into_the_room() -> None:
    label, message = generate_item("excalibur", "forge", patterns=_PATTERNS)
    assert label == "excalibur"
    assert ITEMS["excalibur"]["location"] == "room:forge"
    assert "Forged" in message


def test_a_second_spawn_gets_a_unique_instance() -> None:
    generate_item("excalibur", "forge", patterns=_PATTERNS)
    label, _ = generate_item("excalibur", "forge", patterns=_PATTERNS)
    assert label == "excalibur_2"
    assert "excalibur_2" in ITEMS


def test_an_unknown_pattern_conjures_nothing() -> None:
    label, message = generate_item("godsword", "forge", patterns=_PATTERNS)
    assert label is None
    assert "godsword" not in ITEMS
    assert "No pattern" in message


def test_usage_when_not_item() -> None:
    session = Session(player_id="wiz")
    session.rank = "wizard"
    assert "Usage" in system_generate(session, "room haven")


def test_the_real_catalog_has_excalibur() -> None:
    assert "excalibur" in load_patterns()


# --- through the engine tick: rank-gated -------------------------------------


def _at(room: str, rank: str) -> Session:
    session = Session(player_id=f"u_{rank}")
    session.location = room
    session.rank = rank
    SESSIONS[session.player_id] = session
    return session


def test_a_player_is_denied_generation() -> None:
    out = handle_command(_at("forge", "player"), "@sg item excalibur")
    assert "Denied" in out
    assert "excalibur" not in ITEMS  # nothing spawned


def test_a_wizard_can_generate_through_the_tick() -> None:
    out = handle_command(_at("forge", "wizard"), "@sg item excalibur")
    assert "Forged" in out
    assert "ITM-04.001" in out  # traced to its filed pattern
    assert ITEMS["excalibur"]["location"] == "room:forge"
