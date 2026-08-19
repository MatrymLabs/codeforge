#!/usr/bin/env python3
"""Prove a poured Target Product persists, restarts, and survives recovery.

This file is copied into a cast by ``kernel.cast.generate_cast``. Every stage runs in a fresh
interpreter rooted at the product directory, so the engine repository that poured the product is
not a participant in the proof.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PROBE = "cast-selfproof"
MARKER_NAME = "cast_selfproof.json"
DB_NAME = "codeforge.db"
REFUSED = "REFUSED"
CHILD_ARGUMENT_COUNT = 3
CHILD_STAGE_INDEX = 2
CHILD_PAYLOAD_INDEX = 3

PLANTED: dict[str, object] = {
    "level": 7,
    "xp": 1234,
    "coins": 99,
    "rank": "player",
    "account": "cast-selfproof-account",
}


class ProofRefusedError(RuntimeError):
    """A required detached-proof precondition is absent or has been falsified."""


def product_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _foreign_engine_paths(root: Path) -> list[Path]:
    """Find import roots that expose a second CodeForge engine outside this product."""
    found: list[Path] = []
    for entry in sys.path:
        candidate = Path(entry or Path.cwd()).resolve()
        if _within(candidate, root):
            continue
        if (candidate / "kernel" / "world" / "db.py").is_file():
            found.append(candidate)
    return found


def _prepare_imports() -> Path:
    root = product_root()
    foreign = _foreign_engine_paths(root)
    if foreign:
        rendered = ", ".join(str(path) for path in foreign)
        raise ProofRefusedError(f"engine repository remains on sys.path: {rendered}")
    sys.path.insert(0, str(root))
    return root


def _assert_product_module(module: Any, root: Path) -> None:
    origin = getattr(module, "__file__", None)
    if not origin or not _within(Path(origin), root):
        raise ProofRefusedError(
            f"module {getattr(module, '__name__', '?')} came from outside product"
        )


def _expected() -> dict[str, object]:
    _prepare_imports()
    import kernel
    from kernel.world.jobs import JOBS
    from kernel.world.world import WORLD

    _assert_product_module(kernel, product_root())
    expected = dict(PLANTED)
    expected["job"] = min(JOBS) if JOBS else ""
    locations = sorted(room for room in WORLD if room != "forge")
    expected["location"] = locations[0] if locations else "forge"
    return expected


def _compare(casefile: dict[str, Any] | None, expected: dict[str, object]) -> list[str]:
    if casefile is None:
        return ["character absent from the product database"]
    mismatches = []
    for field, wanted in expected.items():
        if casefile.get(field) != wanted:
            mismatches.append(f"{field}: expected {wanted!r}, got {casefile.get(field)!r}")
    return mismatches


def _stage_persist() -> dict[str, object]:
    root = _prepare_imports()
    from kernel.world import characters
    from kernel.world.session import Session

    _assert_product_module(characters, root)
    expected = _expected()
    session = Session(player_id=PROBE, location=str(expected["location"]))
    session.named = True
    for field, value in expected.items():
        if hasattr(session, field):
            setattr(session, field, value)
    characters.save_character(session)
    return {"saved": True, "expected": expected}


def _stage_restart(expected: dict[str, object]) -> dict[str, object]:
    root = _prepare_imports()
    from kernel.world import characters

    _assert_product_module(characters, root)
    casefile = characters.load_character(PROBE)
    return {"mismatches": _compare(casefile, expected), "found": casefile is not None}


def _stage_survive(expected: dict[str, object]) -> dict[str, object]:
    root = _prepare_imports()
    from kernel.world.characters import load_character
    from kernel.world.db import DB_PATH, backup_db, restore_db

    live = Path(DB_PATH)
    backup = backup_db(root / "backups")
    live.unlink()
    deleted = not live.exists()
    restore_db(backup, live)
    casefile = load_character(PROBE)
    return {
        "deleted": deleted,
        "restored": live.exists(),
        "mismatches": _compare(casefile, expected),
    }


def _child(stage: str) -> int:
    try:
        expected = (
            json.loads(sys.argv[CHILD_PAYLOAD_INDEX]) if len(sys.argv) > CHILD_PAYLOAD_INDEX else {}
        )
        if stage == "persist":
            result = _stage_persist()
        elif stage == "restart":
            result = _stage_restart(expected)
        elif stage == "survive":
            result = _stage_survive(expected)
        else:
            result = {"error": f"unknown proof stage: {stage}"}
    except Exception as exc:  # noqa: BLE001
        # The parent renders this as a refusal, never a traceback.
        result = {"error": f"{type(exc).__name__}: {exc}"}
    print("---CAST_SELFPROOF_JSON---")
    print(json.dumps(result, sort_keys=True))
    return 0


def _spawn(root: Path, stage: str, expected: dict[str, object]) -> dict[str, Any]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["CODEFORGE_DB"] = str(root / DB_NAME)
    env["PYTHONNOUSERSITE"] = "1"
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(Path(__file__)), "--child", stage, json.dumps(expected)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    marker = "---CAST_SELFPROOF_JSON---"
    if marker not in proc.stdout:
        return {"error": f"stage produced no verdict (exit {proc.returncode})"}
    try:
        return json.loads(proc.stdout.split(marker, 1)[1].strip())
    except json.JSONDecodeError as exc:
        return {"error": f"invalid stage verdict: {exc}"}


def _refusal(message: str) -> int:
    print(f"{REFUSED}: {message}")
    return 1


def main() -> int:  # noqa: PLR0911
    root = product_root()
    marker = root / MARKER_NAME
    database = root / DB_NAME

    try:
        foreign = _foreign_engine_paths(root)
        if foreign:
            return _refusal(f"engine repository remains on sys.path: {foreign[0]}")

        # THE PERSIST STAGE ALWAYS RUNS. It used to be skipped whenever a marker from a previous
        # run existed, reading `expected` out of that file and jumping straight to restart.
        #
        # That turned the proof into a different, easier question. On a product that had ever
        # succeeded once, `save_character` was never called again, so a product whose persistence
        # was completely broken still reported:
        #
        #     [PASS] restart    a fresh product interpreter restored the persisted fields
        #     VERDICT: PASS
        #
        # Measured 2026-08-19 by renaming `save_character` out of the poured engine. A VIRGIN pour
        # refused correctly with the AttributeError; the same sabotage on a pour that had run once
        # before passed, because the marker skipped the only stage that would have touched the
        # missing function. The gate was answering "does the old database still match the old
        # marker", which is not what it printed.
        #
        # The marker is now written as EVIDENCE and never read as a reason to skip. A proof that
        # can be satisfied by residue from an earlier run is not a proof of persistence.
        #
        # The marker is still READ for one thing, and that check was already here and is kept: a
        # marker whose database has vanished means the product LOST state between runs, which is
        # the failure this proof exists to detect. It is checked BEFORE persisting, because
        # persisting would recreate the database and destroy the evidence. Always-run persist and
        # this pre-check answer different questions, and both are worth asking.
        if marker.exists():
            if not database.exists():
                return _refusal(f"persisted database is missing: {database.name}")
            # And if the database is still there, it must still AGREE with the marker. Checked
            # here, before persisting, because persisting would overwrite the very corruption
            # this is looking for. A product whose stored state drifted between runs is a finding
            # even though the run about to happen would have papered over it.
            prior = json.loads(marker.read_text(encoding="utf-8"))
            drifted = _spawn(root, "restart", prior)
            prior_mismatches = drifted.get("mismatches") or []
            if drifted.get("error") or prior_mismatches:
                detail = drifted.get("error") or "; ".join(prior_mismatches)
                return _refusal(f"persisted field mismatch: {detail}")

        persisted = _spawn(root, "persist", {})
        if not persisted.get("saved"):
            return _refusal(str(persisted.get("error") or "persist stage did not save"))
        expected = dict(persisted["expected"])
        marker.write_text(json.dumps(expected, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if not database.exists():
            return _refusal(f"persist reported success but no database exists: {database.name}")
        print(f"  [PASS] persist    {PROBE} written to the product database")

        restarted = _spawn(root, "restart", expected)
        mismatches = restarted.get("mismatches") or []
        if restarted.get("error") or mismatches:
            detail = restarted.get("error") or "; ".join(mismatches)
            return _refusal(f"persisted field mismatch after restart: {detail}")
        print("  [PASS] restart    a fresh product interpreter restored the persisted fields")

        survived = _spawn(root, "survive", expected)
        mismatches = survived.get("mismatches") or []
        if (
            survived.get("error")
            or not survived.get("deleted")
            or not survived.get("restored")
            or mismatches
        ):
            detail = (
                survived.get("error") or "; ".join(mismatches) or "database recovery was incomplete"
            )
            return _refusal(f"survive stage failed: {detail}")
        print("  [PASS] survive    database deleted, restored, and fields remained intact")
        print("VERDICT: PASS")
        return 0  # noqa: TRY300
    except (OSError, ValueError, ProofRefusedError) as exc:
        return _refusal(str(exc))


if __name__ == "__main__":
    if len(sys.argv) > CHILD_ARGUMENT_COUNT - 1 and sys.argv[1] == "--child":
        raise SystemExit(_child(sys.argv[CHILD_STAGE_INDEX]))
    raise SystemExit(main())
