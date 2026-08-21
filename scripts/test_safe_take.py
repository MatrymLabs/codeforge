"""Prove safe_take refuses the take when its safety net fails.

Canon 13: a Gate is trusted only when it has been shown to fail for the bad state it claims to
catch. The bad state here is "the snapshot could not be made", and the case that matters is
test_refuses_when_snapshot_fails. Everything else is supporting.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from safe_take import at_risk, take


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo where `other` holds a different version of tracked.txt than the working tree."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "bench@example.invalid")
    _git(root, "config", "user.name", "Bench")
    (root / "tracked.txt").write_text("committed content\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, "commit", "-q", "-m", "base")
    _git(root, "checkout", "-q", "-b", "other")
    (root / "tracked.txt").write_text("other branch content\n", encoding="utf-8")
    _git(root, "commit", "-q", "-am", "other")
    _git(root, "checkout", "-q", "main")
    return root


def test_refuses_when_snapshot_fails(repo: Path) -> None:
    """THE CASE THAT MATTERS. Net fails, so the fall does not happen."""
    (repo / "tracked.txt").write_text("PRECIOUS UNCOMMITTED WORK\n", encoding="utf-8")

    exit_code = take(repo, "other", ["tracked.txt"], snapshot=lambda _root: "")

    assert exit_code == 1
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "PRECIOUS UNCOMMITTED WORK\n"


def test_refusal_names_every_path_it_protected(repo: Path, capsys) -> None:
    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    take(repo, "other", ["tracked.txt"], snapshot=lambda _root: "")

    out = capsys.readouterr().out
    assert "REFUSED" in out
    assert "tracked.txt" in out
    assert "were NOT touched" in out


def test_takes_and_prints_a_working_recovery_command(repo: Path, capsys) -> None:
    """The recovery command is pasted into the output, and it actually restores the content."""
    (repo / "tracked.txt").write_text("about to be overwritten\n", encoding="utf-8")

    assert take(repo, "other", ["tracked.txt"]) == 0
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "other branch content\n"

    recover = [line for line in capsys.readouterr().out.splitlines() if "RECOVER with" in line][0]
    sha = recover.split("git checkout ")[1].split(" -- ")[0]
    _git(repo, "checkout", sha, "--", "tracked.txt")
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "about to be overwritten\n"


def test_untracked_file_is_at_risk_too(repo: Path) -> None:
    """An untracked file has no blob anywhere, so it is the MORE dangerous case, not the lesser."""
    (repo / "untracked.txt").write_text("never committed\n", encoding="utf-8")

    assert at_risk(repo, ["untracked.txt"]) == ["untracked.txt"]

    take(repo, "other", ["untracked.txt"], snapshot=lambda _root: "")
    assert (repo / "untracked.txt").read_text(encoding="utf-8") == "never committed\n"


def test_clean_path_takes_without_a_snapshot(repo: Path, capsys) -> None:
    """No uncommitted content means nothing to protect; the guard must not become friction."""
    assert take(repo, "other", ["tracked.txt"]) == 0
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "other branch content\n"
    assert "nothing was at risk" in capsys.readouterr().out


def test_check_reports_without_touching_anything(repo: Path) -> None:
    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    assert take(repo, "other", ["tracked.txt"], check_only=True) == 1
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "dirty\n"


def test_check_on_a_clean_path_passes(repo: Path) -> None:
    assert take(repo, "other", ["tracked.txt"], check_only=True) == 0


def test_bad_ref_leaves_the_tree_alone(repo: Path) -> None:
    """A checkout that git itself refuses must not be reported as a take."""
    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    assert take(repo, "no-such-ref", ["tracked.txt"]) == 2
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "dirty\n"


def test_main_wires_the_flags_through(repo: Path) -> None:
    """The CLI is the surface a Bench actually touches, so it gets a test like anything else."""
    import safe_take

    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    assert safe_take.main(["--from", "other", "--check", "--root", str(repo), "tracked.txt"]) == 1
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "dirty\n"

    assert safe_take.main(["--from", "other", "--root", str(repo), "tracked.txt"]) == 0
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "other branch content\n"


def test_wipnet_snapshot_returns_a_sha_for_a_dirty_tree(repo: Path) -> None:
    """The bridge to the consumed instrument, exercised for real rather than mocked."""
    import safe_take

    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    sha = safe_take.wipnet_snapshot(repo)

    assert len(sha) == 40
    subprocess.run(["git", "cat-file", "-e", sha], cwd=repo, check=True)


def test_wipnet_snapshot_reports_clean_rather_than_failure(repo: Path) -> None:
    """A clean tree is not a failed snapshot. Conflating them would refuse every safe take."""
    import safe_take

    assert safe_take.wipnet_snapshot(repo) == "CLEAN"


def test_wipnet_snapshot_returns_empty_outside_a_repository(tmp_path: Path) -> None:
    import safe_take

    assert safe_take.wipnet_snapshot(tmp_path) == ""


def test_at_risk_is_empty_when_git_cannot_answer(tmp_path: Path) -> None:
    assert at_risk(tmp_path, ["anything"]) == []
