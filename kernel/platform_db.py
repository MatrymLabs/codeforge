"""Compatibility exports for the single CodeForge archive database boundary.

SeedLab historically imported this module, while the live archive and Alembic migrations owned
``kernel.world.db``.  Keeping a second DeclarativeBase here created two competing metadata and
engine seams for the same tables.  This module remains as a compatibility import path for callers,
but the live archive is now the only owner of the SQLAlchemy models, URL, engine cache, and session
factory.
"""

from kernel.world.db import ArchiveBase as PlatformBase
from kernel.world.db import (
    AuditEventRow,
    SeedArtifactRow,
    SeedManifestEvidenceRow,
    SeedModelRow,
    SeedRegistryRow,
    SeedRunRow,
    SeedSourceRow,
    engine_url,
    open_archive_session,
)

__all__ = [
    "PlatformBase",
    "SeedRegistryRow",
    "SeedModelRow",
    "SeedRunRow",
    "SeedArtifactRow",
    "SeedManifestEvidenceRow",
    "SeedSourceRow",
    "AuditEventRow",
    "engine_url",
    "open_archive_session",
]
