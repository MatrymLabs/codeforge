"""Test twin for parts/world/condition.py -- the at-a-glance present-state Lens (status view).

Acceptance: a hale hero with a calling sees their vital pools and that nothing ails them; an
afflicted hero sees exactly what ails them; a sworn hero sees their Order standing; the `condition`
verb is reachable through the engine tick. Refusal: a hero with no calling yet is told so, not shown
invented pools (state is canonical -- the projection never fabricates resources a drifter lacks).
"""

from __future__ import annotations

import forge
from parts.world import afflictions, condition
from parts.world.jobs import bind_calling
from parts.world.session import SESSIONS, Session


def _hero() -> Session:
    s = Session(player_id="mark", location="void")
    bind_calling(s, "vanguard")  # a real calling gives real stats + pools
    return s


# --- acceptance ---------------------------------------------------------------------------------
def test_a_hale_hero_sees_pools_and_no_affliction():
    out = condition.render_condition(_hero())
    assert "Your condition:" in out
    assert "HP" in out and "MP" in out
    assert "nothing ails you" in out


def test_a_hero_with_a_power_pool_sees_it():
    from parts.world.resources import Resource

    s = _hero()
    s.resources["power"] = Resource(name="power", current=5, maximum=10)
    out = condition.render_condition(s)
    assert "Power 5/10" in out


def test_an_afflicted_hero_sees_exactly_what_ails_them():
    s = _hero()
    afflictions.apply_dot(s, "venom", 5, ticks=2)
    afflictions.apply_daze(s, 1)
    out = condition.render_condition(s)
    assert "venom (2)" in out and "dazed (1)" in out
    assert "nothing ails you" not in out


def test_a_sworn_hero_sees_their_standing():
    s = _hero()
    s.order = "making"
    s.reputation["making"] = 300  # the Honored floor
    out = condition.render_condition(s)
    assert "Sworn to" in out and "Honored" in out and "300" in out


def test_an_unsworn_hero_shows_no_standing_line():
    out = condition.render_condition(_hero())  # order == "" by default
    assert "Sworn to" not in out


# --- refusal ------------------------------------------------------------------------------------
def test_a_hero_with_no_calling_is_told_so_not_shown_empty_pools():
    s = Session(player_id="drifter", location="void")  # no bind_calling -> stats is None
    out = condition.render_condition(s)
    assert "no calling yet" in out
    assert "HP" not in out  # no pools invented for a hero who has none


# --- the verb is reachable through the engine tick ---------------------------------------------
def test_the_condition_verb_is_reachable():
    s = SESSIONS["matrym"] = Session(player_id="matrym", location="courtyard")
    bind_calling(s, "vanguard")
    out = forge.handle_command(s, "condition")
    assert "Your condition:" in out and "HP" in out
    SESSIONS.pop("matrym", None)
