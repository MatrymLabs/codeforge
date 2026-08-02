"""Test twin for tools/zone_density.py -- the per-zone content-density audit.

Acceptance: the audit reads every flagship zone and attributes zone-declared content (settlements +
dungeons + quests). Refusal: a zone below the launch floor is FLAGGED, not silently passed - a zone
with zero dungeons or quests must appear in its `thin_on` list, so under-built zones cannot hide.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import zone_density  # noqa: E402


def test_audits_every_zone():
    rows = zone_density.audit()
    # the flagship's zones.yaml declares 14 zones; the audit must cover all of them.
    assert len(rows) == 14
    assert all(r["zone"] and r["band"] for r in rows)


def test_a_zone_with_no_dungeon_or_no_quest_is_flagged_thin():
    rows = {r["zone"]: r for r in zone_density.audit()}
    # every row whose count is under the floor must name that dimension in thin_on (no silent pass).
    for r in rows.values():
        if r["dungeons"] < zone_density.FLOOR["dungeons"]:
            assert "dungeons" in r["thin_on"]
        if r["quests"] < zone_density.FLOOR["quests"]:
            assert "quests" in r["thin_on"]
        if r["settlements"] < zone_density.FLOOR["settlements"]:
            assert "settlements" in r["thin_on"]
        # a zone meeting every floor is NOT flagged.
        if not r["thin_on"]:
            assert (
                r["dungeons"] >= zone_density.FLOOR["dungeons"]
                and r["quests"] >= zone_density.FLOOR["quests"]
                and r["settlements"] >= zone_density.FLOOR["settlements"]
            )


def test_score_orders_thin_below_dense():
    rows = zone_density.audit()
    # rows are returned thinnest-first (ascending score); the first is <= the last.
    assert rows[0]["score"] <= rows[-1]["score"]


def test_two_token_settlement_quests_are_attributed():
    # Regression: a naive text-scan on settlement KEYS undercounts zones whose settlement keys carry
    # a suffix (aurelian_city) while quests reference the stem (aurelian_gantry). Skyward Spires
    # has authored quests and must NOT read as zero. Attribution is by room-stem, not key substring.
    rows = {r["zone"]: r for r in zone_density.audit()}
    assert rows["Skyward Spires"]["quests"] >= 1
    assert "quests" not in rows["Skyward Spires"]["thin_on"]


def test_ambiguous_stem_is_dropped_not_guessed():
    # A stem owned by more than one zone (a bare `the`) must not attribute; the index drops it.
    zones = zone_density._load("zones.yaml")
    setts = zone_density._load("settlements.yaml")
    dungs = zone_density._load("dungeons.yaml")
    assert "the" not in zone_density._stem_index(zones, setts, dungs)
