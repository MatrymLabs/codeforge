"""CARD: context_selector -- rank items by weighted signals; select the best within a budget.

Clean-room from the Nature-Inspired research (the "context ROI selector": rank the
few files / modules / symbols worth deep analysis before expensive LLM reasoning or
retrieval, RS-2026-07-11-nature p.6,11). Feeding a model everything is waste and
noise; this scores each candidate by weighted signals (name match, dependency
centrality, recency, ...) and greedily selects the highest-value items that fit a
budget (a count or a token/size cost). Generic: the consumer supplies the signals
and the weights, so the same part focuses an LLM prompt, a retrieval set, or a
review scope.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


class ContextError(ValueError):
    """Raised on a malformed item, weight set, or budget."""


@dataclass(frozen=True)
class Item:
    """A candidate for inclusion: an id, a cost (tokens/size), and its signal values."""

    id: str
    signals: Mapping[str, float]
    cost: int = 1

    def __post_init__(self) -> None:
        if not self.id:
            raise ContextError("item id must be non-empty")  # noqa: TRY003
        if self.cost <= 0:
            raise ContextError(f"item {self.id!r} cost must be > 0")  # noqa: TRY003


@dataclass(frozen=True)
class Selection:
    """The chosen items plus the budget accounting."""

    items: tuple[Item, ...]
    total_cost: int
    considered: int
    dropped: tuple[str, ...] = field(default_factory=tuple)


def score(item: Item, weights: Mapping[str, float]) -> float:
    """The weighted sum of an item's signals (unknown signals contribute 0)."""
    return sum(weight * item.signals.get(name, 0.0) for name, weight in weights.items())


def select(
    items: list[Item],
    weights: Mapping[str, float],
    *,
    max_items: int | None = None,
    max_cost: int | None = None,
) -> Selection:
    """Greedily select the highest-scoring items that fit the budget.

    Provide at least one of max_items / max_cost. Items are ranked by score
    (descending), ties broken by id for determinism, then taken in order while the
    running count and cost stay within budget. An item too costly to ever fit is
    skipped (not a blocker), so a smaller item behind it can still be chosen.
    """
    if not weights:
        raise ContextError("weights must be non-empty")  # noqa: TRY003
    if max_items is None and max_cost is None:
        raise ContextError("provide at least one of max_items / max_cost")  # noqa: TRY003
    if max_items is not None and max_items <= 0:
        raise ContextError("max_items must be > 0")  # noqa: TRY003
    if max_cost is not None and max_cost <= 0:
        raise ContextError("max_cost must be > 0")  # noqa: TRY003

    ranked = sorted(items, key=lambda it: (-score(it, weights), it.id))
    chosen: list[Item] = []
    dropped: list[str] = []
    total = 0
    for item in ranked:
        if max_items is not None and len(chosen) >= max_items:
            dropped.append(item.id)
            continue
        if max_cost is not None and total + item.cost > max_cost:
            dropped.append(item.id)  # does not fit; a cheaper later item still can
            continue
        chosen.append(item)
        total += item.cost
    return Selection(tuple(chosen), total, len(items), tuple(dropped))
