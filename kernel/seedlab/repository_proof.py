"""Read-only, durable evidence that a local source models a real repository."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess  # nosec B404 -- fixed argv, no shell, read-only `git ls-files`
from dataclasses import asdict, dataclass
from pathlib import Path

from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import LocalSource


class RepositoryProofError(Exception):
    """A persisted repository proof cannot be read honestly."""


@dataclass(frozen=True)
class RepositoryProof:
    """Metadata-only snapshot of a source tree and its VCS facts."""

    source_id: str
    root: str
    files: tuple[str, ...]
    branch: str | None
    commit: str
    vcs: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def model_repository(root: Path) -> RepositoryProof:
    """Model one source tree through the existing read-only source connector."""
    resolved = Path(root).resolve()
    source_id = f"repository-{hashlib.sha256(str(resolved).encode()).hexdigest()[:16]}"
    connector = LocalSource(
        resolved,
        Provenance(
            source_id=source_id,
            owner="unknown",
            license="unknown",
            visibility="unknown",
            allowed_use="read-only repository proof",
        ),
    )
    record = connector.register()
    branch, commit = record.branch, record.commit
    if branch is None and commit is None:
        branch, commit = _linked_worktree_head(resolved)
    return RepositoryProof(
        source_id=record.source_id,
        root=record.root,
        files=_repository_files(resolved, connector),
        branch=branch,
        commit=commit or "",
        vcs="git" if branch is not None or commit is not None else "no-vcs",
    )


def _linked_worktree_head(root: Path) -> tuple[str | None, str | None]:
    """Read a Git worktree's indirection files without invoking Git or writing its tree."""
    pointer = root / ".git"
    if not pointer.is_file():
        return None, None
    marker = pointer.read_text(encoding="utf-8", errors="replace").strip()
    if not marker.startswith("gitdir: "):
        return None, None
    gitdir = Path(marker.removeprefix("gitdir: "))
    if not gitdir.is_absolute():
        gitdir = (root / gitdir).resolve()
    head = gitdir / "HEAD"
    if not head.is_file():
        return None, None
    ref = head.read_text(encoding="utf-8", errors="replace").strip()
    if not ref.startswith("ref: "):
        return None, ref[:12]
    refpath = ref.removeprefix("ref: ")
    common = gitdir
    common_file = gitdir / "commondir"
    if common_file.is_file():
        common = (gitdir / common_file.read_text(encoding="utf-8").strip()).resolve()
    loose = common / refpath
    branch = refpath.removeprefix("refs/heads/")
    return branch, (
        loose.read_text(encoding="utf-8", errors="replace").strip()[:12]
        if loose.is_file()
        else None
    )


def _path_for(store: Path, source_id: str) -> Path:
    if (
        not source_id.startswith("repository-")
        or not source_id.removeprefix("repository-").isalnum()
    ):
        raise RepositoryProofError(f"invalid repository proof id: {source_id!r}")
    return store / f"{source_id}.json"


def persist(proof: RepositoryProof, store: Path) -> Path:
    """Write a metadata-only proof outside the repository being inspected."""
    store.mkdir(parents=True, exist_ok=True)
    path = _path_for(store, proof.source_id)
    path.write_text(json.dumps(proof.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def recover(store: Path, source_id: str) -> RepositoryProof:
    """Recover the prior report without touching or recomputing the source tree."""
    path = _path_for(store, source_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RepositoryProofError(f"cannot recover repository proof {source_id!r}") from exc
    try:
        return RepositoryProof(
            source_id=payload["source_id"],
            root=payload["root"],
            files=tuple(payload["files"]),
            branch=payload["branch"],
            commit=str(payload["commit"]),
            vcs=payload["vcs"],
        )
    except (KeyError, TypeError) as exc:
        raise RepositoryProofError(f"invalid repository proof {source_id!r}") from exc


def _repository_files(root: Path, connector: LocalSource) -> tuple[str, ...]:
    """The files git TRACKS, falling back to the connector's listing when git cannot answer.

    A repository proof that lists the filesystem is not modelling a repository. Pointed at this
    engine, the connector's rglob listing returned 1809 files of which 532 were gitignored: the
    coverage cache, the hypothesis corpus, and codeforge.db, the live database. None of them are
    part of the codebase, and on a source whose secrets are not in the connector's denylist,
    "every file on disk" is the wrong default for an artifact that gets written out and kept.

    Protected paths are filtered AFTER git, not instead of it, so the denylist still applies to
    anything tracked. A tree with no git, or a git that will not answer, degrades to the previous
    behaviour rather than to an empty model.
    """
    tracked = _git_tracked(root)
    if tracked is None:
        return tuple(connector.list_files())
    return tuple(sorted(f for f in tracked if not connector._is_protected(f)))


def _git_tracked(root: Path) -> list[str] | None:
    """Repo-relative posix paths git tracks, or None when git cannot answer.

    Subprocess is deliberate and confined here. `source_connector` stays subprocess-free because
    it is a runtime seam; this module is proof tooling, and `scripts/packet_gate.py` already shells
    to `git rev-parse` for the same reason. Reading `.git/index` by hand to avoid one read-only
    command would be the more fragile choice, not the safer one.
    """
    git = shutil.which("git")
    if git is None:
        return None
    try:
        done = subprocess.run(  # nosec B603 -- fixed argv, shell=False, read-only  # noqa: S603
            [git, "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return [entry for entry in done.stdout.split("\0") if entry]
