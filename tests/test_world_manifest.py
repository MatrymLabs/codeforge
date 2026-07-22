"""Test twin for parts/world_manifest.py -- the typed World Package identity.

Acceptance (a valid mapping builds a manifest; a real seed's world.yaml loads; a manifest-less
seed is derived, not missing) AND refusal (a bad id / missing title / missing start_room / a
str-not-list authors fails loud). check_world's reconciliation is pinned by monkeypatching the
real spawn, so no fixture rooms.yaml is needed.
"""

from __future__ import annotations

import pytest

from parts import world_manifest as wm
from parts.stat_rules import DEFAULT_RULESET, RulesetError, apply_ruleset
from parts.world_manifest import (
    WorldManifestError,
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


def test_a_manifestless_seed_is_derived_not_missing() -> None:
    m = describe_world("spiral-ascent")  # ships no world.yaml
    assert not m.declared  # derived, but still a typed identity
    assert m.title == "Spiral Ascent"  # de-slugged from the id
    assert m.start_room  # read from the seed's rooms.yaml


def _seed_with_world(tmp_path, start_room: str) -> None:
    seed = tmp_path / "seeds" / "demo-world"
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
    (tmp_path / "seeds" / "bare").mkdir(
        parents=True
    )  # no world.yaml -> derived, nothing to reconcile
    assert check_world("bare", root=tmp_path) == []


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
