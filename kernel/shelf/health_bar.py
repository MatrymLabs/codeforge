"""CARD: health_bar -- render a numeric value as a proportional ASCII meter bar.

Harvested clean-room (pattern-not-code) from Evennia contrib rpg/health_bar (BSD-3-Clause).
codeforge
shows numeric readouts ("HP 10 / 20") but has no visual meter; a bar is a clear UX win and pairs
with
the color harvest. Pure projection: a value + a maximum + a width -> a bar string. Stdlib only.

  bar(12, 20)          -> "[##############------] 12/20"
  bar(0, 20, width=10) -> "[----------] 0/20"
"""

from __future__ import annotations


class HealthBarError(ValueError):
    """Raised loud on a non-positive maximum, a negative value, an over-max value, or width < 1."""


def bar(
    value: float,
    maximum: float,
    *,
    width: int = 20,
    filled: str = "#",
    empty: str = "-",
    show_numbers: bool = True,
) -> str:
    """Render `value`/`maximum` as a `width`-cell meter. `value` is clamped-checked (0 <= value <=
    maximum) and fails loud outside it (a bar must never lie about an impossible value). The fill is
    rounded to the nearest cell; a non-zero value never rounds down to a fully-empty bar, and a
    value
    below maximum never rounds up to a fully-full bar (the edges read true)."""
    if maximum <= 0:
        raise HealthBarError(f"maximum must be > 0 (got {maximum})")
    if value < 0:
        raise HealthBarError(f"value cannot be negative (got {value})")
    if value > maximum:
        raise HealthBarError(f"value {value} exceeds maximum {maximum}")
    if width < 1:
        raise HealthBarError(f"width must be >= 1 (got {width})")
    if len(filled) != 1 or len(empty) != 1:
        raise HealthBarError("filled and empty must each be a single character")

    frac = value / maximum
    cells = round(frac * width)
    if 0 < value < maximum:
        cells = min(max(cells, 1), width - 1)  # keep the edges honest
    meter = filled * cells + empty * (width - cells)
    if show_numbers:
        return f"[{meter}] {_num(value)}/{_num(maximum)}"
    return f"[{meter}]"


def _num(x: float) -> str:
    """Render a number without a trailing .0 for whole values (HP reads as 12, not 12.0)."""
    return str(int(x)) if float(x).is_integer() else str(x)
