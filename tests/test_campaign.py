"""Acceptance tests for the campaign-wide Aethryn level 1-300 content contract."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("FORGE_SEED", "aethryn")

from kernel.world.campaign import load_campaign, report, validate  # noqa: E402
from kernel.world.quest import all_ids  # noqa: E402
from kernel.world.seed import BLUEPRINT_DIR, load_zones  # noqa: E402
from kernel.world.world import NPCS, WORLD, _dungeons, _settlements  # noqa: E402


def _inputs():
    zones = [
        dict(zone, label=label)
        for label, zone in load_zones(BLUEPRINT_DIR / "zones.yaml", set(WORLD)).items()
    ]
    return zones, _dungeons or [], _settlements or [], NPCS, all_ids()


@pytest.mark.skipif(BLUEPRINT_DIR.name != "aethryn", reason="the worker loaded a different seed")
def test_aethryn_campaign_contract_covers_the_full_level_range():
    contract = load_campaign(BLUEPRINT_DIR / "campaign.yaml")
    assert contract is not None
    result = report(contract, *_inputs())
    assert result["zones"] == 14
    assert result["level_cap"] == 300
    assert result["level_band_gaps"] == []
    assert all(result["checkpoints"].values())


@pytest.mark.skipif(BLUEPRINT_DIR.name != "aethryn", reason="the worker loaded a different seed")
def test_every_zone_has_the_complete_content_shape():
    contract = load_campaign(BLUEPRINT_DIR / "campaign.yaml")
    assert contract is not None
    result = report(contract, *_inputs())
    minimums = result["minimums"]
    for zone in result["zone_rows"]:
        assert zone["dungeons"] >= minimums["dungeons"], zone
        assert zone["settlements"] >= minimums["settlements"], zone
        assert zone["combatants"] >= minimums["combatants"], zone
        assert zone["npcs"] >= minimums["npcs"], zone
        assert zone["quests"] >= minimums["quests"], zone


@pytest.mark.skipif(BLUEPRINT_DIR.name != "aethryn", reason="the worker loaded a different seed")
def test_live_world_passes_the_campaign_gate():
    result = validate(BLUEPRINT_DIR / "campaign.yaml", *_inputs())
    assert result is not None
    assert result["combatants"] > 50_000
    assert result["quests"] > 1_000
