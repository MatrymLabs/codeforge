"""Test twin for parts/commands.py -- the command spine.

The framework (namespace rules, rank-gated dispatch, seed-verb guard) is tested in
isolation; the registry command family is proven reachable through the engine tick
against the real shipped registry.
"""

from collections.abc import Iterator

import pytest

from forge import COMMANDS, handle_command, render_scene
from parts.commands import (
    ADMIN,
    CORE,
    SEED,
    Command,
    CommandError,
    CommandSet,
    guard_seed_verbs,
    reserved_words,
)
from parts.registry import load_collective
from parts.session import SESSIONS, Session


def _echo(session: Session, arg: str) -> str:
    return f"ran:{arg}"


# --- the template class enforces the namespace rules -------------------------


def test_admin_verb_must_wear_the_sigil() -> None:
    with pytest.raises(CommandError, match="must start with"):
        Command("sg", "CMD-10.009", "x", _echo, namespace=ADMIN)


def test_only_admin_may_use_the_sigil() -> None:
    with pytest.raises(CommandError, match="only ADMIN"):
        Command("@forge", "CMD-10.009", "x", _echo, namespace=SEED)


def test_a_bad_namespace_is_refused() -> None:
    with pytest.raises(CommandError, match="namespace"):
        Command("x", "CMD-10.009", "x", _echo, namespace="wild")


# --- dispatch: longest-first, rank-gated, fall-through -----------------------


def test_longest_verb_wins() -> None:
    cs = CommandSet()
    cs.add(Command("registry", "CMD-10.001", "list", lambda s, a: "list", namespace=CORE))
    cs.add(
        Command(
            "registry show",
            "CMD-10.002",
            "show",
            lambda s, a: f"show:{a}",
            namespace=CORE,
        )
    )
    session = Session(player_id="p")
    assert cs.dispatch(session, "registry show RM-1") == "show:RM-1"
    assert cs.dispatch(session, "registry") == "list"


def test_unmatched_input_falls_through_to_none() -> None:
    cs = CommandSet()
    cs.add(Command("registry", "CMD-10.001", "list", lambda s, a: "list", namespace=CORE))
    assert cs.dispatch(Session(player_id="p"), "look") is None


def test_an_admin_command_denies_a_mere_player() -> None:
    cs = CommandSet()
    cs.add(Command("@sg", "CMD-09.001", "generate", _echo, namespace=ADMIN, min_rank="owner"))
    player = Session(player_id="p")  # default rank: player
    assert "Denied" in str(cs.dispatch(player, "@sg item excalibur"))
    owner = Session(player_id="o")
    owner.rank = "owner"
    assert cs.dispatch(owner, "@sg item excalibur") == "ran:item excalibur"


def test_duplicate_verbs_are_refused() -> None:
    cs = CommandSet()
    cs.add(Command("x", "CMD-10.001", "a", _echo, namespace=CORE))
    with pytest.raises(CommandError, match="duplicate"):
        cs.add(Command("X", "CMD-10.002", "b", _echo, namespace=CORE))


# --- the scale safety net: a seed can't shadow reserved words ----------------


def test_seed_verb_may_not_shadow_a_core_word() -> None:
    with pytest.raises(CommandError, match="shadows a reserved word"):
        guard_seed_verbs(["look"], reserved={"look", "registry"})


def test_seed_verb_may_not_use_the_admin_sigil() -> None:
    with pytest.raises(CommandError, match="reserved '@' sigil"):
        guard_seed_verbs(["@sg"], reserved=set())


def test_a_clean_seed_verb_passes() -> None:
    guard_seed_verbs(["forge", "cast"], reserved={"look", "registry"})  # no raise


def test_reserved_words_covers_core_and_admin() -> None:
    assert "registry" in reserved_words(COMMANDS)


# --- reachable through the engine tick, over the real registry ---------------


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def _player() -> Session:
    session = Session(player_id="reader")
    SESSIONS["reader"] = session
    return session


def test_registry_show_renders_a_room_card() -> None:
    out = handle_command(_player(), "registry show RM-03.002")
    assert "Designation:  RM-03.002" in out
    assert "Classroom of Practical Arts" in out
    assert "Library & Classroom" in out


def test_registry_type_and_status_filter() -> None:
    session = _player()
    assert "RM-01.001" in handle_command(session, "registry type RM")
    assert "prototype" in handle_command(session, "registry status prototype").lower()


def test_registry_find_searches() -> None:
    assert "archive" in handle_command(_player(), "registry find archive").lower()


def test_every_registry_command_is_filed() -> None:
    # code <-> registry sync: each wired command's designation is a filed CMD record
    filed = {r.designation for r in load_collective()}
    for command in COMMANDS.commands:
        assert command.designation in filed, f"{command.verb} is not filed"


# --- stage 2 slice D: movement verbs, now on the spine -----------------------


def _walker(location: str = "forge") -> Session:
    session = Session(player_id="walker", location=location)
    SESSIONS["walker"] = session
    return session


def test_look_renders_the_scene_through_the_spine() -> None:
    session = _walker("library")
    assert handle_command(session, "look") == render_scene("library", viewer="walker")


def test_look_alias_l_also_renders() -> None:
    session = _walker("library")
    assert handle_command(session, "l") == render_scene("library", viewer="walker")


def test_a_bare_direction_moves_through_the_spine() -> None:
    session = _walker("forge")
    handle_command(session, "n")
    assert session.location == "courtyard"  # forge -> north -> courtyard


def test_go_forwards_a_direction_word() -> None:
    session = _walker("forge")
    handle_command(session, "go north")
    assert session.location == "courtyard"


def test_go_refuses_a_non_direction() -> None:
    session = _walker("forge")
    assert handle_command(session, "go banana") == "You can't go that way."
    assert session.location == "forge"  # unmoved


def test_bare_go_refuses() -> None:
    # The bare verb reaches _go_cmd with an empty arg (the new spine branch): a clear refusal,
    # where the legacy ladder let bare `go` fall through to "Huh?".
    session = _walker("forge")
    assert handle_command(session, "go") == "You can't go that way."
    assert session.location == "forge"
