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
# schema_version is a legacy v1 save (the shape below IS v1) and keeps loading.
SCHEMA_VERSION = 1


def seal_snapshot(location: str, path: Path = SAVE_PATH) -> str:
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "location": location,
        "items": {iid: item["location"] for iid, item in items.ITEMS.items()},
        "doors": {did: door["locked"] for did, door in doors.DOORS.items()},
    }
    path.write_text(json.dumps(snapshot, indent=2))
    return "The world holds its breath. Saved."


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
    for iid, loc in snapshot.get("items", {}).items():
        if iid in items.ITEMS:
            items.ITEMS[iid]["location"] = loc
    for did, locked in snapshot.get("doors", {}).items():
        if did in doors.DOORS:
            doors.DOORS[did]["locked"] = locked
    location = snapshot.get("location") or START_ROOM
    return (location, "The world stirs back to life. Loaded.")
