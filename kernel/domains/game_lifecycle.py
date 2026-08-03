"""CARD: game_lifecycle -- prove a linked game region survives loss and restart: create -> backup ->
restore -> verify, so a generated world is not just emitted but DURABLE.

North Star Priority #4: state surviving restart. game_linker (MOD-10.085) emits a region (rooms, and
an optional quest arc) as canonical seed content; this proves that content is a real, recoverable
Seed. The check mirrors backup.py's philosophy (survive LOSS, not just restart, via a hash-verified
snapshot) at the generated-content level, composing the Linker with the engine's own loaders --
nothing is asserted that the live loaders don't confirm:

  * `snapshot(linked)` -- the BACKUP: each emitted file's sha256 (its canonical bytes).
  * `verify_recovery(linked, snap)`  -- the RESTORE + VERIFY: re-read the files from disk, re-hash
    against the snapshot, and re-validate through the real loader. RECOVERED (every file byte-
    identical AND the region still boots LINKED) / CORRUPTED (a file is missing, its bytes changed,
    or the recovered content no longer links).
  * `prove_lifecycle(spec, dest)` -- the whole loop: CREATE (link) -> VALIDATE (must be LINKED, else
    REFUSED) -> BACKUP -> RESTORE + VERIFY. A verdict word, never a false RECOVERED.

Scope, stated honestly: this proves the WORLD CONTENT (the Seed's canonical, durable state)
survives. The OPERATE half -- a live player travelling the region and advancing the quest -- runs
through the engine's GLOBAL quest registry (kernel.world.quest), which has no clean per-region
teardown today; persisting a live player's in-flight progress across restart is a separate
integration, deferred rather than faked here.

Grammar before worlds: lives in kernel/domains/ (world-aware); kernel/seedlab imports no world or
domain (import-linter `grammar-before-worlds`). Verdicts, not booleans. Status: PROTOTYPED (see
docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kernel.domains.game_linker import (
    LINKED,
    GameSpec,
    LinkedRegion,
    RegionVerdict,
    _sha256,
    link_and_validate,
    validate_region,
)

# --- recovery verdict words (a distinct vocabulary: "did the region come back whole?") ---------
RECOVERED = "recovered"  # every file returned byte-identical AND the region still boots (LINKED)
CORRUPTED = "corrupted"  # a file is missing, its bytes changed, or the content no longer links
REFUSED = "refused"  # the region did not link in the first place: there is nothing to prove


@dataclass(frozen=True)
class LifecycleReport:
    """The honest verdict on one CREATE -> BACKUP -> RESTORE -> VERIFY run of a linked region."""

    verdict: str
    region: str = ""
    files: tuple[str, ...] = ()  # the durable files backed up and verified byte-identical
    detail: str = ""  # why, when not RECOVERED

    @property
    def ok(self) -> bool:
        return self.verdict == RECOVERED


def snapshot(linked: LinkedRegion) -> dict[str, str]:
    """BACKUP: the region's durable fingerprint -- each file's sha256 (its canonical bytes)."""
    return dict(linked.checksums)


def verify_recovery(linked: LinkedRegion, snap: dict[str, str]) -> LifecycleReport:
    """RESTORE + VERIFY: re-read the emitted files from disk, re-hash against the backup, and
    re-validate through the real loader. RECOVERED when every file is byte-identical and the region
    still boots (LINKED); CORRUPTED on a missing file, a changed byte, or content that no longer
    links off its own recovered bytes."""
    dest = Path(linked.dest)
    for rel, digest in snap.items():
        path = dest / rel
        if not path.exists():
            return LifecycleReport(CORRUPTED, linked.region, detail=f"missing after restore: {rel}")
        if _sha256(path.read_text(encoding="utf-8")) != digest:
            return LifecycleReport(CORRUPTED, linked.region, detail=f"bytes changed: {rel}")
    revalidated: RegionVerdict = validate_region(linked)
    if revalidated.verdict != LINKED:
        return LifecycleReport(
            CORRUPTED,
            linked.region,
            detail=f"recovered content no longer links: {revalidated.verdict}",
        )
    return LifecycleReport(RECOVERED, linked.region, files=tuple(sorted(snap)))


def prove_lifecycle(spec: GameSpec, dest: Path) -> LifecycleReport:
    """The whole loop: CREATE (link) -> VALIDATE (must be LINKED) -> BACKUP (snapshot) -> RESTORE +
    VERIFY (re-read, re-hash, re-validate). REFUSED if the region never linked (nothing to prove);
    CORRUPTED if the content did not survive whole; RECOVERED when it comes back byte-identical and
    still boots."""
    linked, verdict = link_and_validate(spec, dest)
    if verdict.verdict != LINKED:
        return LifecycleReport(
            REFUSED, spec.region, detail=f"region did not link ({verdict.verdict}): {verdict.error}"
        )
    return verify_recovery(linked, snapshot(linked))
