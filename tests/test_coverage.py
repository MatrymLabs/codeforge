"""Test twin for parts/coverage.py -- the content-reaches-engine coverage gate.

Acceptance: the live shipped seeds witness every engine capability (the enforced gate), and each
detector fires on the seed feature it names. Refusal: a capability no pack exercises is flagged DARK
with a fix hint; RESERVED suppresses that (a deliberate "built, not yet content"); a RESERVED name
that IS exercised is flagged stale, so the reserve list cannot hide a now-covered capability.
"""

from typing import cast

import parts.coverage as cov
from parts.coverage import (
    CAPABILITIES,
    PackContent,
    _coverage,
    _violations,
    unexercised_capabilities,
)
from parts.seed import Door, Item, Job, Npc, QuestSpec


def _pack(**kw: object) -> PackContent:
    """A pack with empty tables by default; pass npcs/doors/items/jobs/quest to witness one."""
    return PackContent(
        pack=cast(str, kw.get("name", "fixture")),
        npcs=cast("dict[str, Npc]", kw.get("npcs", {})),
        doors=cast("dict[str, Door]", kw.get("doors", {})),
        items=cast("dict[str, Item]", kw.get("items", {})),
        jobs=cast("dict[str, Job]", kw.get("jobs", {})),
        quest=cast("QuestSpec | None", kw.get("quest")),
    )


# --- acceptance --------------------------------------------------------------------------------


def test_the_live_seeds_witness_every_capability():
    """The enforced gate: no shipped engine capability is dark. This is the anti-recurrence pin."""
    assert unexercised_capabilities() == []


def test_each_detector_fires_on_its_seed_feature():
    seen = _coverage(
        [
            _pack(name="agg", npcs=cast("dict[str, Npc]", {"x": {"aggressive": True}})),
            _pack(name="atk", npcs=cast("dict[str, Npc]", {"x": {"atk": 5}})),
            _pack(name="door", doors=cast("dict[str, Door]", {"d": {"locked": True}})),
            _pack(name="gear", items=cast("dict[str, Item]", {"i": {"mods": {"ATK": 6}}})),
            _pack(name="job", jobs=cast("dict[str, Job]", {"j": {}})),
            _pack(name="story", quest=cast(QuestSpec, object())),
        ]
    )
    assert seen["proactive_combat"] == ["agg"]
    assert seen["reactive_combat"] == ["atk"]
    assert seen["locked_barrier"] == ["door"]
    assert seen["equipment"] == ["gear"]
    assert seen["calling"] == ["job"]
    assert seen["quest"] == ["story"]


def test_a_passive_or_bare_pack_witnesses_nothing():
    # an NPC with atk 0 and no aggression does not witness combat; a bare item no equipment
    seen = _coverage(
        [
            _pack(
                npcs=cast("dict[str, Npc]", {"x": {"atk": 0, "aggressive": False}}),
                items=cast("dict[str, Item]", {"i": {"mods": {}}}),
            )
        ]
    )
    assert seen["proactive_combat"] == []
    assert seen["reactive_combat"] == []
    assert seen["equipment"] == []


# --- refusal / hostile -------------------------------------------------------------------------


def _full_map() -> dict[str, list[str]]:
    """A coverage map where every capability is witnessed (baseline for the refusal tests)."""
    return {cap.name: ["aethryn"] for cap in CAPABILITIES}


def test_a_dark_capability_is_flagged_with_a_fix_hint():
    dark = {**_full_map(), "proactive_combat": []}
    problems = _violations(dark)
    assert any("proactive_combat" in p and "no shipped seed exercises it" in p for p in problems)
    assert any("coverage.RESERVED" in p for p in problems)  # the fix hint names the escape hatch


def test_a_reserved_capability_is_not_flagged(monkeypatch):
    """A deliberate 'built, not yet content' declaration suppresses the DARK violation."""
    monkeypatch.setitem(cov.RESERVED, "proactive_combat", "reserved for a later seed")
    dark = {**_full_map(), "proactive_combat": []}
    assert _violations(dark) == []


def test_a_stale_reserve_is_flagged(monkeypatch):
    """A RESERVED capability a pack now exercises must be caught, or the reserve list rots."""
    monkeypatch.setitem(cov.RESERVED, "quest", "was reserved")
    problems = _violations(_full_map())  # quest IS witnessed in the full map
    assert any("stale reserve" in p and "quest" in p for p in problems)
