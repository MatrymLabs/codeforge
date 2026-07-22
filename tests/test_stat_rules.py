"""Test twin for parts/stat_rules.py -- the configurable derived-stat ruleset.

Parity (the DEFAULT_RULESET reproduces the documented prototype formulas exactly) AND config
(a declared ruleset produces different, valid stats) AND refusal (a malformed ruleset fails loud).
"""

from __future__ import annotations

import pytest

from parts.stat_rules import (
    DEFAULT_RULESET,
    DERIVED_STATS,
    RulesetError,
    apply_ruleset,
    from_dict,
)

_TEN = dict.fromkeys(("strength", "speed", "magic", "stamina", "wisdom", "luck"), 10)


def test_the_default_ruleset_reproduces_the_prototype_formulas() -> None:
    # attributes all 10, level 5: the exact prototype numbers derived.py used to hardcode.
    stats = apply_ruleset(DEFAULT_RULESET, _TEN, 5)
    assert stats == {"ATK": 30, "DEF": 20, "EVA": 17, "MAG DEF": 18, "ACC": 78}


def test_a_missing_attribute_reads_zero() -> None:
    stats = apply_ruleset(DEFAULT_RULESET, {"strength": 10}, 0)
    assert stats["ATK"] == 20 and stats["DEF"] == 0  # only strength contributes to ATK


def test_derived_still_matches_the_ruleset() -> None:
    from parts.derived import derived_stats

    assert derived_stats(_TEN, 5) == apply_ruleset(DEFAULT_RULESET, _TEN, 5)


# --- config-driven: a declared ruleset changes the balance ------------------------------
def _min_rule(
    base: int = 0, level: bool = False, attr: str = "strength", coeff: float = 1.0
) -> dict:
    return {"base": base, "level": level, "terms": [{"coeff": coeff, "attributes": [attr]}]}


def _full_config(**overrides: dict) -> dict:
    config = {stat: _min_rule() for stat in DERIVED_STATS}
    config.update(overrides)
    return config


def test_a_declared_ruleset_produces_different_stats() -> None:
    config = _full_config(ATK=_min_rule(base=100, coeff=3.0, attr="strength"))
    ruleset = from_dict(config)
    stats = apply_ruleset(ruleset, _TEN, 5)
    assert stats["ATK"] == 100 + 30  # base 100 + strength(10)*3, no level bonus


def test_a_default_shaped_config_round_trips_to_the_default_behaviour() -> None:
    # Re-declaring the default formulas as data reproduces the default output.
    config = {
        "ATK": {
            "base": 0,
            "level": True,
            "terms": [
                {"coeff": 2.0, "attributes": ["strength"]},
                {"coeff": 0.5, "attributes": ["speed"]},
            ],
        },
        "DEF": {"base": 0, "level": True, "terms": [{"coeff": 1.5, "attributes": ["stamina"]}]},
        "EVA": {
            "base": 0,
            "level": False,
            "terms": [
                {"coeff": 1.2, "attributes": ["speed"]},
                {"coeff": 0.5, "attributes": ["luck"]},
            ],
        },
        "MAG DEF": {
            "base": 0,
            "level": False,
            "terms": [{"coeff": 0.9, "attributes": ["magic", "wisdom"]}],
        },
        "ACC": {
            "base": 70,
            "level": False,
            "terms": [
                {"coeff": 0.5, "attributes": ["speed"]},
                {"coeff": 0.3, "attributes": ["luck"]},
            ],
        },
    }
    assert apply_ruleset(from_dict(config), _TEN, 5) == apply_ruleset(DEFAULT_RULESET, _TEN, 5)


# --- refusal (fail loud) ----------------------------------------------------------------
def test_a_non_mapping_ruleset_is_refused() -> None:
    with pytest.raises(RulesetError, match="mapping"):
        from_dict(["not", "a", "dict"])


def test_a_ruleset_missing_a_stat_is_refused() -> None:
    with pytest.raises(RulesetError, match="missing"):
        from_dict({stat: _min_rule() for stat in DERIVED_STATS if stat != "ACC"})


def test_a_stat_with_no_terms_is_refused() -> None:
    with pytest.raises(RulesetError, match="terms"):
        from_dict(_full_config(ATK={"base": 0, "level": False, "terms": []}))


def test_an_unknown_attribute_is_refused() -> None:
    with pytest.raises(RulesetError, match="unknown attribute"):
        from_dict(_full_config(ATK=_min_rule(attr="charisma")))


def test_a_non_numeric_coeff_is_refused() -> None:
    with pytest.raises(RulesetError, match="coeff"):
        from_dict(
            _full_config(
                ATK={
                    "base": 0,
                    "level": False,
                    "terms": [{"coeff": "lots", "attributes": ["strength"]}],
                }
            )
        )
