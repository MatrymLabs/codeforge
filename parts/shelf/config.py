"""CARD: config -- one typed, validated view of CodeForge's environment.

The environment is read in many modules (each resolves its own var at call time, on
purpose, so tests can monkeypatch it). This is the CATALOG: a single Pydantic model that
names every knob, types it, validates it, and renders it -- credentials redacted. It proves
typed, validated configuration (a recurring hiring ask) without destabilizing the per-module
resolvers. `Settings.load()` fails loud on a bad value (a non-numeric PORT, an out-of-range
port) instead of surfacing a raw crash deep in a driver.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ConfigError(ValueError):
    """A malformed environment value: fail loud at the catalog, not deep in a driver."""


def _redact_url(url: str) -> str:
    """Show a connection string's scheme and host, never its embedded credentials."""
    if not url:
        return "(unset -> SQLite default)"
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    host = rest.split("@", 1)[1] if "@" in rest else rest  # drop user:pass@
    return f"{scheme}://[redacted]@{host}" if "@" in rest else f"{scheme}://{host}"


class Settings(BaseModel):
    """The typed environment. Frozen: settings are read once and never mutated in place."""

    model_config = ConfigDict(frozen=True)

    port: int = Field(default=8000, ge=1, le=65535)
    architect_brain: Literal["local", "claude"] = "local"
    database_url: str = ""  # empty -> the SQLite default (see parts/db.py)
    codeforge_db: str = ""  # empty -> repo-root default path
    seed: str = ""  # empty -> the default seed
    anthropic_key_present: bool = False

    @classmethod
    def load(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Read and validate the environment. A bad value raises ConfigError, loud and named."""
        e = os.environ if env is None else env
        # architect.py treats only "claude" specially; mirror that so an odd value never crashes.
        brain: Literal["local", "claude"] = (
            "claude" if e.get("CODEFORGE_ARCHITECT", "").strip().lower() == "claude" else "local"
        )
        try:
            return cls(
                port=e.get("PORT", "8000") or "8000",  # type: ignore[arg-type]  # pydantic coerces str->int
                architect_brain=brain,
                database_url=e.get("DATABASE_URL", "").strip(),
                codeforge_db=e.get("CODEFORGE_DB", "").strip(),
                seed=e.get("FORGE_SEED", "").strip(),
                anthropic_key_present=bool(e.get("ANTHROPIC_API_KEY", "").strip()),
            )
        except ValidationError as exc:
            raise ConfigError(f"invalid environment: {exc}") from exc

    def render(self) -> str:
        """A human view of the effective config, credentials redacted (the `config` program)."""
        return "\n".join(
            [
                "CONFIGURATION - typed + validated (pydantic)",
                "",
                f"  port            : {self.port}",
                f"  architect_brain : {self.architect_brain}",
                f"  database_url    : {_redact_url(self.database_url)}",
                f"  codeforge_db    : {self.codeforge_db or '(unset -> repo-root default)'}",
                f"  seed            : {self.seed or '(default)'}",
                f"  anthropic_key   : {'present' if self.anthropic_key_present else 'absent'}",
                "",
                "  Secrets are never shown here; the key is reported present/absent only.",
            ]
        )


def render_config() -> str:
    """The `config` terminal program: display the current settings. A read-only view must
    not crash on a bad ambient value -- it surfaces the problem honestly. (The server entry
    point uses Settings.load() directly, so it still fails loud on a bad port.)"""
    try:
        return Settings.load().render()
    except ConfigError as exc:
        return f"CONFIGURATION - INVALID ENVIRONMENT\n\n  {exc}\n\n  Fix the value and retry."
