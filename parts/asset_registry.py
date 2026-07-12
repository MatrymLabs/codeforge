"""CARD: asset_registry -- the practical adapter for the repository: a records/asset registry.

The reverse of parts/logbook: the SAME `Repository` core stores business records instead of game
entries. An `AssetRegistry` registers, finds, updates, and retires assets by id, keeping domain code
(the registry API) independent of storage. Swap the in-memory repository for a database repository
later and this class does not change. Its cousins are stock control, a document registry, and any
records system.
"""

from __future__ import annotations

from dataclasses import dataclass

from parts.repository import InMemoryRepository, Repository


@dataclass(frozen=True)
class Asset:
    """One tracked asset: a stable id, a name, and a lifecycle status."""

    asset_id: str
    name: str
    status: str = "active"


class AssetRegistry:
    """Register, find, update, and retire assets. Storage-agnostic: any Repository works."""

    def __init__(self, repo: Repository[Asset, str] | None = None) -> None:
        self._repo: Repository[Asset, str] = repo or InMemoryRepository(lambda a: a.asset_id)

    def register(self, asset: Asset) -> Asset:
        """Add a new asset (raises DuplicateKey if the id already exists)."""
        return self._repo.add(asset)

    def find(self, asset_id: str) -> Asset | None:
        return self._repo.get(asset_id)

    def retire(self, asset_id: str) -> Asset:
        """Mark an asset retired (raises NotFound if absent)."""
        asset = self._repo.require(asset_id)
        return self._repo.update(Asset(asset.asset_id, asset.name, status="retired"))

    def all(self) -> list[Asset]:
        return self._repo.list()

    def count(self) -> int:
        return self._repo.count()
