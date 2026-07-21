"""CARD: save -- snapshot persistence for world state.

We persist STATE, never text: player location, item locations,
door lock states. Rendered text is a projection; it is not saved.
(Snapshot now; event-sourced history is a future card.)
"""

import json
from pathlib import Path

from parts import doors, items

SAVE_PATH = Path("save.json")
# Version the snapshot shape so a future change is a migration, not a crash. A file with no
# schema_version is a legacy v1 save (items were `{iid: location}` strings) and keeps loading.
# v2 records each item as `{prototype, location}`, so SPAWNED INSTANCES (parts.items.clone)
# round-trip: a v2 restore rebuilds them, where a v1 save had no instances to rebuild.
SCHEMA_VERSION = 2


def seal_snapshot(location: str, path: Path = SAVE_PATH) -> str:
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "location": location,
        "items": {
            iid: {"prototype": items.prototype_of(iid), "location": item["location"]}
            for iid, item in items.ITEMS.items()
        },
        "doors": {did: door["locked"] for did, door in doors.DOORS.items()},
    }
    path.write_text(json.dumps(snapshot, indent=2))
    return "The world holds its breath. Saved."


def _restore_items(saved: dict) -> None:
    """Apply the snapshot's item world: move seed items to their saved locations, and rebuild any
    spawned instances (clones) at their exact ids. Accepts both v2 entries (`{prototype, location}`)
    and legacy v1 entries (a bare location string). Stale clones are cleared first, so a restore is
    idempotent and never accumulates instances the snapshot did not hold."""
    items.drop_clones()
    for iid, entry in saved.items():
        prototype: object = None
        location: object = None
        if isinstance(entry, str):  # v1 legacy: location only, no prototype
            location = entry
        elif isinstance(entry, dict):
            prototype, location = entry.get("prototype"), entry.get("location")
        if not isinstance(location, str):
            continue
        if iid in items.ITEMS:
            items.ITEMS[iid]["location"] = location  # a seed item (or surviving @sg item)
        elif isinstance(prototype, str) and prototype in items.PROTOTYPES:
            items.restore_instance(iid, prototype, location)  # a persisted clone -> rebuild it
        # else: an id we cannot rebuild (v1 legacy non-seed, or an @sg item post-restart) -> skip


def awaken_snapshot(path: Path = SAVE_PATH) -> tuple[str, str]:
    """Return (location, message). Unknown ids in the file are ignored.

    Degrades honestly, never with a stack trace: a malformed file or a save written by a
    NEWER schema starts a fresh world with a plain message (the file is left untouched).
    """
    from parts.world import START_ROOM

    if not path.exists():
        return (START_ROOM, "No saved world found.")
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return (START_ROOM, "The saved world could not be read (corrupt save). Starting fresh.")
    if not isinstance(snapshot, dict):
        return (START_ROOM, "The saved world could not be read (corrupt save). Starting fresh.")
    version = snapshot.get("schema_version", 1)  # no version = a legacy v1 save; keep loading it
    if version > SCHEMA_VERSION:
        return (
            START_ROOM,
            f"The saved world is from a newer version (v{version} > v{SCHEMA_VERSION}). "
            "Starting fresh; the save file was left untouched.",
        )
    _restore_items(snapshot.get("items", {}))
    for did, locked in snapshot.get("doors", {}).items():
        if did in doors.DOORS:
            doors.DOORS[did]["locked"] = locked
    location = snapshot.get("location") or START_ROOM
    return (location, "The world stirs back to life. Loaded.")
