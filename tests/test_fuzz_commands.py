"""Fuzz tests: the command dispatcher on the untrusted player-input boundary.

Every player command is untrusted input (developer-security campaign, Phase 8/13). `CommandSet`
(parts/commands.py) parses arbitrary text and rank-gates it. This fuzzes the dispatcher with
arbitrary unicode, control characters, ANSI escapes, and overlong strings, asserting two things:

  1. it never raises and always returns None or a str (crash-resistance);
  2. no input a PLAYER sends ever executes an ADMIN (owner-only) command -- the parser can never
     become an authorization bypass, however the verb is phrased, cased, or padded.

Runs under `make fuzz`.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kernel.world.session import Session
from parts.commands import ADMIN, CORE, Command, CommandSet

_ADMIN_MARKER = "OWNER-ONLY-RAN"  # the admin handler's output; it must never surface for a player


def _command_set() -> CommandSet:
    """A representative spine: a bare CORE verb, a multi-word CORE verb, an owner-only @ verb."""
    cs = CommandSet()
    cs.add(Command("look", "CMD-00.001", "look around", lambda s, a: f"looked:{a}", CORE, "player"))
    cs.add(Command("registry show", "CMD-00.002", "reg", lambda s, a: "registry", CORE, "player"))
    cs.add(Command("@spawn", "CMD-00.003", "spawn", lambda s, a: _ADMIN_MARKER, ADMIN, "owner"))
    return cs


# Hostile input: arbitrary unicode; a verb-adjacent alphabet (so @spawn is actually reached and the
# rank gate is exercised, not just missed); and pure control/whitespace bytes.
_HOSTILE = st.one_of(
    st.text(max_size=200),
    st.text(alphabet="look@spawn registryshow \x1b[0m\x00\r\n\t", max_size=100),
    st.text(alphabet="\x00\x1b\r\n\t ", max_size=100),
)


@pytest.mark.fuzz
@given(_HOSTILE)
@settings(max_examples=500, deadline=None)
def test_dispatch_never_crashes_on_hostile_input(text):
    result = _command_set().dispatch(Session(player_id="p", location="x"), text)
    assert result is None or isinstance(result, str)


@pytest.mark.fuzz
@given(_HOSTILE)
@settings(max_examples=500, deadline=None)
def test_a_player_can_never_run_an_admin_command_however_phrased(text):
    # A player-rank session (the default) must never reach the owner-only handler. If the parser
    # matched @spawn, the rank gate returns a denial string -- never the handler's output.
    player = Session(player_id="p", location="x")
    assert player.rank == "player"
    result = _command_set().dispatch(player, text)
    assert result != _ADMIN_MARKER


@pytest.mark.fuzz
@given(_HOSTILE)
@settings(max_examples=300, deadline=None)
def test_case_and_padding_never_smuggle_an_admin_verb_past_the_gate(text):
    # Explicitly probe the classic bypass shapes -- uppercased, padded, or suffixed admin verbs --
    # by prefixing hostile noise onto a real admin invocation. Still denied for a player.
    player = Session(player_id="p", location="x")
    for variant in (f"@SPAWN {text}", f"  @spawn{text}", f"@spawn\t{text}"):
        assert _command_set().dispatch(player, variant) != _ADMIN_MARKER
