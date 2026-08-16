"""Test twin for kernel/seed_package.py -- the deployment-tier scaling core.

Gates the campaign's founding move: intent (a tier's player count) in, a full, internally consistent
world blueprint out, sized by data-driven ratios calibrated to the real aethryn build. Covers both
acceptance (the five tiers derive sane, monotonic sizing; the manifest serializes) AND refusal
(unknown tier, empty project, non-positive players, a broken scaling ratio all fail loud).
"""

import json

import pytest

from kernel import seed_package as sp


def test_the_five_named_tiers_exist_and_climb_in_player_target():
    ids = [t.id for t in sp.DEPLOYMENT_TIERS]
    assert ids == ["prototype", "indie", "community", "commercial", "global"]
    players = [t.target_players for t in sp.DEPLOYMENT_TIERS]
    assert players == sorted(players) and players[0] == 500 and players[-1] == 1_000_000


def test_tier_lookup_resolves_and_refuses_the_unknown():
    assert sp.tier("prototype").name == "Prototype"
    with pytest.raises(sp.BlueprintPackageError, match="unknown deployment tier"):
        sp.tier("galactic")


def test_the_prototype_tier_derives_the_shipped_map_worlds_scale():
    # The model is anchored to aethryn (~53,500 rooms for ~500 players); the derivation must land in
    # that neighborhood, not drift into fantasy. This is the honesty anchor, pinned.
    sizing = sp.derive_sizing(sp.tier("prototype"))
    assert 50_000 <= sizing.rooms <= 56_000
    assert 10 <= sizing.zones <= 20  # aethryn ships 14 zones
    assert sizing.dungeons >= 1 and sizing.bosses >= 1 and sizing.settlements >= 1


def test_sizing_scales_monotonically_with_player_count():
    # A bigger tier is a bigger world in every dimension; nothing shrinks as players grow.
    small = sp.derive_sizing(sp.tier("prototype"))
    big = sp.derive_sizing(sp.tier("global"))
    for field in ("rooms", "zones", "regions", "settlements", "dungeons", "npcs", "quests"):
        assert getattr(big, field) > getattr(small, field), f"{field} did not grow with scale"
    # Global targets 2000x Prototype's players, so rooms scale 2000x (ratios are proportional).
    assert big.rooms == small.rooms * 2000


def test_derivation_refuses_a_non_positive_player_target():
    broken = sp.DeploymentTier("empty", "Empty", 0, "no players")
    with pytest.raises(sp.BlueprintPackageError, match="positive player count"):
        sp.derive_sizing(broken)


def test_a_broken_scaling_ratio_fails_loud_by_field():
    bad = sp.ScalingModel(rooms_per_zone=0.0)
    with pytest.raises(sp.BlueprintPackageError, match="rooms_per_zone"):
        bad.validate()


def test_hardware_note_is_honest_about_outgrowing_a_single_host():
    fits = sp.derive_sizing(sp.tier("prototype"))
    assert "single host" in sp.hardware_note(fits)
    huge = sp.derive_sizing(sp.tier("global"))
    note = sp.hardware_note(huge)
    assert "exceeds one host" in note and "shard" in note


def test_storage_human_reads_in_the_right_unit():
    proto = sp.derive_sizing(sp.tier("prototype"))
    # ~53,500 rooms * ~36 KB/room ~= 1.8 GB, reported in GB.
    assert proto.storage_human.endswith("GB")


def test_compile_manifest_produces_a_serializable_blueprint():
    m = sp.compile_manifest("Aethryn", "prototype")
    assert m.project == "Aethryn" and m.tier_id == "prototype"
    payload = json.loads(m.to_json())
    assert payload["schema_version"] == 1
    assert payload["tier_id"] == "prototype"
    assert payload["sizing"]["rooms"] == m.sizing.rooms
    md = m.to_markdown()
    assert "Deployment Tier: Prototype" in md and "Estimated Rooms:" in md


def test_compile_manifest_refuses_an_empty_project_name():
    with pytest.raises(sp.BlueprintPackageError, match="non-empty project name"):
        sp.compile_manifest("   ", "prototype")
