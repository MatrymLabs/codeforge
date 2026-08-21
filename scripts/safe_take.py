#!/usr/bin/env python3
"""Take a file from another ref without silently destroying uncommitted work at that path.

`git checkout <ref> -- <path>` overwrites the working tree with no prompt, no backup and no
record. There is no pre-checkout hook, so git cannot be made to refuse it; the guard has to live
in the command a Bench actually runs.

Installed 2026-08-20, after it happened TWICE IN ONE SESSION, the second time an hour after the
first was named as a lesson in writing:

    git checkout <branch> -- docs/MASTER_CHECKLIST.md   destroyed 182 uncommitted lines
    git checkout <branch> -- .ai/WORK_REGISTER.md       destroyed 35 uncommitted lines

The second was recovered only because a rebase minutes earlier had left an autostash that
happened to contain the file. That is luck. Luck is not a control, and naming a failure mode does
not install a guard against it, which is the whole reason this file exists rather than another
paragraph of doctrine.

The rule: snapshot FIRST, and if the snapshot cannot be made, REFUSE THE TAKE. A guard that
proceeds when its safety net fails is decoration.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

# A snapshotter returns the snapshot sha, or "" when it could not make one.
Snapshotter = Callable[[Path], str]


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        check=False,
    )


def wipnet_snapshot(root: Path) -> str:
    """Snapshot via the existing instrument. CONSUMED as a subprocess, never reimplemented.

    wip_net.py is already tested and already proven not to disturb the working tree or refs/stash.
    Calling it rather than copying its temporary-index logic keeps one implementation of the
    snapshot, which is the point of having it.
    """
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("wip_net.py"))],
        cwd=root,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        if line.startswith("WIPNET: snapshot "):
            return line.split("WIPNET: snapshot ", 1)[1].strip()
    # A clean tree reports "nothing to snapshot" and is not a failure: there was nothing at risk.
    if "nothing to snapshot" in result.stdout:
        return "CLEAN"
    return ""


def at_risk(root: Path, paths: list[str]) -> list[str]:
    """Which of these paths currently hold content that exists ONLY in the working tree.

    Modified-tracked and untracked both count. An untracked file is the more dangerous of the two
    because it has never had a blob written, so nothing in the object database can recover it.
    """
    result = _git(root, "status", "--porcelain", "--", *paths)
    if result.returncode != 0:
        return []
    found: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) > 3:
            found.append(line[3:].strip().strip('"'))
    return found


def take(
    root: Path,
    ref: str,
    paths: list[str],
    *,
    check_only: bool = False,
    snapshot: Snapshotter = wipnet_snapshot,
) -> int:
    """Snapshot, then take. Refuse the take if the snapshot fails."""
    exposed = at_risk(root, paths)

    if check_only:
        if not exposed:
            print(f"SAFE-TAKE: CLEAN no uncommitted content at {', '.join(paths)}")
            return 0
        print(f"SAFE-TAKE: AT RISK {len(exposed)} path(s) would be overwritten by `{ref}`:")
        for path in exposed:
            print(f"    {path}")
        print("SAFE-TAKE: nothing was changed; this was a check")
        return 1

    if not exposed:
        result = _git(root, "checkout", ref, "--", *paths)
        if result.returncode != 0:
            print(f"SAFE-TAKE: FAIL checkout refused: {result.stderr.strip()}")
            return 2
        print(f"SAFE-TAKE: took {', '.join(paths)} from {ref}; nothing was at risk")
        return 0

    sha = snapshot(root)
    if not sha:
        # THE REFUSAL. The net failed, so the fall does not happen.
        print("SAFE-TAKE: REFUSED could not snapshot the working tree")
        print(f"SAFE-TAKE: {len(exposed)} path(s) hold uncommitted content and were NOT touched:")
        for path in exposed:
            print(f"    {path}")
        print("SAFE-TAKE: commit, stash or copy them aside, then take again")
        return 1

    result = _git(root, "checkout", ref, "--", *paths)
    if result.returncode != 0:
        print(f"SAFE-TAKE: FAIL checkout refused: {result.stderr.strip()}")
        print(f"SAFE-TAKE: snapshot {sha} was made; the working tree is unchanged")
        return 2

    print(f"SAFE-TAKE: snapshot {sha}")
    print(f"SAFE-TAKE: overwrote {len(exposed)} path(s) holding uncommitted content:")
    for path in exposed:
        print(f"    {path}")
    print(f"SAFE-TAKE: RECOVER with `git checkout {sha} -- {' '.join(exposed)}`")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Take paths from another ref, snapshotting anything uncommitted first."
    )
    parser.add_argument("--from", dest="ref", required=True, help="ref to take the content from")
    parser.add_argument(
        "--check", action="store_true", help="report what is at risk, change nothing"
    )
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("paths", nargs="+", help="paths to take")
    args = parser.parse_args(argv)
    return take(Path(args.root), args.ref, args.paths, check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
