"""Engine-tick test for the `map` verb (RD-2026-0007 wave 2 consumer of the minimap shelf part).

A verb is not wired until handle_command proves it reachable (the house rule). Lives here, not in
the minimap shelf twin, so the shelf part stays engine-free (poolable in a standalone pour).
"""

from __future__ import annotations

from forge import handle_command
from kernel.world.session import Session


def test_map_verb_reachable_and_renders() -> None:
    out = handle_command(Session(player_id="mapper"), "map")
    assert isinstance(out, str)
    # a spawned player sees their room marked on the minimap (or an honest 'nowhere' message)
    assert "@" in out or "nowhere" in out.lower()
