"""CARD: resources -- bounded depleting values (HP, MP, TP).

Salvaged from codeforge_mk1. Design decision preserved (mk1 ADR-002):
immutable-with-replacement. damage() and heal() return NEW Resource
instances; nothing here ever mutates. State transitions are explicit,
which is the same law as the event log: no silent changes.
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Resource:
    """An immutable bounded value. Transitions produce new instances."""

    name: str
    current: int
    maximum: int

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Resource name must be a non-empty string")
        for label, value in (("current", self.current), ("maximum", self.maximum)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{label} must be an integer")
        if self.maximum < 0:
            raise ValueError(f"maximum ({self.maximum}) cannot be negative")
        if not (0 <= self.current <= self.maximum):
            raise ValueError(f"current ({self.current}) must be within [0, {self.maximum}]")

    def damage(self, amount: int) -> "Resource":
        """Return a new Resource reduced by amount, floored at zero."""
        self._check_amount(amount)
        return replace(self, current=max(0, self.current - amount))

    def heal(self, amount: int) -> "Resource":
        """Return a new Resource increased by amount, capped at maximum."""
        self._check_amount(amount)
        return replace(self, current=min(self.maximum, self.current + amount))

    @property
    def is_depleted(self) -> bool:
        return self.current == 0

    @property
    def is_full(self) -> bool:
        return self.current == self.maximum

    @staticmethod
    def _check_amount(amount: int) -> None:
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise ValueError("amount must be an integer")
        if amount < 0:
            raise ValueError(f"amount ({amount}) cannot be negative")
