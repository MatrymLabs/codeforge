"""Contract tests for every Blueprint's differential verdict."""

from __future__ import annotations

import pytest

from kernel.engine_seam import run_differential


@pytest.mark.parametrize("seed", ["first-forge", "seam-probe", "aethryn", "spiral-ascent"])
def test_every_blueprint_returns_agreed_verdict(seed: str) -> None:
    verdict = run_differential(seed)

    assert verdict.verdict == "AGREED"
    assert "VERDICT: AGREED" in verdict.render()


def test_every_unfalsifiable_probe_has_a_recorded_structural_reason() -> None:
    verdict = run_differential()
    records = {
        f"{record.aspect}/{name}": reason
        for record in verdict.aspect_falsifiability
        for name, reason in record.unfalsifiable_reasons
    }
    expected = {
        "inventory/purse_renders",
        "inventory/module_is_position_free",
        "progression/xp_for_level",
        "progression/jp_for_level",
        "progression/calling_gate",
        "permission/rank_denies_admin",
        "permission/player_denies_teleport",
        "permission/wizard_denies_grant",
        "permission/workshop_barrier_denies_wizard",
        "persistence/grant_key_shape",
        "persistence/gameplay_save_preserves_auth",
    }

    assert len(verdict.falsifiable) == 7
    assert verdict.commands_compared == 18
    assert set(records) == expected
    assert all(records.values())
    assert all(name in verdict.render() for name in (probe.split("/", 1)[1] for probe in expected))
