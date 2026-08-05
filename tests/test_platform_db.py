"""The generic platform SQL boundary has a direct aggregate twin."""

from __future__ import annotations

from pathlib import Path

from kernel.platform_db import PlatformBase, engine_url
from kernel.world.db import ArchiveBase


def test_platform_db_uses_the_platform_owned_base(monkeypatch, tmp_path: Path) -> None:
    database = tmp_path / "platform.db"
    monkeypatch.setenv("CODEFORGE_DB", str(database))
    assert engine_url() == f"sqlite:///{database}"
    assert PlatformBase.metadata.tables["seed_registry"].name == "seed_registry"
    assert PlatformBase is ArchiveBase
