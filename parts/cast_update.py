"""CARD: cast_update -- read-only drift report for a poured cast against a fresh engine source.

A cast (parts/cast.py) vendors the engine as a FROZEN snapshot of codeforge@<commit>. Over time the
source engine gains fixes; this Lens reports the DRIFT between a cast's carried engine and a target
source checkout: which carried modules changed upstream, what is upstream-only, what is cast-only,
and the commit delta -- WITHOUT touching the cast. It is the U1 "know before you touch" phase; an
apply step (re-vendor + revalidate the cast) is a separate, keel-gated build. Reads only; mutates
nothing.

The source is a SEAM: a directory (a codeforge checkout at a chosen ref), with commit resolution
injected, so the diff runs offline and tests never shell out or touch the network.

Honest scope (U1 slice 1): this compares engine FILE CONTENT (forge.py + parts/**/*.py). For a
vendored-selective cast, `upstream_only` includes modules the cast deliberately SHED, not only new
ones -- distinguishing "shed" from "genuinely new" is the selective-closure slice. Detecting the
owner's OWN local edits is the next slice; this one reports drift vs the target, not vs the pin.
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

    @property
    def has_engine_drift(self) -> bool:
        """True when any engine file changed, appeared upstream, or is cast-only."""
        return bool(self.changed or self.upstream_only or self.cast_only)


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


def diff_cast(
    cast_dir: Path | str,
    source_root: Path | str,
    *,
    resolve_commit=_resolve_commit,
) -> CastDrift:
    """Report the drift between a poured cast's engine and a target source checkout (read-only).

    `cast_dir` is a poured cast (must carry a cast_manifest.json); `source_root` is a codeforge
    checkout at the ref to compare against. `resolve_commit` is the injectable seam that names the
    source's commit (defaults to `git rev-parse`), so tests run offline. Fails loud if either side
    is not what it claims (no manifest, or a source with no engine)."""
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
    return CastDrift(
        cast_dir=str(cast_dir),
        pinned_commit=manifest.codeforge_commit,
        target_commit=resolve_commit(source_root),
        engine_strategy=manifest.engine_strategy,
        changed=sorted(f for f in shared if cast_files[f] != src_files[f]),
        upstream_only=sorted(src_files.keys() - cast_files.keys()),
        cast_only=sorted(cast_files.keys() - src_files.keys()),
    )
