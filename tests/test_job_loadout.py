"""Test twin for the rich job loadout schema in parts/seed.load_jobs.

Acceptance: the shipped Engineer carries its full loadout; a simple calling defaults to empty
loadout fields (the new fields are optional). Refusal: a malformed loadout (a non-string in a
list field, a wrong-typed ability slot) fails loud at load.
"""

from __future__ import annotations

import pytest

from parts.jobs import JOBS
from parts.seed import SeedError, load_jobs


def test_the_shipped_engineer_carries_its_full_loadout() -> None:
    engineer = JOBS["engineer"]
    assert engineer["name"] == "Engineer"
    assert set(engineer["stats"]) == {"strength", "speed", "magic", "stamina", "wisdom", "luck"}
    assert "support" in engineer["role_tags"]
    assert engineer["automatic_attack"] == "Calibrated Strike"
    assert "Field Repair" in engineer["abilities"]
    assert engineer["counter"] == "Emergency Repair"
    assert engineer["movement"] == "Field Deployment"
    assert engineer["inherent"] == "Systems Thinking"
    assert engineer["signature"] == "Forge Overdrive"


def test_a_simple_calling_defaults_to_an_empty_loadout(tmp_path) -> None:
    path = tmp_path / "jobs.yaml"
    path.write_text("squire:\n  name: Squire\n  stats: {strength: 10}\n")
    squire = load_jobs(path)["squire"]
    assert squire["role_tags"] == [] and squire["abilities"] == []
    assert squire["counter"] == "" and squire["signature"] == ""
    # defaults still fill the six attributes
    assert set(squire["stats"]) == {"strength", "speed", "magic", "stamina", "wisdom", "luck"}


def test_a_non_string_ability_is_rejected_at_load(tmp_path) -> None:
    path = tmp_path / "jobs.yaml"
    path.write_text("golem:\n  name: Golem\n  abilities: [Smash, 42]\n")
    with pytest.raises(SeedError, match="abilities entry must be a string"):
        load_jobs(path)


def test_a_wrong_typed_ability_slot_is_rejected_at_load(tmp_path) -> None:
    path = tmp_path / "jobs.yaml"
    path.write_text("golem:\n  name: Golem\n  counter: [not, a, string]\n")
    with pytest.raises(SeedError):
        load_jobs(path)
