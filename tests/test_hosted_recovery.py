"""Test twin for kernel/domains/hosted_recovery.py -- prove an INSTALLED World Package survives loss
and restart, manifest included (North Star #5, the restorable half).

Acceptance: a hosted world (rooms + quest + a world.yaml manifest) comes back byte-identical AND its
identity still holds through the engine's own gates -> RECOVERED, and the manifest is covered (the
whole point vs game_lifecycle, which stops at the region content).

Refusal (fail loud): a dropped file, a changed byte, an invalid manifest, or a declared spawn that
no longer matches the seed's first room are each CORRUPTED, surfaced not hidden; a world that never
installed HOSTABLE is REFUSED.
"""

from __future__ import annotations

from pathlib import Path

from kernel.domains.game_lifecycle import CORRUPTED, RECOVERED, REFUSED
from kernel.domains.game_linker import GameSpec, RoomSpec
from kernel.domains.hosted_recovery import (
    HostedRecoveryReport,
    prove_hosted_recovery,
    snapshot_seed,
    verify_seed_recovery,
)
from kernel.domains.hosted_world import install_world
from kernel.domains.journey import journey_region


def test_an_installed_world_survives_backup_and_restore(tmp_path: Path) -> None:
    spec = journey_region("veridia", ["greenhold", "riverside", "summit"])
    report = prove_hosted_recovery(spec, tmp_path)
    assert report.verdict == RECOVERED and report.ok is True
    assert report.seed_name == "veridia"


def test_recovery_covers_the_manifest_not_just_the_region(tmp_path: Path) -> None:
    # The whole point vs game_lifecycle: the world.yaml MANIFEST is backed up and verified too.
    report = prove_hosted_recovery(journey_region("veridia", ["greenhold", "summit"]), tmp_path)
    assert report.verdict == RECOVERED
    assert "world.yaml" in report.files
    assert "rooms.yaml" in report.files and "quest.yaml" in report.files


def test_snapshot_fingerprints_files_only_not_directories(tmp_path: Path) -> None:
    world = install_world(journey_region("veridia", ["greenhold"]), tmp_path)
    (Path(world.seed_dir) / "sub").mkdir()  # a directory in the seed dir is not content
    snap = snapshot_seed(Path(world.seed_dir))
    assert "sub" not in snap  # only files are fingerprinted, never directories
    assert "world.yaml" in snap and "rooms.yaml" in snap


def test_a_dropped_file_after_restore_is_corrupted(tmp_path: Path) -> None:
    world = install_world(journey_region("veridia", ["greenhold", "summit"]), tmp_path)
    snap = snapshot_seed(Path(world.seed_dir))
    (Path(world.seed_dir) / "quest.yaml").unlink()  # a file vanishes on restore
    report = verify_seed_recovery("veridia", tmp_path, snap)
    assert report.verdict == CORRUPTED and "missing after restore" in report.detail


def test_a_changed_byte_after_restore_is_corrupted(tmp_path: Path) -> None:
    world = install_world(journey_region("veridia", ["greenhold", "summit"]), tmp_path)
    snap = snapshot_seed(Path(world.seed_dir))
    manifest = Path(world.seed_dir) / "world.yaml"
    manifest.write_text(manifest.read_text() + "\n# tampered\n", encoding="utf-8")
    report = verify_seed_recovery("veridia", tmp_path, snap)
    assert report.verdict == CORRUPTED and "bytes changed" in report.detail


# --- verify_seed_recovery as a general restore-verifier: it re-validates identity through the
# engine's OWN manifest gates, so a backup whose manifest is invalid (or whose declared spawn no
# longer matches the seed) is caught even when every byte is unchanged. --------------------------


def test_an_invalid_manifest_is_corrupted_even_if_unchanged(tmp_path: Path) -> None:
    seed_dir = tmp_path / "content" / "blueprints" / "veridia"
    seed_dir.mkdir(parents=True)
    (seed_dir / "rooms.yaml").write_text("trailhead:\n", encoding="utf-8")
    # A world.yaml with an invalid world_id (uppercase) -- describe_world fails loud.
    (seed_dir / "world.yaml").write_text(
        "world_id: Bad_ID\ntitle: Veridia\nstart_room: trailhead\n", encoding="utf-8"
    )
    snap = snapshot_seed(seed_dir)  # the backup faithfully carries the invalid manifest
    report = verify_seed_recovery("veridia", tmp_path, snap)
    assert report.verdict == CORRUPTED and "manifest no longer valid" in report.detail


def test_a_stale_declared_spawn_is_corrupted(tmp_path: Path) -> None:
    seed_dir = tmp_path / "content" / "blueprints" / "veridia"
    seed_dir.mkdir(parents=True)
    (seed_dir / "rooms.yaml").write_text("trailhead:\nsummit:\n", encoding="utf-8")
    # A valid manifest, but its declared spawn is NOT the seed's first room -> check_world flags it.
    (seed_dir / "world.yaml").write_text(
        "world_id: veridia\ntitle: Veridia\nstart_room: summit\n", encoding="utf-8"
    )
    snap = snapshot_seed(seed_dir)
    report = verify_seed_recovery("veridia", tmp_path, snap)
    assert report.verdict == CORRUPTED and "declared spawn inconsistent" in report.detail


def test_a_world_that_never_installed_is_refused(tmp_path: Path) -> None:
    # A region that does not link never becomes HOSTABLE: there is no world to prove recoverable.
    broken = GameSpec(
        region="broken", start="gate", rooms=(RoomSpec(label="gate", exits={"north": "nowhere"}),)
    )
    report: HostedRecoveryReport = prove_hosted_recovery(broken, tmp_path)
    assert report.verdict == REFUSED and "not hostable" in report.detail
