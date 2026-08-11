"""Read-only, durable evidence that a local source models a real repository."""

from __future__ import annotations

import hashlib
import json
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
    commit: str | None
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
        files=tuple(connector.list_files()),
        branch=branch,
        commit=commit,
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
            commit=payload["commit"],
            vcs=payload["vcs"],
        )
    except (KeyError, TypeError) as exc:
        raise RepositoryProofError(f"invalid repository proof {source_id!r}") from exc
