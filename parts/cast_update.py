"""CARD: cast_update -- read-only drift report for a poured cast against a fresh engine source.

A cast (parts/cast.py) vendors the engine as a FROZEN snapshot of codeforge@<commit>. Over time the
source engine gains fixes; this Lens reports the DRIFT between a cast's carried engine and a target
source checkout: which carried modules changed upstream, what is upstream-only, what is cast-only,
and the commit delta -- WITHOUT touching the cast. It is the U1 "know before you touch" phase; an
apply step (re-vendor + revalidate the cast) is a separate, keel-gated build. Reads only; mutates
nothing.

The source is a SEAM: a directory (a codeforge checkout at a chosen ref), with commit resolution
injected, so the diff runs offline and tests never shell out or touch the network.

Two lenses on the same vendored tree:
  - drift vs the TARGET source (changed / upstream-only / cast-only): what an update would bring.
  - local edits vs the PIN (locally_modified): what the OWNER changed since pour, which a blind
    re-vendor would overwrite. U2's apply step must refuse to clobber these.

Honest scope: this compares engine FILE CONTENT (forge.py + parts/**/*.py). `upstream_only` is split
by the pin into `newly_upstream` (absent at the pin: genuinely new engine modules) and `shed`
(present at the pin: the cast chose not to carry them). That is a file-history split, not a surface
re-trace: whether a NEWLY-upstream module actually enters this cast's SURFACE closure needs the
cast's surfaces recorded at pour time (a future slice / U2 concern). All pin-relative lenses need
the pinned commit present in the source repo; when it is not, the report says so (pin_verifiable).
"""

from __future__ import annotations

import hashlib
import subprocess  # nosec B404 -- fixed argv, no shell; used only to read the source's git commit
from dataclasses import dataclass, field
from pathlib import Path

from parts.cast import CastError, read_manifest


@dataclass(frozen=True)
class CastDrift:
    """The drift between a cast's vendored engine and a target source (empty lists == in sync)."""

    cast_dir: str
    pinned_commit: str  # the commit the cast was poured from (its manifest)
    target_commit: str  # the target source checkout's commit
    engine_strategy: str  # vendored-whole | vendored-selective (shapes how upstream_only reads)
    changed: list[str] = field(default_factory=list)  # carried files whose upstream content differs
    upstream_only: list[str] = field(default_factory=list)  # in source, not the cast (new OR shed)
    cast_only: list[str] = field(
        default_factory=list
    )  # in the cast, not source (owner-added/removed)
    locally_modified: list[str] = field(
        default_factory=list
    )  # carried files the OWNER changed since pour (an update would overwrite these)
    newly_upstream: list[str] = field(
        default_factory=list
    )  # upstream_only files ABSENT at the pin: genuinely new engine modules an update would add
    shed: list[str] = field(
        default_factory=list
    )  # upstream_only files PRESENT at the pin: deliberately not carried (a selective cast's cut)
    pin_verifiable: bool = True  # could the pinned commit's tree be read to check for local edits?

    @property
    def has_engine_drift(self) -> bool:
        """True when any engine file changed, appeared upstream, or is cast-only."""
        return bool(self.changed or self.upstream_only or self.cast_only)

    @property
    def in_sync(self) -> bool:
        """Fully in sync: no drift vs the target AND no unverified/local edits vs the pin."""
        return not self.has_engine_drift and not self.locally_modified and self.pin_verifiable


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _engine_files(root: Path) -> dict[str, str]:
    """Map each engine file's root-relative path -> sha256 (forge.py + parts/**/*.py, no caches)."""
    files: dict[str, str] = {}
    forge = root / "forge.py"
    if forge.is_file():
        files["forge.py"] = _sha(forge)
    parts = root / "parts"
    if parts.is_dir():
        for path in sorted(parts.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            files[str(path.relative_to(root))] = _sha(path)
    return files


def _resolve_commit(source_root: Path) -> str:
    """The source checkout's short commit via git; 'unknown' if it is not a repo. Never raises."""
    try:
        done = subprocess.run(  # nosec B603 B607 -- fixed argv, no shell; read-only git query
            ["git", "-C", str(source_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return done.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _commit_present(source_root: Path, commit: str) -> bool:
    """True if <commit> exists in the source repo; '' / 'unknown' -> False. Never raises."""
    if commit in ("", "unknown"):
        return False
    try:
        done = subprocess.run(  # nosec B603 B607 -- fixed argv, no shell; read-only existence check
            ["git", "-C", str(source_root), "cat-file", "-e", f"{commit}^{{commit}}"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return done.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _read_at_commit(source_root: Path, commit: str, relpath: str) -> bytes | None:
    """The bytes of <relpath> at <commit> via `git show`, or None if absent. Never raises."""
    try:
        done = subprocess.run(  # nosec B603 B607 -- fixed argv, no shell; read-only blob read
            ["git", "-C", str(source_root), "show", f"{commit}:{relpath}"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return done.stdout if done.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def diff_cast(
    cast_dir: Path | str,
    source_root: Path | str,
    *,
    resolve_commit=_resolve_commit,
    commit_present=_commit_present,
    read_at_commit=_read_at_commit,
) -> CastDrift:
    """Report the drift between a poured cast's engine and a target source checkout (read-only).

    `cast_dir` is a poured cast (must carry a cast_manifest.json); `source_root` is a codeforge
    checkout at the ref to compare against. Two lenses: drift vs the target (changed / upstream-only
    / cast-only), and local edits vs the PIN (files the owner changed since pour). The three git
    calls are injectable seams (resolve_commit / commit_present / read_at_commit), so tests run
    offline. Fails loud if either side is not what it claims (no manifest, or a source with no
    engine)."""
    cast_dir, source_root = Path(cast_dir), Path(source_root)
    manifest_path = cast_dir / "cast_manifest.json"
    if not manifest_path.is_file():
        raise CastError(f"no cast_manifest.json in {cast_dir}: not a poured cast")
    if not (source_root / "forge.py").is_file() or not (source_root / "parts").is_dir():
        raise CastError(f"source {source_root} is not a codeforge checkout (no forge.py / parts/)")
    manifest = read_manifest(manifest_path)
    cast_files = _engine_files(cast_dir)
    src_files = _engine_files(source_root)
    shared = cast_files.keys() & src_files.keys()

    # Local-edit lens: a carried file whose content differs from the source AT THE PIN was edited by
    # the owner after pour. Only checkable when the pinned commit is present in the source repo; a
    # file absent at the pin is owner-ADDED (cast_only), not a local edit, so it is skipped here.
    upstream_only = sorted(src_files.keys() - cast_files.keys())
    pinned = manifest.codeforge_commit
    pin_verifiable = commit_present(source_root, pinned)
    locally_modified: list[str] = []
    newly_upstream: list[str] = []
    shed: list[str] = []
    if pin_verifiable:
        for rel in sorted(cast_files):
            original = read_at_commit(source_root, pinned, rel)
            if original is not None and hashlib.sha256(original).hexdigest() != cast_files[rel]:
                locally_modified.append(rel)
        # Split upstream_only by the pin: a file present at the pin was SHED (the cast chose not to
        # carry it); one absent at the pin is genuinely NEW upstream (an update would add it).
        for rel in upstream_only:
            if read_at_commit(source_root, pinned, rel) is None:
                newly_upstream.append(rel)
            else:
                shed.append(rel)

    return CastDrift(
        cast_dir=str(cast_dir),
        pinned_commit=pinned,
        target_commit=resolve_commit(source_root),
        engine_strategy=manifest.engine_strategy,
        changed=sorted(f for f in shared if cast_files[f] != src_files[f]),
        upstream_only=upstream_only,
        cast_only=sorted(cast_files.keys() - src_files.keys()),
        locally_modified=locally_modified,
        newly_upstream=newly_upstream,
        shed=shed,
        pin_verifiable=pin_verifiable,
    )


def _section(title: str, items: list[str]) -> list[str]:
    body = [f"    - {m}" for m in items] if items else ["    (none)"]
    return [f"  {title} ({len(items)}):", *body]


def render_drift(drift: CastDrift) -> str:
    """A human-readable drift report: the commit delta then the engine file drift, honestly labeled.

    In sync == no file drift (the target carries the same engine). Otherwise it names the three
    buckets so a reader knows exactly what an apply step would touch. It states plainly that this is
    read-only, so no one mistakes the report for an update."""
    if not drift.pin_verifiable:
        local_line = (
            f"  local edits:      cannot verify (pin {drift.pinned_commit} not in the source)"
        )
    elif drift.locally_modified:
        local_line = (
            f"  local edits:      {len(drift.locally_modified)} file(s) modified since pour"
        )
    else:
        local_line = "  local edits:      none (vendored engine matches the pin)"
    lines = [
        f"Cast drift -- {drift.cast_dir}",
        "=" * 40,
        "",
        f"  engine strategy:  {drift.engine_strategy}",
        f"  pinned commit:    {drift.pinned_commit}",
        f"  target commit:    {drift.target_commit}",
        local_line,
        "",
    ]
    if drift.in_sync:
        lines.append("  engine: IN SYNC with the target (no file drift, no local edits).")
        return "\n".join(lines)
    if drift.locally_modified:
        title = "locally modified since pour (an update would overwrite these)"
        lines += [*_section(title, drift.locally_modified), ""]
    lines += _section("changed upstream (a fix you could pull)", drift.changed)
    if drift.pin_verifiable:
        # Split by the pin: genuinely new engine modules vs modules this cast deliberately shed.
        lines += [
            "",
            *_section(
                "newly upstream since your pin (an update would add these)", drift.newly_upstream
            ),
        ]
        lines += [
            "",
            *_section("shed by this cast (not carried; expected for a selective cut)", drift.shed),
        ]
    else:
        title = "upstream-only (new upstream, or shed by a selective cast)"
        lines += ["", *_section(title, drift.upstream_only)]
    lines += [
        "",
        *_section("cast-only (your local additions, or removed upstream)", drift.cast_only),
    ]
    lines += [
        "",
        "  Read-only report. Applying an update (re-vendor + revalidate) is a separate step.",
    ]
    return "\n".join(lines)
