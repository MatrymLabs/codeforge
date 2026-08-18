"""Contract tests for every Blueprint's differential verdict."""

from __future__ import annotations

import pytest

from kernel.engine_seam import run_differential


@pytest.mark.parametrize("seed", ["first-forge", "seam-probe"])
def test_available_blueprints_return_agreed_verdict(seed: str) -> None:
    verdict = run_differential(seed)

    assert verdict.verdict == "AGREED"
    assert "VERDICT: AGREED" in verdict.render()


@pytest.mark.parametrize("seed", ["aethryn", "spiral-ascent"])
def test_missing_overlay_returns_named_unmeasurable_verdict(seed: str) -> None:
    verdict = run_differential(seed)

    assert verdict.verdict == "UNMEASURABLE"
    assert verdict.unmeasurable_reason is not None
    assert seed in verdict.unmeasurable_reason
    assert "world_overlay.json" in verdict.unmeasurable_reason
    assert "VERDICT: UNMEASURABLE" in verdict.render()
