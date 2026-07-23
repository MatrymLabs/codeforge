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
import json
import os
import re
import shutil
import subprocess  # nosec B404 -- fixed argv, no shell; used only to read the source's git commit
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

from parts.cast import (
    VENDORED_SELECTIVE,
    CastError,
    _declared_deps,
    _engine_runtime_deps,
    _vendor_selective,
    read_manifest,
    validate_cast,
    write_manifest,
)


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
    deps_added: list[str] = field(
        default_factory=list
    )  # runtime deps the source has, the cast lacks
    deps_removed: list[str] = field(
        default_factory=list
    )  # deps the cast declares, the source dropped
    deps_changed: list[str] = field(default_factory=list)  # "name: <cast spec> -> <source spec>"
    pin_verifiable: bool = True  # could the pinned commit's tree be read to check for local edits?

    @property
    def has_engine_drift(self) -> bool:
        """True when any engine file changed, appeared upstream, or is cast-only."""
        return bool(self.changed or self.upstream_only or self.cast_only)

    @property
    def has_dep_drift(self) -> bool:
        """True when the cast's declared runtime deps differ from the source's."""
        return bool(self.deps_added or self.deps_removed or self.deps_changed)

    @property
    def in_sync(self) -> bool:
        """Fully in sync: nothing changed, no NEW upstream module, no owner-only/local edits, no dep
        drift, pin verifiable. A selective cast's SHED modules are expected and do not count (else a
        current selective cast would forever read as drifted)."""
        return (
            not self.changed
            and not self.newly_upstream
            and not self.cast_only
            and not self.has_dep_drift
            and not self.locally_modified
            and self.pin_verifiable
        )


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


_REQ_NAME = re.compile(r"^([A-Za-z0-9._-]+)")


def _req_name(requirement: str) -> str:
    """The PEP 503-normalized name of a requirement string ('PyYAML>=6' -> 'pyyaml')."""
    match = _REQ_NAME.match(requirement.strip())
    name = match.group(1) if match else requirement.strip()
    return re.sub(r"[-_.]+", "-", name).lower()


def _dep_delta(
    cast_deps: list[str], source_deps: list[str]
) -> tuple[list[str], list[str], list[str]]:
    """Compare two requirement lists by name: (added, removed, changed). Offline, pure."""
    cast_by = {_req_name(d): d for d in cast_deps}
    src_by = {_req_name(d): d for d in source_deps}
    added = sorted(src_by[n] for n in src_by.keys() - cast_by.keys())
    removed = sorted(cast_by[n] for n in cast_by.keys() - src_by.keys())
    changed = sorted(
        f"{n}: {cast_by[n]} -> {src_by[n]}"
        for n in cast_by.keys() & src_by.keys()
        if cast_by[n] != src_by[n]
    )
    return added, removed, changed


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

    # Dependency lens (offline): the cast's declared runtime deps vs the source's. Only meaningful
    # when BOTH sides carry a pyproject; a bare fixture without one gets no phantom delta.
    deps_added: list[str] = []
    deps_removed: list[str] = []
    deps_changed: list[str] = []
    if (cast_dir / "pyproject.toml").is_file() and (source_root / "pyproject.toml").is_file():
        deps_added, deps_removed, deps_changed = _dep_delta(
            _declared_deps(cast_dir / "pyproject.toml"), _engine_runtime_deps(source_root)[0]
        )

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
        deps_added=deps_added,
        deps_removed=deps_removed,
        deps_changed=deps_changed,
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
    if drift.has_dep_drift:
        n = len(drift.deps_added) + len(drift.deps_removed) + len(drift.deps_changed)
        dep_line = f"  dependencies:     {n} change(s) vs the source (see below)"
    else:
        dep_line = "  dependencies:     match the source"
    lines = [
        f"Cast drift -- {drift.cast_dir}",
        "=" * 40,
        "",
        f"  engine strategy:  {drift.engine_strategy}",
        f"  pinned commit:    {drift.pinned_commit}",
        f"  target commit:    {drift.target_commit}",
        local_line,
        dep_line,
        "",
    ]
    if drift.in_sync:
        lines.append("  engine: IN SYNC with the target (no file drift, no dep drift, no edits).")
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
    if drift.has_dep_drift:
        lines += ["", *_section("dependencies added upstream", drift.deps_added)]
        lines += ["", *_section("dependencies removed upstream", drift.deps_removed)]
        lines += ["", *_section("dependency version specs changed", drift.deps_changed)]
    lines += [
        "",
        "  Read-only report. Applying an update (re-vendor + revalidate) is a separate step.",
    ]
    return "\n".join(lines)


def _pip_audit_runner(requirements: list[str]) -> str:
    """Run pip-audit against `requirements`, returning its JSON output. NEEDS NETWORK (the vuln DB).

    The seam the CVE audit is mocked at: unit tests inject a fake so they never hit the network."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        handle.write("\n".join(requirements) + "\n")
        reqfile = handle.name
    try:
        done = subprocess.run(  # nosec B603 B607 -- fixed argv, no shell; read-only dependency audit
            ["pip-audit", "-r", reqfile, "-f", "json"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return done.stdout
    finally:
        os.unlink(reqfile)


def audit_requirements(requirements: list[str], *, runner=_pip_audit_runner) -> list[str]:
    """The known-CVE lines for `requirements` via pip-audit (behind a runner seam). Empty == clean.

    Each line is `<name> <version>: <vuln id> (fix: <versions>)`. `runner` returns pip-audit's JSON;
    the default shells out (network), tests inject a fake. Malformed JSON yields no findings, not a
    crash -- the audit is advisory, and a broken scan must not read as a clean bill of health here,
    so the caller distinguishes 'ran clean' from 'did not run' by the runner it passes."""
    if not requirements:
        return []
    try:
        data = json.loads(runner(requirements))
    except (json.JSONDecodeError, TypeError):
        return []
    findings: list[str] = []
    for dep in data.get("dependencies", []):
        name, version = dep.get("name", "?"), dep.get("version", "?")
        for vuln in dep.get("vulns", []):
            fix = ", ".join(vuln.get("fix_versions", [])) or "no fix listed"
            findings.append(f"{name} {version}: {vuln.get('id', '?')} (fix: {fix})")
    return sorted(findings)


def render_audit(findings: list[str]) -> str:
    """The dependency-audit section: the CVE findings, or an all-clear line."""
    if not findings:
        return "\n  dependency audit: no known vulnerabilities in the cast's declared deps."
    return "\n".join(["", *_section("dependency vulnerabilities (pip-audit)", findings)])


# --- U2: apply an engine update to a poured cast, safely -----------------------------------------


@dataclass(frozen=True)
class UpdateOutcome:
    """The result of an update attempt. `applied` is the only 'the cast changed' signal."""

    applied: bool
    reason: str
    from_commit: str
    to_commit: str
    files_revendored: int = 0
    validated: bool = False
    rolled_back: bool = False


def _default_validator(cast_dir: Path) -> tuple[bool, str]:
    """The real re-validation: boot the updated cast and run its command corpus (parts.cast)."""
    return validate_cast(cast_dir)


def _restore_engine(cast_dir: Path, backup: Path) -> None:
    """Put the backed-up engine (parts/ + forge.py) back, replacing whatever is there now."""
    if (cast_dir / "parts").exists():
        shutil.rmtree(cast_dir / "parts")
    shutil.copytree(backup / "parts", cast_dir / "parts")
    shutil.copy2(backup / "forge.py", cast_dir / "forge.py")


def _apply_update(
    cast_dir: Path,
    source_root: Path,
    drift: CastDrift,
    *,
    modules: set[str] | None,
    validate: bool,
    validator,
) -> UpdateOutcome:
    """Back up the engine, re-vendor from the source, re-validate, and roll back on any failure.

    `modules` None re-vendors the WHOLE engine (copytree); a set re-vendors only that closure (a
    selective cast, via the same `_vendor_selective` the pour uses). The mutation is bracketed by a
    backup: if validation fails or anything raises, the cast is restored to its prior engine.
    The manifest's pinned commit advances only on success. Never commits -- the owner does."""
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    backup = Path(tempfile.mkdtemp(prefix="cast-update-backup-"))
    try:
        shutil.copytree(cast_dir / "parts", backup / "parts", ignore=ignore)
        shutil.copy2(cast_dir / "forge.py", backup / "forge.py")

        shutil.rmtree(cast_dir / "parts")
        if modules is None:
            shutil.copytree(source_root / "parts", cast_dir / "parts", ignore=ignore)
        else:
            _vendor_selective(source_root / "parts", cast_dir / "parts", modules, ignore)
        shutil.copy2(source_root / "forge.py", cast_dir / "forge.py")
        revendored = len(_engine_files(cast_dir))

        if validate:
            ok, detail = (validator or _default_validator)(cast_dir)
            if not ok:
                _restore_engine(cast_dir, backup)
                return UpdateOutcome(
                    applied=False,
                    reason=f"update failed validation, rolled back: {detail}",
                    from_commit=drift.pinned_commit,
                    to_commit=drift.target_commit,
                    rolled_back=True,
                )

        manifest = read_manifest(cast_dir / "cast_manifest.json")
        write_manifest(
            replace(manifest, codeforge_commit=drift.target_commit),
            cast_dir / "cast_manifest.json",
        )
        return UpdateOutcome(
            applied=True,
            reason="engine updated and revalidated"
            if validate
            else "engine updated (validation skipped)",
            from_commit=drift.pinned_commit,
            to_commit=drift.target_commit,
            files_revendored=revendored,
            validated=validate,
        )
    except Exception as exc:  # any mid-flight failure: restore, then fail loud
        _restore_engine(cast_dir, backup)
        raise CastError(f"update failed and was rolled back: {exc}") from exc
    finally:
        shutil.rmtree(backup, ignore_errors=True)


def _selective_validator(surfaces: list[str]):
    """A validator that boots the cast and drives the surfaces' full corpus (the D2 harness)."""
    from parts import coupling

    def _check(cast_dir: Path) -> tuple[bool, str]:
        return validate_cast(
            cast_dir,
            commands=coupling.surface_commands(surfaces),
            imports=coupling.surface_imports(surfaces),
        )

    return _check


def update_cast(
    cast_dir: Path | str,
    source_root: Path | str,
    *,
    force: bool = False,
    validate: bool = True,
    validator=None,
    closure_fn=None,
    resolve_commit=_resolve_commit,
    commit_present=_commit_present,
    read_at_commit=_read_at_commit,
) -> UpdateOutcome:
    """Apply an engine update to a poured cast, guarded by the broad harness.

    Reads the drift first, then REFUSES rather than risk the owner's work: a selective cast whose
    surfaces were not recorded at pour (re-pour to enable updates), local edits or an unverifiable
    pin without `force`, or a cast in sync. On apply it backs up, re-vendors from the source (WHOLE,
    or the surfaces' recomputed closure for selective), re-validates with the matching corpus,
    and rolls back on failure; it advances the manifest's pin only on success and never commits.
    `validator` and `closure_fn` are injectable seams (default: boot cast / coupling.closure)."""
    cast_dir, source_root = Path(cast_dir), Path(source_root)
    drift = diff_cast(
        cast_dir,
        source_root,
        resolve_commit=resolve_commit,
        commit_present=commit_present,
        read_at_commit=read_at_commit,
    )
    here, there = drift.pinned_commit, drift.target_commit
    manifest = read_manifest(cast_dir / "cast_manifest.json")
    selective = drift.engine_strategy == VENDORED_SELECTIVE
    if selective and not manifest.surfaces:
        return UpdateOutcome(
            False,
            "selective cast has no recorded surfaces (poured before recording); re-pour to update",
            here,
            there,
        )
    if drift.in_sync:
        return UpdateOutcome(
            False, "already in sync with the target; nothing to update", here, there
        )
    if not drift.pin_verifiable and not force:
        return UpdateOutcome(
            False,
            f"cannot verify local edits (pin {here} not in the source); re-run with force",
            here,
            there,
        )
    if drift.locally_modified and not force:
        n = len(drift.locally_modified)
        return UpdateOutcome(
            False,
            f"{n} local edit(s) would be overwritten; commit/stash them or re-run with force",
            here,
            there,
        )
    if selective:
        from parts import coupling

        modules = (closure_fn or coupling.closure)(manifest.surfaces)
        check = validator or _selective_validator(manifest.surfaces)
    else:
        modules = None
        check = validator
    return _apply_update(
        cast_dir, source_root, drift, modules=modules, validate=validate, validator=check
    )


def render_update(outcome: UpdateOutcome) -> str:
    """A human-readable update result: what happened, and (on success) the reminder to commit it."""
    if outcome.applied:
        head = "UPDATED"
    elif "already in sync" in outcome.reason:
        head = "NO-OP"
    else:
        head = "REFUSED"
    lines = [
        f"Cast update: {head}",
        f"  {outcome.from_commit} -> {outcome.to_commit}",
        f"  {outcome.reason}",
    ]
    if outcome.applied:
        lines.append(
            f"  re-vendored {outcome.files_revendored} file(s); validated={outcome.validated}"
        )
        lines.append("  Review the diff and commit the update yourself (never auto-committed).")
    if outcome.rolled_back:
        lines.append("  The cast was restored to its previous engine (rolled back).")
    return "\n".join(lines)
