"""Contract tests for the non-destructive WIP snapshot instrument."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import wip_net as gate

SCRIPT = Path(__file__).resolve().with_name("wip_net.py")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    assert _git(root, "commit", "-qm", "base").returncode == 0
    return root


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=root, capture_output=True, text=True, check=False
    )


def test_main_clean_and_dirty_paths_are_covered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr(gate, "ROOT", root)
    assert gate.main() == 0
    assert "clean tree" in capsys.readouterr().out

    (root / "tracked.txt").write_text("covered\n", encoding="utf-8")
    assert gate.main() == 0
    output = capsys.readouterr().out
    assert "WIPNET: snapshot" in output


def test_git_stash_create_preserves_status_and_stash_ref_and_contains_edit(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "tracked.txt").write_text("uncommitted\n", encoding="utf-8")
    before = _git(root, "status", "--porcelain").stdout
    ref_before = _git(root, "rev-parse", "-q", "--verify", "refs/stash").stdout

    result = _run(root)

    after = _git(root, "status", "--porcelain").stdout
    ref_after = _git(root, "rev-parse", "-q", "--verify", "refs/stash").stdout
    assert result.returncode == 0, result.stdout + result.stderr
    assert before == after
    assert ref_before == ref_after
    sha = re.search(r"WIPNET: snapshot ([0-9a-f]{40})", result.stdout)
    assert sha is not None
    assert "uncommitted" in _git(root, "show", f"{sha.group(1)}:tracked.txt").stdout

    (root / "tracked.txt").write_text("lost\n", encoding="utf-8")
    restore = _git(root, "checkout", sha.group(1), "--", ".")
    assert restore.returncode == 0
    assert (root / "tracked.txt").read_text(encoding="utf-8") == "uncommitted\n"
    assert f"git checkout {sha.group(1)} -- ." in result.stdout


def test_untracked_is_snapshotted_and_ignored_is_excluded(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ".gitignore").write_text("ignored.log\n", encoding="utf-8")
    _git(root, "add", ".gitignore")
    assert _git(root, "commit", "-qm", "ignore generated files").returncode == 0
    (root / "wipnet_canary.txt").write_text("new work\n", encoding="utf-8")
    (root / "ignored.log").write_text("generated\n", encoding="utf-8")
    before = _git(root, "status", "--porcelain").stdout
    ref_before = _git(root, "rev-parse", "-q", "--verify", "refs/stash").stdout

    result = _run(root)

    after = _git(root, "status", "--porcelain").stdout
    ref_after = _git(root, "rev-parse", "-q", "--verify", "refs/stash").stdout
    sha = re.search(r"WIPNET: snapshot ([0-9a-f]{40})", result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sha is not None
    assert before == after
    assert ref_before == ref_after
    assert _git(root, "show", f"{sha.group(1)}:wipnet_canary.txt").stdout == "new work\n"
    assert _git(root, "show", f"{sha.group(1)}:ignored.log").returncode != 0


def test_clean_tree_reports_no_snapshot_and_exits_zero(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    result = _run(root)
    assert result.returncode == 0
    assert "clean tree; nothing to snapshot" in result.stdout
    assert "WIPNET: snapshot " not in result.stdout
