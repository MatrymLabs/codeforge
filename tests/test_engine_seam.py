"""Contract tests for every Blueprint's differential verdict."""

from __future__ import annotations

import pytest

from kernel.engine_seam import run_differential


@pytest.mark.parametrize("seed", ["first-forge", "seam-probe"])
def test_available_blueprints_return_agreed_verdict(seed: str) -> None:
    verdict = run_differential(seed)

    assert verdict.verdict == "AGREED"
    assert "VERDICT: AGREED" in verdict.render()


def test_missing_overlay_returns_named_unmeasurable_verdict() -> None:
    """A Blueprint with no overlay is UNMEASURABLE, named, and not a traceback.

    This asserted the BEHAVIOUR against two real Blueprints, "aethryn" and "spiral-ascent",
    which happened to be missing their overlays on the day it was written. Both overlays landed
    hours later and the test failed -- correctly, and for the wrong reason: it had pinned a
    DEFECT as though it were a specification, so repairing the defect broke the test.

    A test naming today's broken things breaks the moment they are fixed, and the failure looks
    like a regression rather than progress. So the missing overlay is now MANUFACTURED: a
    Blueprint that has never existed, which cannot acquire an overlay and stop testing this.
    """
    seed = "blueprint-that-does-not-exist"
    verdict = run_differential(seed)

    assert verdict.verdict == "UNMEASURABLE"
    assert verdict.unmeasurable_reason is not None
    assert seed in verdict.unmeasurable_reason
    assert "world_overlay.json" in verdict.unmeasurable_reason
    assert "VERDICT: UNMEASURABLE" in verdict.render()


@pytest.mark.parametrize("seed", ["aethryn", "spiral-ascent"])
def test_the_blueprints_that_were_unmeasurable_now_measure(seed: str) -> None:
    """The other half, and the one that would otherwise go unrecorded: these two are no longer
    UNMEASURABLE. Their overlays exist and cover every room in rooms.yaml exactly."""
    verdict = run_differential(seed)

    assert verdict.verdict != "UNMEASURABLE", verdict.render()
    assert verdict.unmeasurable_reason is None
