"""CARD: hosted_recovery -- prove an INSTALLED World Package survives loss and restart: install ->
backup -> restore -> verify, over the WHOLE seed (rooms + quest + the world.yaml MANIFEST), the
restorable half of North Star #5.

game_lifecycle (MOD-10.086) proves the region CONTENT (rooms + quest) is durable, but it stops
at the Linker's output; it never sees the `world.yaml` manifest that hosted_world (MOD-10.090)
adds to make a region a bootable, IDENTIFIED World Package. If backup/restore drops or mangles the
manifest, the region content could survive while the world no longer boots (no id, no declared
spawn). This proves the thing the server actually hosts: the installed seed dir, manifest and all:

  * `snapshot_seed(seed_dir)` -- the BACKUP: sha256 of EVERY file in the installed seed dir, keyed
    by its path relative to the seed dir. It globs the whole directory, so a file that vanishes on
    restore is caught, not just the ones we happened to expect.
  * `verify_seed_recovery(seed_name, blueprint_root, snap)` -- the RESTORE + VERIFY: re-read every
    backed-up file, re-hash against the snapshot, then re-validate the seed's IDENTITY through the
    engine's OWN manifest gates (`describe_world` must not fail, `check_world` must find the
    declared spawn consistent with the real first room). RECOVERED (every file byte-identical AND
    the world's identity holds) / CORRUPTED (a file missing, a byte changed, a manifest now invalid,
    or the declared spawn no longer matches). It is a general restore-verifier: it judges a backup
    on its own merits, so a seed whose manifest was never valid is caught too, not trusted.
  * `prove_hosted_recovery(spec, blueprint_root, *, seed_name=, title=)` -- the whole loop: INSTALL
    (hosted_world) -> require HOSTABLE (else REFUSED, nothing to prove) -> BACKUP -> RESTORE+VERIFY.

Byte-identity is the durability guarantee: install_world already validated the content LINKED and
the identity HOSTABLE, so content that returns byte-identical still links, and the manifest re-check
confirms the bootable identity came back whole. Verdicts, not booleans.

Grammar before worlds: lives in kernel/domains/ (world-aware), composing hosted_world +
kernel.world.world_manifest; kernel/seedlab imports neither (import-linter `grammar-before-worlds`).
Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kernel.domains.game_lifecycle import CORRUPTED, RECOVERED, REFUSED
from kernel.domains.game_linker import GameSpec, _sha256
from kernel.domains.hosted_world import HOSTABLE, install_world
from kernel.world.seed import BLUEPRINTS_ROOT

# CORRUPTED / RECOVERED / REFUSED reuse game_lifecycle's recovery vocabulary: "did it come back
# whole?" is the same question, one layer up (the installed package, not just the region content).


@dataclass(frozen=True)
class HostedRecoveryReport:
    """The honest verdict on one INSTALL -> BACKUP -> RESTORE -> VERIFY run of a World Package."""

    verdict: str
    seed_name: str = ""
    files: tuple[str, ...] = ()  # every seed file backed up and verified byte-identical
    detail: str = ""  # why, when not RECOVERED

    @property
    def ok(self) -> bool:
        return self.verdict == RECOVERED


def _blueprint_root(root: Path) -> Path:
    resolver_root = BLUEPRINTS_ROOT.parents[1]
    return (
        BLUEPRINTS_ROOT
        if root == resolver_root
        else root / BLUEPRINTS_ROOT.relative_to(resolver_root)
    )


def snapshot_seed(seed_dir: Path) -> dict[str, str]:
    """BACKUP: the installed seed's durable fingerprint -- each file's sha256 (its canonical bytes),
    keyed by path relative to the seed dir. Globs the whole directory so nothing is silently
    dropped: rooms.yaml, quest.yaml, AND the world.yaml manifest are all covered."""
    seed_dir = Path(seed_dir)
    snap: dict[str, str] = {}
    for path in sorted(seed_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(seed_dir).as_posix()
            snap[rel] = _sha256(path.read_text(encoding="utf-8"))
    return snap


def verify_seed_recovery(
    seed_name: str, blueprint_root: Path, snap: dict[str, str]
) -> HostedRecoveryReport:
    """RESTORE + VERIFY: re-read every backed-up file, re-hash against the snapshot, then re-check
    the seed's identity through the engine's OWN manifest gates. RECOVERED when every file is byte-
    identical AND the world's identity holds (`describe_world` succeeds, `check_world` finds the
    declared spawn consistent); CORRUPTED on a missing file, a changed byte, an invalid manifest, or
    a spawn that no longer matches. A general restore-verifier: it trusts nothing it cannot re-check
    against the live engine."""
    blueprint_root = Path(blueprint_root)
    seed_dir = _blueprint_root(blueprint_root) / seed_name
    for rel, digest in snap.items():
        path = seed_dir / rel
        if not path.exists():
            return HostedRecoveryReport(
                CORRUPTED, seed_name, detail=f"missing after restore: {rel}"
            )
        if _sha256(path.read_text(encoding="utf-8")) != digest:
            return HostedRecoveryReport(CORRUPTED, seed_name, detail=f"bytes changed: {rel}")

    # Re-validate the bootable IDENTITY through the engine's own gates -- the manifest half that
    # game_lifecycle never sees. A backup can carry a manifest that was never valid; catch it.
    from kernel.world.world_manifest import WorldManifestError, check_world, describe_world # noqa: I001

    try:
        describe_world(seed_name, root=blueprint_root)
    except WorldManifestError as exc:
        return HostedRecoveryReport(CORRUPTED, seed_name, detail=f"manifest no longer valid: {exc}")
    problems = check_world(seed_name, root=blueprint_root)
    if problems:
        return HostedRecoveryReport(
            CORRUPTED, seed_name, detail=f"declared spawn inconsistent: {'; '.join(problems)}"
        )
    return HostedRecoveryReport(RECOVERED, seed_name, files=tuple(sorted(snap)))


def prove_hosted_recovery(
    spec: GameSpec,
    blueprint_root: Path,
    *,
    seed_name: str = "",
    title: str = "",
) -> HostedRecoveryReport:
    """The whole loop: INSTALL the region as a World Package (hosted_world) -> require HOSTABLE
    (else REFUSED: there is no bootable world to prove) -> BACKUP the whole seed -> RESTORE+VERIFY.
    Never a false RECOVERED: it re-reads and re-validates through the engine's own gates."""
    world = install_world(spec, blueprint_root, seed_name=seed_name, title=title)
    if world.verdict != HOSTABLE:
        return HostedRecoveryReport(
            REFUSED,
            world.seed_name,
            detail=f"world is not hostable ({world.verdict}): {'; '.join(world.problems)}",
        )
    snap = snapshot_seed(Path(world.seed_dir))
    return verify_seed_recovery(world.seed_name, blueprint_root, snap)
