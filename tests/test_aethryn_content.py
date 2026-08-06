from pathlib import Path

import pytest

from kernel.seedlab.aethryn_content import AethrynContentError, AethrynItemLifecycle
from kernel.world import creator_workshop as workshop
from kernel.world import workshop_state
from kernel.world.items import ITEMS
from kernel.world.seed import SEEDS_ROOT, inspect_world_links, load_items, load_npcs, load_rooms
from kernel.world.world import WORLD


def test_item_lifecycle_draft_validate_simulate_publish_observe_and_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEFORGE_WORKSHOP_STATE", str(tmp_path / "workshop.json"))
    room = next(iter(WORLD))
    label = "lifecycle_lantern"
    ITEMS.pop(label, None)
    workshop.clear_published_state()
    service = AethrynItemLifecycle(tmp_path / "lifecycle")

    created = service.create(
        "content-lantern",
        "draft-lantern",
        "aethryn",
        "owner",
        {"kind": "item", "name": "Lifecycle Lantern", "label": label, "room": room},
    )
    assert created.status == "created"
    validated = service.validate("content-lantern", "owner")
    assert validated.status == "validated" and validated.validation["status"] == "passed"
    simulated = service.simulate("content-lantern", "owner")
    assert simulated.status == "simulated"
    assert simulated.simulation["mutated_live_state"] is False
    assert label not in ITEMS
    reviewed = service.submit_review("content-lantern", "owner")
    approved = service.approve("content-lantern", "reviewer")
    assert reviewed.status == "review" and approved.status == "approved"

    published = service.publish("content-lantern", "reviewer")
    assert published.status == "published"
    assert ITEMS[label]["name"] == "Lifecycle Lantern"
    recovered = AethrynItemLifecycle(tmp_path / "lifecycle").get("content-lantern")
    assert recovered.status == "published"

    observed = service.observe("content-lantern", "observer")
    rolled_back = service.rollback("content-lantern", "operator")
    assert observed.status == "observed" and observed.observation["live"] is True
    assert rolled_back.status == "rolled_back"
    assert label not in ITEMS
    assert workshop_state.load_changes("aethryn") == []


def test_item_lifecycle_refuses_bad_canon_before_simulation_or_publication(tmp_path: Path) -> None:
    service = AethrynItemLifecycle(tmp_path / "lifecycle")
    service.create(
        "content-bad",
        "draft-bad",
        "aethryn",
        "owner",
        {"kind": "item", "name": "Bad", "label": "bad", "room": "not-a-room"},
    )
    with pytest.raises(AethrynContentError, match="canon validation"):
        service.validate("content-bad", "owner")


def test_authored_sunken_barrow_guardian_links_to_authored_drop() -> None:
    """The opening dungeon's real authored boss must link to a real drop prototype.

    The live gateway journey uses the authored level-2 scout for its equipment proof; the guardian
    assertion keeps the opening dungeon's boss reward link covered by the same loader contract.
    """
    root = SEEDS_ROOT / "aethryn"
    rooms = load_rooms(root / "rooms.yaml")
    items = load_items(root / "items.yaml")
    npcs = load_npcs(root / "npcs.yaml")

    inspect_world_links(rooms, items, npcs)
    assert npcs["the_sunken_barrow_guardian"]["location"] == "the_sunken_barrow"
    assert npcs["the_sunken_barrow_guardian"]["drops"] == ["greater_healing_draught"]
    assert items["greater_healing_draught"]["location"] == "nowhere"
    assert npcs["the_sunken_barrow_scout"]["drops"] == ["cinder_hammer"]
    assert items["cinder_hammer"]["location"] == "nowhere"
