"""CARD: feature_control -- the practical adapter for feature flags: an environment kill switch.

The reverse of parts/features: the SAME `FlagRegistry` core, but an environment variable overrides
the registered default (the 12-factor precedence: `FEATURE_<NAME>=true|false` wins). This is how a
service ships a kill switch or a canary flag without a redeploy. The environment mapping is
injected, so tests are deterministic (no real os.environ dependency).
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from parts.feature_flags import FlagRegistry

_TRUTHY = ("1", "true", "on", "yes")


class FeatureControl:
    """Runtime feature flags whose defaults an environment variable can override."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env: Mapping[str, str] = env if env is not None else os.environ
        self._registry = FlagRegistry()

    def register(self, name: str, default: bool = False, description: str = "") -> None:
        self._registry.register(name, default, description)

    def is_on(self, name: str) -> bool:
        """Env override (FEATURE_<NAME>) beats the registered default; unknown flag raises."""
        self._registry._require(name)  # loud on an unknown flag, before reading env
        env_key = f"FEATURE_{name.upper()}"
        if env_key in self._env:
            return self._env[env_key].strip().lower() in _TRUTHY
        return self._registry.is_on(name)

    def snapshot(self) -> dict[str, bool]:
        """The effective state of every flag, env overrides applied."""
        return {flag.name: self.is_on(flag.name) for flag in self._registry.all()}
