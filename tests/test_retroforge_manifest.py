"""Test twin for kernel/retroforge/manifest.py.

Acceptance: a manifest stamps this run's source checksum onto every asset it records, and reports
itself traceable.

Refusal (fail loud): an asset carrying a checksum from a DIFFERENT source makes the manifest
untraceable and it must say so. That is the whole property; a manifest that reported traceable
while holding a foreign asset would be a verdict over something never measured.
"""

from __future__ import annotations

from dataclasses import replace

from kernel.retroforge.artifact import RomArtifact
from kernel.retroforge.manifest import ExtractionManifest

ART = RomArtifact.from_bytes(b"NES\x1a" + bytes(60), source_path="fixture.nes")


def test_a_manifest_takes_its_identity_from_the_artifact() -> None:
    m = ExtractionManifest.for_artifact(ART)
    assert m.source_checksum == ART.checksum
    assert m.source_path == "fixture.nes"


def test_every_recorded_asset_carries_this_runs_checksum() -> None:
    """Duplicated onto each asset on purpose: assets travel, and one without provenance is the
    thing the manifest exists to prevent."""
    m = ExtractionManifest.for_artifact(ART)
    m.record("chr_bank_0", "tileset", offset=16, byte_length=8192, codec_id="nes.2bpp")
    m.record("chr_bank_1", "tileset", offset=8208, byte_length=8192, codec_id="nes.2bpp")
    assert [a.source_checksum for a in m.assets] == [ART.checksum, ART.checksum]
    assert m.traceable


def test_an_empty_manifest_is_vacuously_traceable() -> None:
    assert ExtractionManifest.for_artifact(ART).traceable


def test_an_asset_from_a_different_source_makes_the_manifest_untraceable() -> None:
    """The refusal that matters. Planted, so the property is shown able to fail."""
    m = ExtractionManifest.for_artifact(ART)
    m.record("chr_bank_0", "tileset", offset=16, byte_length=8192, codec_id="nes.2bpp")
    m.assets[0] = replace(m.assets[0], source_checksum="0" * 64)
    assert not m.traceable


def test_a_warning_is_recorded_rather_than_swallowed() -> None:
    m = ExtractionManifest.for_artifact(ART)
    m.warn("CHR RAM: no CHR ROM in this cartridge, tiles are generated at runtime")
    assert m.warnings == ["CHR RAM: no CHR ROM in this cartridge, tiles are generated at runtime"]
