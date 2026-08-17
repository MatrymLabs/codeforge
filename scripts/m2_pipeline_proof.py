#!/usr/bin/env python3
"""M2 pipeline proof: drive an emitted Target Product produce -> persist -> restart -> survive.

The Workshop has had every leg of this pipeline for a while (`cast-plan`, `cast`, `shelf-pour`,
`backup`, `restore`) and has never run them as ONE chain against ONE artifact. Each leg had its own
test twin; the seam BETWEEN the legs had nothing. This closes that: a cast is poured, a hero is
persisted into the poured product's own database, the interpreter DIES, a second interpreter reads
the hero back, and then the database is destroyed outright and restored from a backup.

Four stages, each in its own subprocess, because a "restart" that reuses the parent interpreter
proves nothing about persistence -- it only proves the object is still in memory.

  1. ISOLATION   the poured product imports its OWN engine, not the checkout that poured it
  2. PERSIST     a hero is written to the product's database and the facts are recorded
  3. RESTART     a FRESH interpreter reads that hero back and the facts still match
  4. SURVIVE     the database is deleted outright, restored from backup, and the hero is still there

Every stage returns JSON on stdout, so the parent compares real values instead of trusting prose.

`--sabotage <stage>` breaks one stage on purpose. A gate is trusted only when it has been shown to
fail for the bad state it claims to catch (canon section 13), so the sabotage mode is part of the
instrument, not a debugging leftover.

Usage:
    python scripts/m2_pipeline_proof.py --target <poured-product-dir>
    python scripts/m2_pipeline_proof.py --target <dir> --sabotage restart
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# The hero the proof drives. Deliberately not a name any seed ships, so a collision with real
# content is visible as a collision rather than silently passing on somebody else's record.
PROBE = "m2probe"

# The facts written in PERSIST and demanded back in RESTART. A restart that returns a hero with the
# right NAME and the wrong everything-else is the failure this is built to catch, so the comparison
# covers the whole sheet, never just identity.
#
# `job` is deliberately NOT here: it is chosen from the Blueprint under test at run time. The first
# draft hardcoded "smith" and the proof reported a defect that was not one -- `restore_character`
# refuses a calling absent from the current Blueprint and restores a jobless sheet on purpose
# ("seeds are games"). A cast proof that hardcodes world content is measuring the seed pack it was
# written against, not the pipeline, and every other Blueprint would fail it for being itself.
PLANTED = {
    "level": 7,
    "xp": 1234,
    "coins": 99,
    "rank": "player",
    "account": "m2proof",
}

PASS, FAIL = "PASS", "FAIL"


# --- the stage bodies, each executed in a FRESH interpreter with cwd = the target ---------------


def _bootstrap() -> None:
    """Put the target (cwd) at the FRONT of the import path.

    A script's sys.path[0] is the SCRIPT's directory, never the working directory, so without this
    a child launched with cwd=<target> would still import the engine that poured the product. The
    insert is what makes ISOLATION a real question rather than a foregone one.
    """
    sys.path.insert(0, os.getcwd())  # noqa: PTH109


def _planted_in(expected: dict[str, object]) -> dict[str, object]:
    """The facts PERSIST recorded, narrowed back out of the JSON handshake.

    An empty dict means the comparison loop below finds nothing to compare, which would pass
    vacuously, so callers must have already checked that PERSIST reported a write.
    """
    planted = expected.get("planted")
    return dict(planted) if isinstance(planted, dict) else {}


def stage_isolation(sabotage: bool) -> dict[str, object]:
    _bootstrap()
    if sabotage:
        # Put the ENGINE that poured this product AHEAD of the product itself (so, after the
        # bootstrap, not before it). If the stage still reports PASS it is not measuring isolation.
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import kernel
    import kernel.world.characters as chars

    target = Path.cwd().resolve()
    engine_of = Path(kernel.__file__).resolve().parent.parent
    return {
        "kernel_resolved_to": str(engine_of),
        "target": str(target),
        "imported_from_target": engine_of == target,
        "characters_module": str(Path(chars.__file__).resolve()),
    }


def stage_persist(sabotage: bool) -> dict[str, object]:
    _bootstrap()
    from kernel.world.characters import save_character
    from kernel.world.jobs import JOBS
    from kernel.world.session import Session
    from kernel.world.world import WORLD

    session = Session(player_id=PROBE)
    session.named = True
    planted = dict(PLANTED)
    for field, value in planted.items():
        setattr(session, field, value)

    # Take a calling THIS Blueprint actually ships. Sorted for determinism, so a rerun on the same
    # Blueprint plants the same hero and a divergence means the pipeline moved, not the probe.
    if JOBS:
        calling = sorted(JOBS)[0]  # noqa: FURB192
        planted["job"] = calling
        session.job = calling

    # Move the hero off the spawn room, so "survived" cannot be satisfied by a default. If the
    # world has only one room the spawn is the only honest answer and the proof says so.
    rooms = [r for r in WORLD if r != session.location]
    if rooms:
        session.location = sorted(rooms)[0]  # noqa: FURB192

    if sabotage:
        # Write nothing. Everything downstream reads an empty store, which is the whole point:
        # if the chain still passes, it was never reading what this stage wrote.
        return {"saved": False, "planted": planted, "location": session.location}

    save_character(session)
    return {
        "saved": True,
        "player_id": PROBE,
        "location": session.location,
        "moved_off_spawn": bool(rooms),
        "job_source": "chosen from the Blueprint under test" if JOBS else "Blueprint ships no jobs",
        "planted": planted,
    }


def stage_restart(expected: dict[str, object], sabotage: bool) -> dict[str, object]:
    _bootstrap()
    from kernel.world.characters import load_character, restore_character
    from kernel.world.session import Session

    casefile = load_character(PROBE)
    if casefile is None:
        return {"found": False, "mismatches": ["character absent from the store after restart"]}

    revived = Session(player_id=PROBE)
    if not sabotage:
        restore_character(revived, casefile)
    # Sabotaged: the casefile was READ but never applied. A stage that passes on a hero it never
    # restored is reporting on the read, not on the round trip.

    mismatches = []
    for field, want in _planted_in(expected).items():
        got = getattr(revived, field)
        if got != want:
            mismatches.append(f"{field}: wrote {want!r}, read back {got!r}")
    if revived.location != expected["location"]:
        mismatches.append(
            f"location: wrote {expected['location']!r}, read back {revived.location!r}"
        )

    return {
        "found": True,
        "location": revived.location,
        "level": revived.level,
        "xp": revived.xp,
        "coins": revived.coins,
        "mismatches": mismatches,
    }


def stage_survive(expected: dict[str, object], sabotage: bool) -> dict[str, object]:
    """Total loss, not a restart: back the database up, DELETE it, restore, read the hero back."""
    _bootstrap()
    from kernel.world.characters import load_character
    from kernel.world.db import DB_PATH, backup_db, restore_db

    live = Path(DB_PATH)
    backup = backup_db()
    steps: dict[str, object] = {"backup": str(backup), "db": str(live)}

    if not sabotage:
        live.unlink()  # the loss the backup exists for
    steps["deleted"] = not live.exists()

    # With the database gone the hero must be unreachable, otherwise the restore below proves
    # nothing: it would be reading a store that was never actually lost.
    steps["gone_while_deleted"] = load_character(PROBE) is None if steps["deleted"] else False

    restore_db(backup)
    casefile = load_character(PROBE)
    if casefile is None:
        steps["recovered"] = False
        steps["mismatches"] = ["hero did not come back from the backup"]
        return steps

    mismatches = []
    for field, want in _planted_in(expected).items():
        got = casefile.get(field)
        if got != want:
            mismatches.append(f"{field}: backed up {want!r}, restored {got!r}")
    if casefile.get("location") != expected["location"]:
        mismatches.append(
            f"location: backed up {expected['location']!r}, restored {casefile.get('location')!r}"
        )
    steps["recovered"] = True
    steps["mismatches"] = mismatches
    return steps


# --- the child dispatcher ----------------------------------------------------------------------

_STAGES = {
    "isolation": lambda payload, sab: stage_isolation(sab),  # noqa: ARG005
    "persist": lambda payload, sab: stage_persist(sab),  # noqa: ARG005
    "restart": lambda payload, sab: stage_restart(payload, sab),  # noqa: PLW0108
    "survive": lambda payload, sab: stage_survive(payload, sab),  # noqa: PLW0108
}


def _run_child() -> int:
    stage = sys.argv[2]
    payload = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}  # noqa: PLR2004
    sabotage = os.environ.get("M2_SABOTAGE") == stage
    try:
        result = _STAGES[stage](payload, sabotage)
    except Exception as blast:  # a stage that explodes is a FAIL with a reason, never a traceback  # noqa: BLE001, E501
        result = {"error": f"{type(blast).__name__}: {blast}"}
    print("---M2JSON---")
    print(json.dumps(result))
    return 0


# --- the parent --------------------------------------------------------------------------------


def _spawn(target: Path, stage: str, payload: dict[str, object], sabotage: str | None) -> dict:
    """Run one stage in a brand new interpreter rooted at the target."""
    env = dict(os.environ)
    env["CODEFORGE_DB"] = str(target / "codeforge.db")  # the PRODUCT's state, never the engine's
    env["PYTHONNOUSERSITE"] = "1"
    if sabotage:
        env["M2_SABOTAGE"] = sabotage

    proc = subprocess.run(  # noqa: PLW1510, S603
        [sys.executable, str(Path(__file__).resolve()), "--child", stage, json.dumps(payload)],
        cwd=str(target),
        env=env,
        capture_output=True,
        text=True,
    )
    if "---M2JSON---" not in proc.stdout:
        return {
            "error": f"stage produced no verdict (exit {proc.returncode})",
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
    return json.loads(proc.stdout.split("---M2JSON---", 1)[1].strip())


def _verdict(name: str, ok: bool, detail: str) -> bool:
    print(f"  [{PASS if ok else FAIL}] {name:<10} {detail}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", required=True, type=Path, help="the poured Target Product")
    ap.add_argument("--sabotage", choices=sorted(_STAGES), help="break one stage on purpose")
    args = ap.parse_args()

    target = args.target.resolve()
    if not (target / "forge.py").is_file():
        print(f"FAIL: {target} does not look like a poured product (no forge.py)")
        return 2

    print("M2 pipeline proof")
    print(f"  target    {target}")
    print(f"  python    {sys.executable}")
    if args.sabotage:
        print(f"  SABOTAGE  {args.sabotage} (this run is expected to FAIL at that stage)")
    print()

    ok = True

    iso = _spawn(target, "isolation", {}, args.sabotage)
    ok &= _verdict(
        "isolation",
        bool(iso.get("imported_from_target")),
        iso.get("error") or f"engine imported from {iso.get('kernel_resolved_to')}",
    )

    persisted = _spawn(target, "persist", {}, args.sabotage)
    saved = bool(persisted.get("saved"))
    ok &= _verdict(
        "persist",
        saved,
        persisted.get("error")
        or (
            f"hero '{PROBE}' saved at {persisted.get('location')!r} "
            f"as {dict(persisted.get('planted') or {}).get('job', 'no calling')!r}"
            if saved
            else f"hero '{PROBE}' was never written to the store"
        ),
    )
    if not persisted.get("saved"):
        print("\nVERDICT: FAIL (nothing was persisted, the remaining stages cannot mean anything)")
        return 1

    revived = _spawn(target, "restart", persisted, args.sabotage)
    restart_ok = bool(revived.get("found")) and not revived.get("mismatches")
    ok &= _verdict(
        "restart",
        restart_ok,
        revived.get("error")
        or (
            f"fresh interpreter read back level {revived.get('level')}, "
            f"xp {revived.get('xp')}, at {revived.get('location')!r}"
            if restart_ok
            else "; ".join(revived.get("mismatches") or ["hero not found"])
        ),
    )

    survived = _spawn(target, "survive", persisted, args.sabotage)
    survive_ok = (
        bool(survived.get("recovered"))
        and bool(survived.get("deleted"))
        and bool(survived.get("gone_while_deleted"))
        and not survived.get("mismatches")
    )
    if survived.get("recovered") and not survived.get("deleted"):
        detail = "database was never actually deleted, so the restore proves nothing"
    elif survived.get("recovered") and not survived.get("gone_while_deleted"):
        detail = "hero was still readable with the database deleted, so the loss was not real"
    else:
        detail = survived.get("error") or (
            "database deleted and restored from backup, hero intact"
            if survive_ok
            else "; ".join(survived.get("mismatches") or ["not recovered"])
        )
    ok &= _verdict("survive", survive_ok, detail)

    print()
    print(f"VERDICT: {PASS if ok else FAIL}")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        raise SystemExit(_run_child())
    raise SystemExit(main())
