"""CARD: source_connector -- a safe, read-only, path-bounded connector that registers a local
directory as a project source: record its provenance, inspect its metadata (incl. git branch and
commit), and list / search / read ONLY approved files -- never a secret, never a path outside root.

Stage 3 of the Seed Platform directive: the first real project-source connector. It is the control
plane's front door, so it is deliberately narrow and hostile-input-safe:

  * Read-only -- no method writes, moves, or deletes anything under the source root.
  * Path-bounded -- every access resolves inside the root; `..`, absolute paths, and symlinks that
    escape the root are refused (`resolve()` collapses them to a real path we bounds-check).
  * Secret-protected -- a denylist (`.env`, keys, `.git`, vaults, `secrets*`, ...) is never listed,
    searched, or read; a request for one fails loud.

Provenance (owner/license/visibility) is recorded for every registered source, reusing the Seed's
`Provenance` type. A registered source becomes an entry in the Project Hub's `sources` facet
(`source_label`). No `kernel/world/` coupling,no subprocess (git facts are read from `.git/` files).
Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from parts.seedlab.project_model import Provenance

# Files/dirs a project source must never expose. Matched against every path component, so a match
# anywhere in the path (a nested `.env`, a `secrets/` dir) is protected. Read-only + this denylist
# are the connector's two safety rails.
_DENY: tuple[str, ...] = (
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    "id_rsa*",
    "id_ed25519*",
    "*.kdbx",
    "secrets",
    "secrets.*",
    "*.secret",
    ".secrets.*",
    "credentials",
    "credentials.*",
    "*.pyc",
)

# Manifests / test / doc signals the connector identifies by convention (the directive's Stage-3
# "identify manifests / tests / documentation").
_MANIFESTS = (
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Makefile",
)


class SourceConnectorError(Exception):
    """Base for a source-connector failure. Fails loud; never guesses past a boundary."""


class PathBoundaryError(SourceConnectorError):
    """A requested path escapes the source root (traversal, absolute path, or symlink escape)."""


class ProtectedPathError(SourceConnectorError):
    """A requested path is on the protected denylist (a secret, a VCS dir, a build artifact)."""


@dataclass(frozen=True)
class SourceRecord:
    """What a registered source is: its id, provenance, root, and inspected metadata. This is the
    record the Seed persists and the Project Hub lists under `sources`."""

    source_id: str
    provenance: Provenance
    root: str
    file_count: int
    branch: str | None
    commit: str | None


@dataclass(frozen=True)
class LocalSource:
    """A read-only, path-bounded view of one local directory as a project source. `provenance` is
    recorded at construction; `root` is resolved to a real absolute path for bounds-checking."""

    root: Path
    provenance: Provenance
    deny: tuple[str, ...] = _DENY

    def __post_init__(self) -> None:
        resolved = Path(self.root).resolve()
        if not resolved.is_dir():
            raise SourceConnectorError(f"source root is not a directory: {self.root}")
        object.__setattr__(self, "root", resolved)  # frozen: set the resolved root once

    # --- safety rails --------------------------------------------------------------------------
    def _is_protected(self, relpath: str) -> bool:
        return any(fnmatch(part, pattern) for part in Path(relpath).parts for pattern in self.deny)

    def _resolve(self, relpath: str) -> Path:
        """Resolve a relative path inside the root, refusing anything that escapes it."""
        if os.path.isabs(relpath):
            raise PathBoundaryError(f"absolute paths are refused: {relpath!r}")
        candidate = (self.root / relpath).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise PathBoundaryError(f"path escapes the source root: {relpath!r}") from exc
        return candidate

    # --- inspect (all read-only) ---------------------------------------------------------------
    def list_files(self) -> list[str]:
        """Every approved file under the root, as posix relpaths. Protected paths are omitted."""
        out: list[str] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root).as_posix()
            if not self._is_protected(rel):
                out.append(rel)
        return out

    def read(self, relpath: str, *, max_bytes: int = 1_000_000) -> str:
        """Read one approved file as text (bounded). Refuses protected or out-of-root paths."""
        if self._is_protected(relpath):
            raise ProtectedPathError(f"path is protected and cannot be read: {relpath!r}")
        path = self._resolve(relpath)
        if not path.is_file():
            raise SourceConnectorError(f"not a file under the source: {relpath!r}")
        return path.read_bytes()[:max_bytes].decode("utf-8", errors="replace")

    def search(self, query: str, *, max_hits: int = 100) -> list[tuple[str, int, str]]:
        """Case-insensitive substring search across approved text files. Returns (relpath, line#,
        line) triples. Protected files are never searched; binary/undecodable files are skipped."""
        if not query:
            raise SourceConnectorError("search query must be non-empty")
        needle = query.lower()
        hits: list[tuple[str, int, str]] = []
        for rel in self.list_files():
            try:
                text = self.read(rel)
            except SourceConnectorError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if needle in line.lower():
                    hits.append((rel, lineno, line.strip()[:200]))
                    if len(hits) >= max_hits:
                        return hits
        return hits

    def identify(self) -> dict[str, list[str]]:
        """Classify approved top-signal files: manifests, tests, docs (by convention)."""
        manifests: list[str] = []
        tests: list[str] = []
        docs: list[str] = []
        for rel in self.list_files():
            name = Path(rel).name
            lower = name.lower()
            if name in _MANIFESTS or lower.startswith("requirements"):
                manifests.append(rel)
            if (
                lower.startswith("test_")
                or lower.endswith(("_test.py", "_test.go"))
                or "/tests/" in f"/{rel}"
            ):
                tests.append(rel)
            if lower.startswith("readme") or lower.endswith(".md") or "/docs/" in f"/{rel}":
                docs.append(rel)
        return {"manifests": manifests, "tests": tests, "docs": docs}

    def _git_head(self) -> tuple[str | None, str | None]:
        """Read the current branch + short commit from `.git/` files (no subprocess). (None, None)
        if this is not a git working tree."""
        head = self.root / ".git" / "HEAD"
        if not head.is_file():
            return None, None
        ref = head.read_text(encoding="utf-8", errors="replace").strip()
        if ref.startswith("ref: "):
            refpath = ref[len("ref: ") :]
            branch = refpath.rsplit("/", 1)[-1]
            loose = self.root / ".git" / refpath
            if loose.is_file():
                return branch, loose.read_text(encoding="utf-8").strip()[:12]
            return branch, None  # commit only in packed-refs; branch is enough here
        return None, ref[:12]  # detached HEAD

    def metadata(self) -> dict:
        """A structured snapshot of the source: root, approved-file count, and git branch/commit."""
        branch, commit = self._git_head()
        return {
            "root": str(self.root),
            "name": self.root.name,
            "file_count": len(self.list_files()),
            "branch": branch,
            "commit": commit,
        }

    def register(self) -> SourceRecord:
        """Register this source: the record the Seed persists and the Project Hub lists. Provenance
        must name the source (a bare `unknown` owner is allowed but visible, never trusted)."""
        meta = self.metadata()
        return SourceRecord(
            source_id=self.provenance.source_id,
            provenance=self.provenance,
            root=meta["root"],
            file_count=meta["file_count"],
            branch=meta["branch"],
            commit=meta["commit"],
        )


def source_label(record: SourceRecord) -> str:
    """The one-line entry a registered source contributes to the Project Hub's `sources` facet."""
    where = record.branch or "no-vcs"
    at = f"@{record.commit}" if record.commit else ""
    return f"local:{record.source_id} ({record.file_count} files, {where}{at})"
