"""CARD: retroforge.manifest -- what was extracted, from which bytes, by which codec.

The manifest is the traceability half of RetroForge. Tiles without it are pixels of unknown
origin; with it, every asset names its source checksum, its offset, and the codec that read it,
so a later reader can re-derive the same output or prove it cannot.

`source_checksum` is copied onto EVERY asset rather than held once at the top. That is deliberate
duplication: assets get split out of manifests, pasted into issues, and handed to other tools, and
an asset that travels without its provenance is the thing this file exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kernel.retroforge.artifact import RomArtifact


@dataclass(frozen=True)
class ExtractedAsset:
    """One thing pulled out of a ROM, carrying where it came from."""

    asset_id: str
    kind: str
    offset: int
    byte_length: int
    codec_id: str
    source_checksum: str
    notes: str = ""


@dataclass
class ExtractionManifest:
    """The record of one extraction run. Never holds ROM bytes, only where they were."""

    source_path: str
    source_checksum: str
    platform: str
    assets: list[ExtractedAsset] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def for_artifact(cls, artifact: RomArtifact) -> ExtractionManifest:
        return cls(
            source_path=artifact.source_path,
            source_checksum=artifact.checksum,
            platform=artifact.platform,
        )

    def record(
        self,
        asset_id: str,
        kind: str,
        offset: int,
        byte_length: int,
        codec_id: str,
        notes: str = "",
    ) -> ExtractedAsset:
        """File one asset against this run's source, stamping the checksum onto it."""
        asset = ExtractedAsset(
            asset_id=asset_id,
            kind=kind,
            offset=offset,
            byte_length=byte_length,
            codec_id=codec_id,
            source_checksum=self.source_checksum,
            notes=notes,
        )
        self.assets.append(asset)
        return asset

    def warn(self, message: str) -> None:
        """A named uncertainty. A manifest that hides a doubt is worse than one that has none."""
        self.warnings.append(message)

    @property
    def traceable(self) -> bool:
        """Every asset cites THIS run's source. False is a manifest that cannot be trusted."""
        return all(a.source_checksum == self.source_checksum for a in self.assets)
