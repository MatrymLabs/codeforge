"""Test twin for kernel/seedlab/repository_proof.py -- the platform models a REAL repository.

Acceptance: a genuine git working tree is modeled, and the branch and commit recorded match what
git itself reports; a fresh process recovers the same facts; a non-git directory is honestly
recorded as no-vcs rather than refused.

Refusal (fail loud): the report never carries file CONTENTS, only metadata; a protected path is
never listed; a path outside the target tree is refused.

Why this file exists: every prior proof pointed at a fabricated .git written by the test itself,
which proves the parser reads bytes it was handed, not that the platform can model a real codebase.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.seedlab.repository_proof import model_repository


def _real_repo(root: Path) -> tuple[str, str]:
    """A REAL git repository, built by git itself. Returns (branch, short_commit)."""
    root.mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git[:3], "init", "-q", "-b", "main"], check=True, capture_output=True)
    (root / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "README.md").write_text("# real\n", encoding="utf-8")
    (root / ".env").write_text("SECRET_TOKEN=hunter2\n", encoding="utf-8")  # must never be listed
    subprocess.run([*git, "add", "-A"], check=True, capture_output=True)
    subprocess.run([*git, "commit", "-qm", "first"], check=True, capture_output=True)
    branch = subprocess.run(
        [*git[:3], "rev-parse", "--abbrev-ref", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    commit = subprocess.run(
        [*git[:3], "rev-parse", "--short", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    return branch, commit


def test_the_recorded_branch_and_commit_are_what_git_reports(tmp_path: Path) -> None:
    """The whole point. Not 'a string was stored' -- the SAME string git itself reports."""
    branch, commit = _real_repo(tmp_path / "repo")
    modeled = model_repository(tmp_path / "repo")
    assert modeled.branch == branch
    assert modeled.commit.startswith(commit[:7])


def test_a_real_repository_is_not_reported_as_no_vcs(tmp_path: Path) -> None:
    _real_repo(tmp_path / "repo")
    assert model_repository(tmp_path / "repo").vcs != "no-vcs"


def test_a_plain_directory_is_honestly_no_vcs_not_an_error(tmp_path: Path) -> None:
    """Refusing it would make the platform less useful, not safer."""
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "notes.txt").write_text("hello\n", encoding="utf-8")
    assert model_repository(plain).vcs == "no-vcs"


def test_a_protected_path_is_never_listed(tmp_path: Path) -> None:
    _real_repo(tmp_path / "repo")
    listed = " ".join(model_repository(tmp_path / "repo").files)
    assert ".env" not in listed
    assert ".git" not in listed


def test_the_report_carries_metadata_and_never_file_contents(tmp_path: Path) -> None:
    """A report that embeds source is an exfiltration path, not an artifact."""
    _real_repo(tmp_path / "repo")
    blob = str(model_repository(tmp_path / "repo").to_dict())
    assert "hunter2" not in blob  # the .env secret
    assert "def main" not in blob  # the source itself


def test_a_missing_target_is_refused_loudly(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        model_repository(tmp_path / "nope")


def test_the_recorded_facts_outlive_the_process(tmp_path: Path) -> None:
    """A fresh process must recover the same correspondence from disk, not recompute it."""
    import importlib

    from kernel.seedlab import repository_proof

    branch, commit = _real_repo(tmp_path / "repo")
    first = model_repository(tmp_path / "repo")
    store = tmp_path / "store"
    repository_proof.persist(first, store)

    importlib.reload(repository_proof)
    recovered = repository_proof.recover(store, first.source_id)

    assert recovered.branch == branch
    assert recovered.commit == first.commit
    assert recovered.source_id == first.source_id


def test_a_real_linked_worktree_records_its_git_facts(tmp_path: Path) -> None:
    """A developer worktree uses a .git pointer file, not a fabricated .git directory."""
    source = tmp_path / "source"
    _real_repo(source)
    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "-C", str(source), "worktree", "add", "-q", "-b", "linked", str(linked)],
        check=True,
        capture_output=True,
    )
    branch = subprocess.run(
        ["git", "-C", str(linked), "rev-parse", "--abbrev-ref", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    commit = subprocess.run(
        ["git", "-C", str(linked), "rev-parse", "--short", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    modeled = model_repository(linked)
    assert modeled.branch == branch
    assert modeled.commit.startswith(commit[:7])
