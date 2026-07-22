"""Test twin for parts/derived.py -- the prototype derived-stat formulas.

The formulas are prototype balance, but they are DETERMINISTIC, so the numbers are pinned
exactly: a formula change is a visible, reviewable diff, never a silent drift. A partial
attribute set must still produce all five stats (the sheet renders incomplete characters).
"""

from __future__ import annotations

from parts.derived import DERIVED_STATS, derived_stats

# A fixed attribute set so the expected numbers are exact.
_ATTRS = {"strength": 10, "speed": 12, "magic": 8, "stamina": 11, "wisdom": 13, "luck": 9}


def test_all_five_derived_stats_are_produced() -> None:
    result = derived_stats(_ATTRS, level=1)
    assert set(result) == set(DERIVED_STATS)


def test_the_prototype_numbers_are_exact_and_deterministic() -> None:
    # Pins the current prototype formulas; changing them must change this test on purpose.
    result = derived_stats(_ATTRS, level=1)
    assert result == {"ATK": 27, "DEF": 17, "EVA": 19, "MAG DEF": 19, "ACC": 79}


def test_level_raises_the_scaling_stats() -> None:
    low = derived_stats(_ATTRS, level=1)
    high = derived_stats(_ATTRS, level=10)
    assert high["ATK"] > low["ATK"]  # ATK and DEF scale with level
    assert high["EVA"] == low["EVA"]  # EVA does not, by the prototype design


def test_a_missing_attribute_reads_zero_not_a_crash() -> None:
    result = derived_stats({"strength": 6}, level=0)  # only one attribute present
    assert set(result) == set(DERIVED_STATS)
    assert result["ATK"] == 12  # strength 6 * 2, everything else 0


def test_derived_stats_uses_the_active_world_ruleset(monkeypatch) -> None:
    # A world's declared balance reaches the sheet: derived_stats() with no ruleset arg uses the
    # module-level active ruleset, bound at import from the booted world's world.yaml.
    import parts.derived as derived
    from parts.stat_rules import from_dict

    custom = from_dict(
        {
            stat: {"base": 999, "level": False, "terms": [{"coeff": 0.0, "attributes": ["luck"]}]}
            for stat in ("ATK", "DEF", "EVA", "MAG DEF", "ACC")
        }
    )
    monkeypatch.setattr(derived, "_ACTIVE_RULESET", custom)
    ten = dict.fromkeys(("strength", "speed", "magic", "stamina", "wisdom", "luck"), 10)
    assert derived.derived_stats(ten, 5)["ATK"] == 999  # picked up the active ruleset, no arg
