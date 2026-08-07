"""Engine-tick proof for packet-declared Aethryn state mutations."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_structured_action_outcome_can_consume_a_declared_item(tmp_path: Path, monkeypatch) -> None:
    from kernel.world import aethryn_actions, items
    from kernel.world.aethryn_state import WorldStateStore
    from kernel.world.session import Session

    player_id = "structured_action_hero"
    item_id = "structured_action_tool"
    monkeypatch.setitem(
        items.ITEMS,
        item_id,
        {
            "name": "a test action tool",
            "keywords": ["tool"],
            "location": items.carrier(player_id),
            "slot": "",
            "mods": {},
        },
    )
    schema = {
        "test.state": {
            "room_id": "test_room",
            "initial_value": "idle",
            "reversible_values": ["idle", "done"],
            "actions": [
                {
                    "command": "maintain",
                    "target": "test",
                    "required_item": "structured_action_tool",
                    "consume_item": True,
                    "from": "idle",
                    "to": "done",
                }
            ],
        }
    }
    store = WorldStateStore(tmp_path / "world-state.json", schema)
    session = Session(player_id=player_id, location="test_room", named=True)

    outcome = aethryn_actions.apply_declared_action_result(session, "maintain", "test", store)

    assert outcome.status == "changed"
    assert outcome.previous_value == "idle"
    assert outcome.new_value == "done"
    assert outcome.consumed_item == item_id
    assert item_id not in items.ITEMS


def test_brightwater_maintain_action_requires_token_persists_and_projects(tmp_path: Path) -> None:
    script = r"""
import json
from forge import handle_command
from kernel.world.session import SESSIONS, Session

s = Session(player_id="brightwater_action_hero", location="brightwater_sluice", named=True)
SESSIONS[s.player_id] = s

missing = handle_command(s, "maintain sluice")
assert "need brightwater sluice token" in missing.lower(), missing

taken = handle_command(s, "take sluice-token")
assert "sluice-token" in taken.lower(), taken

changed = handle_command(s, "maintain sluice")
assert "settle quiet" in changed.lower(), changed

again = handle_command(s, "maintain sluice")
assert "already quiet" in again.lower(), again

look = handle_command(s, "look")
assert "flow-gates remain quiet" in look.lower(), look
print("AETHRYN_MAINTAIN_OK")
"""
    env = {
        **os.environ,
        "FORGE_SEED": "aethryn",
        "AETHRYN_STATE_PATH": str(tmp_path / "world-state.json"),
        "CODEFORGE_DB": str(tmp_path / "action.db"),
        "PYTHONPATH": str(ROOT),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, f"mutation tick failed:\n{result.stdout}\n{result.stderr}"
    assert "AETHRYN_MAINTAIN_OK" in result.stdout
    persisted = json.loads((tmp_path / "world-state.json").read_text(encoding="utf-8"))
    assert persisted["brightwater.sluice_status"] == "quiet"


def test_greenhold_cistern_repair_follows_authored_key_route_and_updates_pressure(
    tmp_path: Path,
) -> None:
    script = r"""
from forge import handle_command
from kernel.world.session import SESSIONS, Session

s = Session(player_id="greenhold_action_hero", location="greenhold_undercroft", named=True)
SESSIONS[s.player_id] = s
for command in ("up", "south", "out", "south", "east"):
    handle_command(s, command)

missing = handle_command(s, "maintain cistern")
assert "need greenhold valve key" in missing.lower(), missing

for command in (
    "west",
    "north",
    "square",
    "north",
    "down",
    "take valve-key",
    "up",
    "south",
    "out",
    "south",
    "east",
):
    handle_command(s, command)

changed = handle_command(s, "maintain cistern")
assert "answers with a clear rising flow" in changed.lower(), changed

again = handle_command(s, "maintain cistern")
assert "already flowing" in again.lower(), again

look = handle_command(s, "look")
assert "public channel runs clear" in look.lower(), look
assert "water shortage" not in look.lower(), look
print("AETHRYN_CISTERN_OK")
"""
    env = {
        **os.environ,
        "FORGE_SEED": "aethryn",
        "AETHRYN_STATE_PATH": str(tmp_path / "world-state.json"),
        "CODEFORGE_DB": str(tmp_path / "action.db"),
        "PYTHONPATH": str(ROOT),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, f"cistern tick failed:\n{result.stdout}\n{result.stderr}"
    assert "AETHRYN_CISTERN_OK" in result.stdout
    persisted = json.loads((tmp_path / "world-state.json").read_text(encoding="utf-8"))
    assert persisted["greenhold.cistern_status"] == "flowing"


def test_duskwood_lantern_relight_uses_salver_persists_and_clears_shortage(
    tmp_path: Path,
) -> None:
    script = r"""
from forge import handle_command
from kernel.world.session import SESSIONS, Session

s = Session(player_id="duskwood_action_hero", location="ravenwatch", named=True)
SESSIONS[s.player_id] = s

for command in ("out", "black", "threshold", "east"):
    handle_command(s, command)

missing = handle_command(s, "maintain lantern")
assert "need duskwood lantern salver" in missing.lower(), missing

for command in (
    "west",
    "in",
    "out",
    "ravenwatch",
):
    handle_command(s, command)

taken = handle_command(s, "take lantern-salve")
assert "lantern salve" in taken.lower(), taken

for command in ("out", "black", "threshold", "east"):
    handle_command(s, command)

changed = handle_command(s, "maintain lantern")
assert "catches along the return markers" in changed.lower(), changed

again = handle_command(s, "maintain lantern")
assert "already lit" in again.lower(), again

look = handle_command(s, "look")
assert "lantern burns lit" in look.lower(), look
assert "lantern shortage" not in look.lower(), look
print("AETHRYN_LANTERN_OK")
"""
    env = {
        **os.environ,
        "FORGE_SEED": "aethryn",
        "AETHRYN_STATE_PATH": str(tmp_path / "world-state.json"),
        "CODEFORGE_DB": str(tmp_path / "action.db"),
        "PYTHONPATH": str(ROOT),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, f"lantern tick failed:\n{result.stdout}\n{result.stderr}"
    assert "AETHRYN_LANTERN_OK" in result.stdout
    persisted = json.loads((tmp_path / "world-state.json").read_text(encoding="utf-8"))
    assert persisted["duskwood.hollow_lantern"] == "lit"
