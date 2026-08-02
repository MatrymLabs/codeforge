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
from parts.scripting import scripting_available
from parts.world.session import SESSIONS, Session
from parts.world.world import WORLD


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


def test_admin_verbs_are_derived_from_the_spine() -> None:
    verbs = COMMANDS.admin_verbs()
    assert verbs == sorted(verbs)  # sorted, so a listing is stable
    assert all(v.startswith("@") for v in verbs)  # only sigil verbs
    assert {"@sg", "@forge", "@arch"} <= set(verbs)  # the real admin surface, not a subset


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


# --- compound directions (ne/nw/se/sw) + noun exits ("nouns as rooms") -------
# The compass gained its diagonals and a threshold may be keyed by the noun it opens onto. Proven
# by hanging a `ne` and a `market` exit off a real room, then restoring it (mutates only the
# exits map, a dict[str, str]).


@pytest.fixture
def _named_exits() -> Iterator[None]:
    exits = WORLD["forge"]["exits"]
    saved = dict(exits)
    exits["northeast"] = "courtyard"  # a diagonal, keyed canonically (like "north", not "n")
    exits["market"] = "courtyard"  # a threshold named for its destination
    try:
        yield
    finally:
        exits.clear()
        exits.update(saved)


def test_bare_compound_direction_moves(_named_exits: None) -> None:
    session = _walker("forge")
    handle_command(session, "ne")  # a bare diagonal, registered off DIRECTIONS
    assert session.location == "courtyard"


def test_bare_noun_exit_moves(_named_exits: None) -> None:
    session = _walker("forge")
    handle_command(session, "market")  # a lone noun that names an exit walks through it
    assert session.location == "courtyard"


def test_go_forwards_a_noun_exit(_named_exits: None) -> None:
    session = _walker("forge")
    handle_command(session, "go market")
    assert session.location == "courtyard"


def test_unknown_word_naming_no_exit_still_huhs(_named_exits: None) -> None:
    # A lone word that is neither a verb nor an exit of this room is still refused, unmoved --
    # the noun-exit fallback must not swallow genuine nonsense.
    session = _walker("forge")
    assert "Huh?" in handle_command(session, "banana")
    assert session.location == "forge"


def test_a_near_miss_command_suggests_the_nearest_spine_verb() -> None:
    # The "did you mean ...?" nudge, reachable through the tick (kernel.shelf.textmatch).
    session = _walker("forge")
    verbs = {c.verb.split(" ", 1)[0].lower() for c in COMMANDS.available_to(session)}
    target = next(v for v in sorted(verbs, key=len, reverse=True) if len(v) >= 5)
    out = handle_command(
        session, target[:-1]
    )  # drop the last char: edit distance 1 from a real verb
    assert "Huh?" in out
    assert "Did you mean `" in out


def test_pure_nonsense_gets_no_suggestion() -> None:
    # The max-distance guard: gibberish far from every verb gets a plain refusal, not a wild guess.
    session = _walker("forge")
    out = handle_command(session, "qwertyzxcv")
    assert "Huh?" in out
    assert "Did you mean" not in out


# --- @script: the owner-only sandboxed Lua console (polyglot organ 7) ---------


def test_script_command_is_owner_gated() -> None:
    player = _walker("forge")  # default rank: player
    out = handle_command(player, "@script return 1")
    assert "Denied" in out  # an ADMIN verb a mere player cannot reach


def test_script_command_without_lua_reports_cleanly(monkeypatch) -> None:
    # Even with lupa installed, the graceful 'not installed' path must read cleanly (base gate).
    import parts.scripting as scripting

    monkeypatch.setattr(scripting, "scripting_available", lambda: False)
    session = _walker("forge")
    session.rank = "owner"
    assert "not installed" in handle_command(session, "@script return 1").lower()


@pytest.mark.skipif(not scripting_available(), reason="Lua runtime not installed (the [lua] extra)")
def test_owner_runs_a_sandboxed_script_through_the_tick() -> None:
    session = _walker("forge")
    session.rank = "owner"
    out = handle_command(session, "@script emit('hi'); return 6 * 7")
    assert "hi" in out and "42" in out


@pytest.mark.skipif(not scripting_available(), reason="Lua runtime not installed (the [lua] extra)")
def test_a_sandbox_violation_returns_a_script_error_not_a_crash() -> None:
    session = _walker("forge")
    session.rank = "owner"
    out = handle_command(session, "@script return os.time()")
    assert "script error" in out.lower()  # os is denied; the tick reports it, never crashes


# --- stage 2 slice E: console/diagnostic verbs, now on the spine -------------


def test_store_index_reachable_through_the_spine() -> None:
    assert "Hardware Store" in handle_command(_player(), "store")


def test_complexity_lens_reachable_through_the_spine() -> None:
    assert "Complexity hot-spots" in handle_command(_player(), "complexity")


def test_clones_lens_reachable_through_the_spine() -> None:
    assert "Clone scan" in handle_command(_player(), "clones")


# --- stage 2 slice F: ability aliases reach the same handler over the spine ---


def test_barrier_alias_deploys_through_the_spine() -> None:
    from parts.world.jobs import bind_calling

    session = _player()
    bind_calling(session, "engineer")  # deploy_barrier needs the Engineer's kit
    assert "deploy a barrier" in handle_command(session, "barrier")


def test_secondary_alias_sets_a_subjob_through_the_spine() -> None:
    from parts.world.jobs import bind_calling

    session = _player()
    bind_calling(session, "engineer")  # a primary is required first
    assert "as your secondary" in handle_command(session, "secondary scholar")


def test_two_word_ability_aliases_dispatch_through_the_spine() -> None:
    # "field repair" and "deploy barrier" are multi-word verbs (longest-first match); each shares
    # its one-word form's designation and reaches the same Engineer handler.
    from parts.world.jobs import bind_calling

    session = _player()
    bind_calling(session, "engineer")
    assert "repair" in handle_command(session, "field repair").lower()
    assert "barrier" in handle_command(session, "deploy barrier").lower()


def test_unlock_without_with_prompts() -> None:
    # The no-"with" branch of _unlock_cmd (stage 2 slice G): a usage prompt, no door touched.
    out = handle_command(_player(), "unlock door")
    assert out == "Unlock what with what? Try: unlock door with key"


# --- stage 2 slice H: classroom + lifecycle verbs, the finale ----------------


def test_help_returns_the_help_text_through_the_spine() -> None:
    from forge import HELP_TEXT

    assert handle_command(_player(), "help") == HELP_TEXT


def test_save_and_load_round_trip_through_the_spine() -> None:
    # conftest quarantines the snapshot into tmp; save seals, load restores.
    assert "Saved" in handle_command(_player(), "save")
    out = handle_command(_player(), "load")
    assert "Loaded" in out and "Huh?" not in out


def test_score_with_a_bad_mode_surfaces_the_error() -> None:
    # The ValueError branch of _score_cmd: the renderer rejects an unknown mode, surfaced as text.
    from parts.world.jobs import bind_calling

    session = _player()
    bind_calling(session, "engineer")
    assert "unknown display_mode" in handle_command(session, "score no-such-mode")


def test_lesson_with_an_unknown_subcommand_prompts() -> None:
    out = handle_command(_player(), "lesson wibble")
    assert out == "Try: lesson list, or lesson start <subject>"


def test_solo_opening_shows_the_seed_splash_then_the_scene() -> None:
    # Solo play now opens with the world's own splash (like the gateways), not a generic line.
    from forge import render_opening

    session = Session(player_id="solo", location="forge")
    SESSIONS["solo"] = session
    opening = render_opening(session)
    assert "F I R S T   F O R G E" in opening  # the seed's splash banner
    assert render_scene("forge", viewer="solo") in opening  # then the room they wake in
    assert "Type HELP for commands." in opening


def test_game_loop_prints_the_opening_then_runs_one_command(monkeypatch, capsys) -> None:
    # Drive the terminal loop with a scripted keyboard: it prints the splash opening, then a
    # single `quit` ends the loop cleanly (the driver's only exit is session.alive going False).
    import forge

    keys = iter(["quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(keys))
    forge.game_loop()
    printed = capsys.readouterr().out
    assert "F I R S T   F O R G E" in printed  # the opening splash reached the screen
    assert "The world dims" in printed  # quit ran through the spine and ended the loop
