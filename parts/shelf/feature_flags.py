"""CARD: feature_flags -- toggle features at runtime without a redeploy: flags with precedence.

Register named flags with a default; enable, disable, or reset them at runtime; ask `is_on`. An
override beats the default (the precedence); resetting returns to the default; retiring removes the
flag entirely. An unknown flag is an error, never silently off. `snapshot` gives the reproducible
current state. This is the standard feature-flag pattern (LaunchDarkly-style), reimplemented from
the concept -- no code copied.

Framework-free and deterministic: no I/O, no clock. One core, two lives: an in-world feature panel
in the game (`parts/features`) and an environment-driven kill switch in a practical app
(`parts/feature_control`).

Provenance: independently_implemented_pattern (feature flags / toggles). No code copied.
"""

from __future__ import annotations

from dataclasses import dataclass


class FeatureFlagError(ValueError):
    """A flag was registered twice, or an unknown flag was asked about. Fails loud."""


@dataclass(frozen=True)
class Flag:
    """A registered flag: its name, its default state, and a description."""

    name: str
    default: bool
    description: str = ""


class FlagRegistry:
    """A registry of named flags. Overrides beat defaults; unknown flags are an error."""

    def __init__(self) -> None:
        self._flags: dict[str, Flag] = {}
        self._overrides: dict[str, bool] = {}

    def register(self, name: str, default: bool = False, description: str = "") -> None:
        """Register a flag. Raises FeatureFlagError on a duplicate name."""
        if name in self._flags:
            raise FeatureFlagError(f"a flag named {name!r} is already registered")
        self._flags[name] = Flag(name, default, description)

    def _require(self, name: str) -> None:
        if name not in self._flags:
            raise FeatureFlagError(f"unknown flag {name!r}")

    def is_on(self, name: str) -> bool:
        """Whether the flag is on now (override if set, else the default). Unknown flag raises."""
        self._require(name)
        return self._overrides.get(name, self._flags[name].default)

    def enable(self, name: str) -> None:
        self._require(name)
        self._overrides[name] = True

    def disable(self, name: str) -> None:
        self._require(name)
        self._overrides[name] = False

    def reset(self, name: str) -> None:
        """Drop any override, returning the flag to its registered default."""
        self._require(name)
        self._overrides.pop(name, None)

    def retire(self, name: str) -> None:
        """Remove a flag entirely (flag retirement)."""
        self._require(name)
        del self._flags[name]
        self._overrides.pop(name, None)

    def snapshot(self) -> dict[str, bool]:
        """The reproducible current state: every flag name to its effective value, sorted."""
        return {name: self.is_on(name) for name in sorted(self._flags)}

    def all(self) -> list[Flag]:
        return list(self._flags.values())
