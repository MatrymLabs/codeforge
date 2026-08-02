"""CARD: stat_rules -- a configurable ruleset for the derived combat stats (data, not hardcode).

The derived stats (ATK/DEF/EVA/MAG DEF/ACC) were computed by PROTOTYPE formulas hardcoded in
parts/derived. This lifts those coefficients into a typed, validated Ruleset: each stat is
`base + round(sum(coeff * sum(attributes))) + (level bonus?)`, so balance is DATA a world can
declare, not Python to edit. The DEFAULT_RULESET reproduces the prototype formulas EXACTLY (a
parity test pins byte-identity over the attribute space), so nothing changes until a ruleset is
supplied. It computes and validates only; it stores no state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# The derived stats, in canonical sheet order, and the six attributes they draw from.
DERIVED_STATS = ("ATK", "DEF", "EVA", "MAG DEF", "ACC")
ATTRIBUTES = ("strength", "speed", "magic", "stamina", "wisdom", "luck")


class RulesetError(ValueError):
    """A stat ruleset was built with an invalid field. Fails loud at construction."""


@dataclass(frozen=True)
class Term:
    """`coeff * (sum of the named attributes)` -- a grouped weighted term."""

    coeff: float
    attributes: tuple[str, ...]


@dataclass(frozen=True)
class StatRule:
    """One derived stat: `base + round(sum(terms)) + (level if uses_level)`."""

    base: int
    uses_level: bool
    terms: tuple[Term, ...]


Ruleset = dict[str, StatRule]  # stat name -> its rule


# The prototype formulas, as data. Verified byte-identical to the old parts/derived hardcode.
DEFAULT_RULESET: Ruleset = {
    "ATK": StatRule(0, True, (Term(2.0, ("strength",)), Term(0.5, ("speed",)))),
    "DEF": StatRule(0, True, (Term(1.5, ("stamina",)),)),
    "EVA": StatRule(0, False, (Term(1.2, ("speed",)), Term(0.5, ("luck",)))),
    "MAG DEF": StatRule(0, False, (Term(0.9, ("magic", "wisdom")),)),
    "ACC": StatRule(70, False, (Term(0.5, ("speed",)), Term(0.3, ("luck",)))),
}


def apply_ruleset(ruleset: Ruleset, attributes: Mapping[str, int], level: int) -> dict[str, int]:
    """Compute the derived stats from attributes + level under a ruleset. Pure, integer-valued.
    A missing attribute reads 0 (the sheet must render a partial character)."""
    lvl = max(0, int(level))
    out: dict[str, int] = {}
    for stat in DERIVED_STATS:
        rule = ruleset[stat]
        total = sum(
            term.coeff * sum(int(attributes.get(name, 0)) for name in term.attributes)
            for term in rule.terms
        )
        out[stat] = rule.base + round(total) + (lvl if rule.uses_level else 0)
    return out


def _term_from_dict(stat: str, raw: Any) -> Term:
    if not isinstance(raw, dict) or "coeff" not in raw or "attributes" not in raw:
        raise RulesetError(f"stat {stat!r}: each term needs 'coeff' and 'attributes'")
    attrs = raw["attributes"]
    if isinstance(attrs, str) or not hasattr(attrs, "__iter__"):
        raise RulesetError(f"stat {stat!r}: a term's 'attributes' must be a list")
    names = tuple(str(name) for name in attrs)
    unknown = [name for name in names if name not in ATTRIBUTES]
    if unknown:
        raise RulesetError(f"stat {stat!r}: unknown attribute(s) {unknown}; valid: {ATTRIBUTES}")
    if not names:
        raise RulesetError(f"stat {stat!r}: a term needs at least one attribute")
    try:
        coeff = float(raw["coeff"])
    except (TypeError, ValueError) as exc:
        raise RulesetError(f"stat {stat!r}: 'coeff' must be a number") from exc
    return Term(coeff, names)


def _rule_from_dict(stat: str, raw: Any) -> StatRule:
    if not isinstance(raw, dict):
        raise RulesetError(f"stat {stat!r} must be a mapping")
    terms_raw = raw.get("terms", [])
    if not isinstance(terms_raw, list) or not terms_raw:
        raise RulesetError(f"stat {stat!r} needs a non-empty 'terms' list")
    return StatRule(
        base=int(raw.get("base", 0)),
        uses_level=bool(raw.get("level", False)),
        terms=tuple(_term_from_dict(stat, term) for term in terms_raw),
    )


def from_dict(raw: Any) -> Ruleset:
    """Build + validate a Ruleset from a mapping (a world's declared balance). Fails loud, and
    requires a rule for every derived stat so no stat silently falls back."""
    if not isinstance(raw, dict):
        raise RulesetError(f"a ruleset must be a mapping, got {type(raw).__name__}")
    missing = [stat for stat in DERIVED_STATS if stat not in raw]
    if missing:
        raise RulesetError(f"ruleset is missing rule(s) for {missing}")
    return {stat: _rule_from_dict(stat, raw[stat]) for stat in DERIVED_STATS}
