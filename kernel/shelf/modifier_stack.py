"""CARD: modifier_stack -- fold add/multiply modifiers (sources, stacking, conditions) onto a stat.

The keystone Evennia harvest. codeforge's derived.py:12 openly defers "the modifier stack (a later
batch)", and afflictions.py is HP-only, so equipment/buff/status modifiers are scattered as inline
flags with no unified fold. Harvested clean-room (pattern-not-code) from Evennia's rpg/buffs
BuffHandler + Mod pipeline (BSD-3-Clause): the reusable primitive that folds many modifiers onto one
base value, honoring source-tracking (for stacking + targeted removal) and conditional application.

The canonical RPG fold: final = (base + sum(add*stacks)) * product(mult**stacks), over the mods that
target the stat and whose condition passes. STATE IS CANONICAL, VALUE IS A PROJECTION: `resolve`
never mutates; the Stack is frozen + copy-on-write. Lifecycle hooks (at_apply/at_expire) and event
triggers are a consumer concern left to adoption; this is the pure math core. Clean-room, stdlib
only.

  Mod(stat, op, value, source, stacks, condition) ; Stack.add/remove_by_source ; resolve(base, stat)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

ADD = "add"
MULT = "mult"
_OPS = frozenset({ADD, MULT})


class ModifierError(ValueError):
    """Raised loud and early on a bad op, non-positive stacks, or a blank stat/source label."""


@dataclass(frozen=True)
class Mod:
    """One modifier on one stat. `op` ADD contributes `value*stacks` to the additive sum; `op` MULT
    contributes a factor of `value**stacks` to the multiplicative product. `source` groups mods for
    stacking and targeted removal (e.g. "rusty_sword", "poison"). `condition`, if set, gates the mod
    on a context (only applies when condition(ctx) is truthy)."""

    stat: str
    op: str
    value: float
    source: str = ""
    stacks: int = 1
    condition: Callable[[Any], bool] | None = None

    def __post_init__(self) -> None:
        if not self.stat or not self.stat.strip():
            raise ModifierError("stat cannot be blank")
        if self.op not in _OPS:
            raise ModifierError(f"op must be one of {sorted(_OPS)} (got {self.op!r})")
        if self.stacks < 1:
            raise ModifierError(f"stacks must be >= 1 (got {self.stacks})")

    def applies(self, ctx: Any) -> bool:
        """Whether this mod is active for `ctx` (True when there is no condition)."""
        return True if self.condition is None else bool(self.condition(ctx))


@dataclass(frozen=True)
class Stack:
    """The canonical set of active modifiers. Frozen + copy-on-write: add/remove return a NEW Stack,
    so resolving a value can never change the world."""

    mods: tuple[Mod, ...] = ()

    def add(self, mod: Mod) -> Stack:
        """A new Stack with `mod` appended."""
        return replace(self, mods=(*self.mods, mod))

    def remove_by_source(self, source: str) -> Stack:
        """A new Stack with every mod from `source` removed (idempotent: unknown -> unchanged)."""
        if not source:
            raise ModifierError("source cannot be blank for removal")
        kept = tuple(m for m in self.mods if m.source != source)
        return self if len(kept) == len(self.mods) else replace(self, mods=kept)

    def sources(self) -> tuple[str, ...]:
        """The distinct non-blank sources present, in first-seen order (for inspection/UI)."""
        seen: dict[str, None] = {}
        for m in self.mods:
            if m.source:
                seen.setdefault(m.source, None)
        return tuple(seen)


def resolve(base: float, mods: Stack | tuple[Mod, ...], stat: str, *, ctx: Any = None) -> float:
    """Fold the mods targeting `stat` onto `base`: (base + sum add*stacks) * product mult**stacks.

    Only mods whose stat matches AND whose condition passes for `ctx` contribute. With no matching
    mods, returns `base` unchanged. Pure: no mutation of the Stack or its Mods."""
    if not stat or not stat.strip():
        raise ModifierError("stat cannot be blank")
    active = mods.mods if isinstance(mods, Stack) else tuple(mods)
    additive = 0.0
    multiplicative = 1.0
    for m in active:
        if m.stat != stat or not m.applies(ctx):
            continue
        if m.op == ADD:
            additive += m.value * m.stacks
        else:  # MULT
            multiplicative *= m.value**m.stacks
    return (base + additive) * multiplicative


@dataclass(frozen=True)
class Breakdown:
    """An auditable explanation of a resolve: the base, the additive total, the multiply factor,
    the final, and the per-source contributions (so a UI can show WHY a stat is what it is)."""

    base: float
    additive: float
    multiplier: float
    final: float
    contributions: tuple[tuple[str, float], ...] = field(default_factory=tuple)


def explain(base: float, mods: Stack | tuple[Mod, ...], stat: str, *, ctx: Any = None) -> Breakdown:
    """Like `resolve`, but return a Breakdown naming each contributing source (evidence, not a bare
    number). Honesty aid for the derived-stat surface: never quote a stat without its provenance."""
    if not stat or not stat.strip():
        raise ModifierError("stat cannot be blank")
    active = mods.mods if isinstance(mods, Stack) else tuple(mods)
    additive = 0.0
    multiplicative = 1.0
    contribs: list[tuple[str, float]] = []
    for m in active:
        if m.stat != stat or not m.applies(ctx):
            continue
        if m.op == ADD:
            amount = m.value * m.stacks
            additive += amount
            contribs.append((m.source or "(anon)", amount))
        else:
            multiplicative *= m.value**m.stacks
            contribs.append((m.source or "(anon)", m.value**m.stacks))
    final = (base + additive) * multiplicative
    return Breakdown(base, additive, multiplicative, final, tuple(contribs))
