#!/usr/bin/env python3
"""Snapshot uncommitted tracked work without changing the working tree."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path.cwd()


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  # git is the instrument's intended subprocess
        ["git", *args],  # noqa: S607  # resolve git from PATH; absolute paths recreate KF-WIN-2
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        check=False,
    )


def _stash_ref() -> str:
    result = _git("rev-parse", "-q", "--verify", "refs/stash")
    return result.stdout.strip() if result.returncode == 0 else ""


def _snapshot_with_temporary_index() -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile(prefix="wipnet-index-", delete=False) as handle:
        index = Path(handle.name)
    index.unlink()
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = str(index)
    try:
        for args in (("read-tree", "HEAD"), ("add", "--all", "--", ".")):
            result = subprocess.run(  # noqa: S603  # git is the instrument's intended subprocess
                ["git", *args],  # noqa: S607  # resolve git from PATH; absolute paths recreate KF-WIN-2
                cwd=ROOT,
                env=env,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return result
        tree = subprocess.run(
            ["git", "write-tree"],  # noqa: S607  # resolve git from PATH; absolute paths recreate KF-WIN-2
            cwd=ROOT,
            env=env,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            check=False,
        )
        if tree.returncode != 0:
            return tree
        return subprocess.run(  # noqa: S603  # git is the instrument's intended subprocess
            ["git", "commit-tree", tree.stdout.strip(), "-p", "HEAD", "-m", "WIPNET snapshot"],  # noqa: S607  # resolve git from PATH; absolute paths recreate KF-WIN-2
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            check=False,
        )
    finally:
        index.unlink(missing_ok=True)


def main() -> int:
    before = _git("status", "--porcelain")
    if before.returncode != 0:
        print(f"WIPNET: cannot read git status: {before.stderr.strip()}")
        return 1
    if not before.stdout:
        print("WIPNET: clean tree; nothing to snapshot")
        return 0

    ref_before = _stash_ref()
    snapshot = _snapshot_with_temporary_index()
    sha = snapshot.stdout.strip()
    after = _git("status", "--porcelain")
    ref_after = _stash_ref()

    if before.stdout != after.stdout:
        print("WIPNET: FAIL git stash create changed git status --porcelain")
        return 1
    if ref_before != ref_after:
        print("WIPNET: FAIL git stash create moved refs/stash")
        return 1
    if snapshot.returncode != 0 or not sha:
        print(
            "WIPNET: FAIL git stash create returned no snapshot; "
            "snapshot creation failed; no working-tree changes were made"
        )
        return 1

    print(f"WIPNET: snapshot {sha}")
    print(f"WIPNET: restore with `git checkout {sha} -- .`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
