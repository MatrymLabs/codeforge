"""CARD: save -- snapshot persistence for world state.

We persist STATE, never text: player location, item locations,
door lock states. Rendered text is a projection; it is not saved.
(Snapshot now; event-sourced history is a future card.)
"""

import json
from pathlib import Path

from parts import doors, items

SAVE_PATH = Path("save.json")


def seal_snapshot(location: str, path: Path = SAVE_PATH) -> str:
    snapshot = {
        "location": location,
        "items": {iid: item["location"] for iid, item in items.ITEMS.items()},
        "doors": {did: door["locked"] for did, door in doors.DOORS.items()},
    }
    path.write_text(json.dumps(snapshot, indent=2))
    return "The world holds its breath. Saved."


def awaken_snapshot(path: Path = SAVE_PATH) -> tuple[str, str]:
    """Return (location, message). Unknown ids in the file are ignored."""
    if not path.exists():
        from parts.world import START_ROOM

        return (START_ROOM, "No saved world found.")
    snapshot = json.loads(path.read_text())
    for iid, loc in snapshot["items"].items():
        if iid in items.ITEMS:
            items.ITEMS[iid]["location"] = loc
    for did, locked in snapshot["doors"].items():
        if did in doors.DOORS:
            doors.DOORS[did]["locked"] = locked
    return (snapshot["location"], "The world stirs back to life. Loaded.")
