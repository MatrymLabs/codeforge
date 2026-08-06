import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

from kernel.gmcp import aethryn_profile
from kernel.world import items
from kernel.world.authored_towns import raise_town
from kernel.world.items import carrier
from kernel.world.seed import SEEDS_ROOT


def _clear_carrier(player_id: str) -> None:
    owner = carrier(player_id)
    for iid in list(items.items_in(owner)):
        items.ITEMS.pop(iid, None)


def test_adapted_ashen_monoliths_resolves_current_town_contract() -> None:
    rooms, npcs, local_items = raise_town(
        SEEDS_ROOT / "aethryn" / "authored" / "ashen_monoliths.yaml"
    )

    assert rooms["ashen_monoliths_cinderfield"]["node"] == "cinderium"
    assert npcs["ashen_monoliths_surveylead"]["shop"]["buys"] == {"cinderium": 14}
    assert npcs["ashen_monoliths_commandshade"]["loot"]["cinderium"] == 3
    assert set(local_items) == {"ashen_monoliths_halfcommand", "ashen_monoliths_cinderline"}


def test_adapted_makers_accord_observes_real_gather_and_craft_actions() -> None:
    # The quest registry is selected once at import, so run the live Aethryn contract in the same
    # process shape as the gateway rather than mutating a globally loaded first-forge registry.
    script = dedent(
        """
        from kernel.world import crafting, gather, items, quest
        from kernel.world.items import carrier
        from kernel.world.jobs import bind_calling
        from kernel.world.session import Session

        player_id = "harvest-adaptation-test"
        session = Session(player_id=player_id, location="greenhold_smithy", named=True)
        bind_calling(session, "vanguard")
        try:
            quest.on_event(session, "enter", "greenhold_smithy")
            assert quest._RUNS[player_id]["veridia_makers_accord"].state == "gathering"
            session.location = "greenhold_fields"
            gathered = gather.gather(session)
            assert "meadowfoil" in gathered
            assert quest._RUNS[player_id]["veridia_makers_accord"].state == "crafting"
            items.clone("meadowfoil", carrier(player_id))
            forged = crafting.craft(session, "meadowfoil_salve")
            assert "forge" in forged.lower()
            assert quest._RUNS[player_id]["veridia_makers_accord"].state == "done"
            assert session.reputation.get("making") == 30
            assert (
                len(
                    [
                        iid
                        for iid in items.items_in(carrier(player_id))
                        if items.prototype_of(iid) == "herbal_salve"
                    ]
                )
                == 1
            )
            reward = quest._apply_effect(
                quest._QUESTS["veridia_makers_accord"], "grant_item:meadowfoil", session
            )
            assert "receive" in reward and "meadowfoil" in reward
        finally:
            quest._RUNS.pop(player_id, None)
            for iid in list(items.items_in(carrier(player_id))):
                items.ITEMS.pop(iid, None)
        """
    )
    environment = dict(os.environ, FORGE_SEED="aethryn")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        env=environment,
    )
    assert result.returncode == 0


def test_adapted_profile_uses_current_runtime_bindings() -> None:
    profile = aethryn_profile(version="1.1.0")

    assert profile["version"] == "1.1.0"
    assert profile["terminology"] == {
        "job": "Calling",
        "jobs": "Callings",
        "skill": "Technique",
        "skills": "Techniques",
    }
    assert {panel["name"] for panel in profile["panels"]} == {
        "Region",
        "Map",
        "Character",
        "Calling",
        "Quest",
        "Observation Log",
    }
