"""Test twin for parts/world_manifest.py -- the typed World Package identity.

Acceptance (a valid mapping builds a manifest; a real seed's world.yaml loads; a manifest-less
seed is derived, not missing) AND refusal (a bad id / missing title / missing start_room / a
str-not-list authors fails loud). check_world's reconciliation is pinned by monkeypatching the
real spawn, so no fixture rooms.yaml is needed.
"""

from __future__ import annotations

import pytest

from parts import world_manifest as wm
from parts.world_manifest import (
    WorldManifestError,
    check_world,
    describe_world,
    from_dict,
    to_dict,
    to_markdown,
)

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
