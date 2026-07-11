"""CARD: stats -- validated, immutable character statistics.

Salvaged from codeforge_mk1 (the Evennia-era kernel). A Stat that
exists is guaranteed valid; a StatBlock is guaranteed coherent; a
StatModifier derives values without ever mutating a Stat.

Kernel rule preserved from mk1: this module imports nothing from
the engine. Pure schema, pure logic, fully portable.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Stat:
    """An immutable, validated stat block.

    A Stat that exists is guaranteed valid: name is non-empty,
    bounds are sane, and base lies within them.
    """

    name: str
    base: int
    min_value: int = 0
    max_value: int = 100

    def __post_init__(self) -> None:
        if not isinstance(self.base, int):
            raise ValueError("base must be an integer")
        if not self.name or not self.name.strip():
            raise ValueError("Stat name must be a non-empty string")
        if self.min_value > self.max_value:
            raise ValueError(
                f"min_value ({self.min_value}) cannot exceed max_value ({self.max_value})"
            )
        if not (self.min_value <= self.base <= self.max_value):
            raise ValueError(
                f"base ({self.base}) must be within [{self.min_value}, {self.max_value}]"
            )


@dataclass(frozen=True)
class StatBlock:
    """An immutable collection of Stats with unique names.

    A StatBlock that exists is guaranteed coherent: every member
    is a valid Stat, and no two members share a name.
    """

    stats: tuple[Stat, ...]

    def __post_init__(self) -> None:
        for s in self.stats:
            if not isinstance(s, Stat):
                raise ValueError(f"StatBlock members must be Stat, got {type(s).__name__}")
        names = [s.name for s in self.stats]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"duplicate stat names: {sorted(duplicates)}")

    def get(self, name: str) -> Stat:
        """Return the Stat with this name, or raise KeyError."""
        for s in self.stats:
            if s.name == name:
                return s
        raise KeyError(f"no stat named {name!r}")


@dataclass(frozen=True)
class StatModifier:
    """A flat and/or percentage adjustment applied to a Stat.

    percent applies to the stat's base, not to base + flat.
    Results are clamped to the stat's own [min_value, max_value].
    """

    source: str
    flat: int = 0
    percent: float = 0.0

    def __post_init__(self) -> None:
        if not self.source or not self.source.strip():
            raise ValueError("source must be a non-empty string")
        if not isinstance(self.flat, int) or isinstance(self.flat, bool):
            raise ValueError("flat must be an integer")
        if not isinstance(self.percent, (int, float)) or isinstance(self.percent, bool):
            raise ValueError("percent must be a number")

    def apply(self, stat: Stat) -> int:
        """Return the modified effective value, clamped to the stat's bounds."""
        raw = stat.base + self.flat + round(stat.base * self.percent)
        return max(stat.min_value, min(stat.max_value, raw))


_STACK_MODES = ("additive", "compound")


@dataclass(frozen=True)
class ModifierStack:
    """Many StatModifiers applied as one, by an explicitly chosen strategy (salvaged mk1 kernel).

    Two order-independent modes, neither a hidden default of the other:
      additive: base + sum(flats) + round(base * sum(percents))
      compound: round((base + sum(flats)) * product(1 + percent))

    This is the primitive equipment, status effects, and job perks all use to bend derived
    stats: gather the sources' modifiers, stack them, apply once. Pure -- it never mutates a Stat.
    """

    modifiers: tuple[StatModifier, ...] = ()
    mode: str = "additive"

    def __post_init__(self) -> None:
        if self.mode not in _STACK_MODES:
            raise ValueError(f"mode must be one of {_STACK_MODES}, got {self.mode!r}")
        for m in self.modifiers:
            if not isinstance(m, StatModifier):
                raise ValueError(
                    f"ModifierStack members must be StatModifier, got {type(m).__name__}"
                )

    def apply(self, stat: Stat) -> int:
        """Return the combined effective value, clamped to the stat's bounds."""
        total_flat = sum(m.flat for m in self.modifiers)
        if self.mode == "additive":
            percent = sum(m.percent for m in self.modifiers)
            raw = stat.base + total_flat + round(stat.base * percent)
        else:
            factor = math.prod(1 + m.percent for m in self.modifiers)
            raw = round((stat.base + total_flat) * factor)
        return max(stat.min_value, min(stat.max_value, raw))
