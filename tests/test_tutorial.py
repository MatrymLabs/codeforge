"""Test twin for kernel/world/tutorial.py -- the state-driven onboarding ladder.

Acceptance: next_step names the right next thing at each rung of a new hero's first hour (no calling
-> untested -> ungeared -> established), from live state; the `tutorial` verb reaches it through
the tick. Nudge: greeting welcomes a brand-new hero and points them at the first step, but is silent
for an established hero (one who already holds a calling), so a veteran is never nagged.
"""

from __future__ import annotations

from kernel.world import tutorial
from kernel.world.jobs import bind_calling
from kernel.world.session import Session


def test_a_hero_with_no_calling_is_told_to_choose_one():
    step = tutorial.next_step(Session(player_id="new"))
    assert "JOBS" in step and "JOB <name>" in step


def test_a_fresh_calling_is_told_to_learn_to_fight():
    s = Session(player_id="bram")
    bind_calling(s, "vanguard")  # has a calling, level 1
    step = tutorial.next_step(s)
    assert "ATTACK" in step and "SKILLS" in step


def test_a_levelled_but_ungeared_hero_is_told_to_gear_up():
    s = Session(player_id="bram")
    bind_calling(s, "vanguard")
    s.level = 5  # past the first fight, but wearing nothing
    step = tutorial.next_step(s)
    assert "EQUIP" in step and "SCORE" in step


def test_an_established_hero_is_told_the_world_is_open():
    s = Session(player_id="bram")
    bind_calling(s, "vanguard")
    s.level = 5
    s.equipped["weapon"] = "some_blade"  # geared: past onboarding
    step = tutorial.next_step(s)
    assert "world is open" in step and "HELP" in step


def test_greeting_welcomes_a_brand_new_hero_with_the_first_step():
    nudge = tutorial.greeting(Session(player_id="new"))
    assert "New to Aethryn" in nudge and "TUTORIAL" in nudge
    assert "JOBS" in nudge  # carries the first step inline


def test_greeting_is_silent_for_an_established_hero():
    s = Session(player_id="bram")
    bind_calling(s, "vanguard")  # already has a calling
    assert tutorial.greeting(s) == ""  # a veteran is never nagged


def test_tutorial_reaches_through_the_engine_tick():
    from forge import handle_command

    out = handle_command(Session(player_id="new"), "tutorial")
    assert "choose a calling" in out  # the verb surfaces the current step


def test_the_tutorial_names_the_booted_world_not_a_hardcoded_one() -> None:
    """The world is data: a seed names itself, and Python does not name it for them.

    This line read "Welcome to Aethryn" as a hardcoded literal, so a player on first-forge (the
    DEFAULT seed) was welcomed to a world they were not in, and a third-party seed had no way to
    correct it without editing the engine. Found by driving the actual login walk, not by a test.
    """
    from kernel.world.seed import SEED_NAME
    from kernel.world.tutorial import WORLD_TITLE, next_step
    from kernel.world.world_manifest import describe_world

    assert describe_world(SEED_NAME).title == WORLD_TITLE
    greeting = next_step(Session(player_id="newcomer"))
    assert WORLD_TITLE in greeting
    if SEED_NAME != "aethryn":
        assert "Aethryn" not in greeting  # the defect: the wrong world, named in Python
