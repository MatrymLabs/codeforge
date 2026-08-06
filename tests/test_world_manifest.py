"""Test twin for kernel/world/world_manifest.py -- the typed World Package identity.

Acceptance (a valid mapping builds a manifest; real Seed world.yaml files load; a manifest-less
seed is derived, not missing) AND refusal (a bad id / missing title / missing start_room / a
str-not-list authors fails loud). check_world's reconciliation is pinned by monkeypatching the
real spawn; audit_worlds is pinned over real fixture seeds AND asserts every committed World
Package reconciles clean (the standing "fail loud in CI, not at a player's spawn" guarantee).
"""

from __future__ import annotations

import pytest

from kernel.world import world_manifest as wm
from kernel.world.stat_rules import DEFAULT_RULESET, RulesetError, apply_ruleset
from kernel.world.world_manifest import (
    WorldManifestError,
    audit_worlds,
    check_world,
    describe_world,
    from_dict,
    load_ruleset,
    to_dict,
    to_markdown,
)

_A_RULES_BLOCK = """
rules:
  ATK: {base: 50, level: false, terms: [{coeff: 5.0, attributes: [strength]}]}
  DEF: {base: 0, level: false, terms: [{coeff: 1.0, attributes: [stamina]}]}
  EVA: {base: 0, level: false, terms: [{coeff: 1.0, attributes: [speed]}]}
  MAG DEF: {base: 0, level: false, terms: [{coeff: 1.0, attributes: [wisdom]}]}
  ACC: {base: 90, level: false, terms: [{coeff: 1.0, attributes: [luck]}]}
"""
_TEN_ATTRS = dict.fromkeys(("strength", "speed", "magic", "stamina", "wisdom", "luck"), 10)

_VALID = {
    "world_id": "first-forge",
    "title": "The First Forge",
    "start_room": "forge",
    "version": "1",
    "description": "a world",
    "authors": ["MatrymLabs"],
    "tags": ["starter"],
}


def test_a_valid_mapping_builds_a_manifest() -> None:
    m = from_dict(_VALID)
    assert m.world_id == "first-forge" and m.start_room == "forge" and m.declared


@pytest.mark.parametrize(
    "bad, match",
    [
        ({**_VALID, "world_id": "First_Forge"}, "world_id"),  # uppercase + underscore
        ({**_VALID, "world_id": ""}, "world_id"),
        ({k: v for k, v in _VALID.items() if k != "title"}, "title"),
        ({k: v for k, v in _VALID.items() if k != "start_room"}, "start_room"),
        ({**_VALID, "authors": "solo"}, "authors"),  # a str, not a list of strings
    ],
)
def test_a_malformed_manifest_fails_loud(bad: dict, match: str) -> None:
    with pytest.raises(WorldManifestError, match=match):
        from_dict(bad)


def test_a_non_mapping_fails_loud() -> None:
    with pytest.raises(WorldManifestError, match="mapping"):
        from_dict(["not", "a", "dict"])


def test_to_dict_round_trips() -> None:
    m = from_dict(_VALID)
    assert from_dict(to_dict(m)) == m


def test_to_markdown_shows_the_identity() -> None:
    md = to_markdown(from_dict(_VALID))
    assert "The First Forge" in md and "forge" in md and "declared" in md


def test_the_flagship_seed_has_a_declared_manifest() -> None:
    m = describe_world("first-forge")
    assert m.declared and m.start_room == "forge" and m.title.startswith("CodeForge")


def test_a_second_seed_loads_its_declared_manifest() -> None:
    m = describe_world("spiral-ascent")
    assert m.declared and m.title == "The Spiral Ascent"
    assert m.start_room  # read from the seed's rooms.yaml


def _seed_with_world(tmp_path, start_room: str) -> None:
    seed = tmp_path / "content" / "seeds" / "demo-world"
    seed.mkdir(parents=True)
    (seed / "world.yaml").write_text(
        f"world_id: demo-world\ntitle: Demo\nstart_room: {start_room}\n"
    )


def test_check_world_flags_a_stale_declared_spawn(tmp_path, monkeypatch) -> None:
    _seed_with_world(tmp_path, "alpha")
    monkeypatch.setattr(wm, "_first_room", lambda _d: "beta")  # the real spawn disagrees
    gaps = check_world("demo-world", root=tmp_path)
    assert len(gaps) == 1 and "alpha" in gaps[0] and "beta" in gaps[0]


def test_check_world_is_clean_when_the_spawn_matches(tmp_path, monkeypatch) -> None:
    _seed_with_world(tmp_path, "alpha")
    monkeypatch.setattr(wm, "_first_room", lambda _d: "alpha")
    assert check_world("demo-world", root=tmp_path) == []


def test_check_world_skips_a_derived_manifest(tmp_path) -> None:
    (tmp_path / "content" / "seeds" / "bare").mkdir(
        parents=True
    )  # no world.yaml -> derived, nothing to reconcile
    assert check_world("bare", root=tmp_path) == []


# --- audit_worlds: every installed World Package boots with a consistent identity (fail loud in
# CI, not at a player's spawn) --------------------------------------------------------------------


def _installed_seed(tmp_path, name: str, rooms: str, world: str = "") -> None:
    seed = tmp_path / "content" / "seeds" / name
    seed.mkdir(parents=True)
    (seed / "rooms.yaml").write_text(rooms)
    if world:
        (seed / "world.yaml").write_text(world)


def test_every_shipped_world_is_hostable() -> None:
    # The standing guarantee: every committed seed reconciles clean through the engine's own gates.
    report = audit_worlds()
    assert report  # at least the flagship seeds are installed
    broken = {name: problems for name, problems in report.items() if problems}
    assert broken == {}, f"shipped worlds with a broken identity: {broken}"


def test_audit_worlds_flags_a_stale_declared_spawn(tmp_path) -> None:
    # world.yaml declares 'summit', but the seed's first room is 'trailhead' -> flagged.
    _installed_seed(
        tmp_path,
        "demo",
        "trailhead:\nsummit:\n",
        "world_id: demo\ntitle: Demo\nstart_room: summit\n",
    )
    report = audit_worlds(root=tmp_path)
    assert len(report["demo"]) == 1 and "summit" in report["demo"][0]


def test_audit_worlds_flags_an_invalid_manifest(tmp_path) -> None:
    _installed_seed(
        tmp_path, "demo", "trailhead:\n", "world_id: Bad_ID\ntitle: Demo\nstart_room: trailhead\n"
    )
    report = audit_worlds(root=tmp_path)
    assert report["demo"] and "invalid manifest" in report["demo"][0]


def test_audit_worlds_passes_a_clean_declared_and_a_derived_seed(tmp_path) -> None:
    _installed_seed(
        tmp_path,
        "declared",
        "trailhead:\nsummit:\n",
        "world_id: declared\ntitle: Declared\nstart_room: trailhead\n",
    )
    _installed_seed(
        tmp_path, "derived", "gate:\n"
    )  # no world.yaml -> derived, nothing to reconcile
    report = audit_worlds(root=tmp_path)
    assert report == {"declared": [], "derived": []}


def test_audit_worlds_ignores_a_directory_without_rooms(tmp_path) -> None:
    (tmp_path / "content" / "seeds" / "not_a_seed").mkdir(parents=True)  # no rooms.yaml
    _installed_seed(tmp_path, "real", "gate:\n")
    report = audit_worlds(root=tmp_path)
    assert "not_a_seed" not in report and "real" in report


def test_audit_worlds_is_empty_without_a_seeds_root(tmp_path) -> None:
    assert audit_worlds(root=tmp_path) == {}  # no content/seeds/ at all -> nothing to audit


# --- load_ruleset: a world declares its combat balance (wires #292 + #293) --------------
def _seed_dir(tmp_path, name: str, body: str):
    seed = tmp_path / name
    seed.mkdir()
    (seed / "world.yaml").write_text(body)
    return seed


def test_load_ruleset_reads_a_declared_rules_block(tmp_path) -> None:
    seed = _seed_dir(
        tmp_path, "brawler", "world_id: brawler\ntitle: B\nstart_room: pit\n" + _A_RULES_BLOCK
    )
    ruleset = load_ruleset(seed)
    assert apply_ruleset(ruleset, _TEN_ATTRS, 5)["ATK"] == 100  # base 50 + strength(10) * 5


def test_load_ruleset_defaults_without_a_world_yaml(tmp_path) -> None:
    (tmp_path / "bare").mkdir()
    assert load_ruleset(tmp_path / "bare") == DEFAULT_RULESET


def test_load_ruleset_defaults_without_a_rules_block(tmp_path) -> None:
    seed = _seed_dir(tmp_path, "plain", "world_id: plain\ntitle: P\nstart_room: r\n")
    assert load_ruleset(seed) == DEFAULT_RULESET  # a world.yaml with no rules -> default balance


def test_load_ruleset_fails_loud_on_a_malformed_block(tmp_path) -> None:
    # a rules block that omits stats is a broken balance -- refused loud, not silently defaulted
    body = (
        "world_id: broken\ntitle: B\nstart_room: r\n"
        "rules:\n  ATK: {base: 0, level: false, terms: [{coeff: 1.0, attributes: [strength]}]}\n"
    )
    seed = _seed_dir(tmp_path, "broken", body)
    with pytest.raises(RulesetError):
        load_ruleset(seed)
