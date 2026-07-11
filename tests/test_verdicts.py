"""Test twin for parts/verdicts.py -- the shared readiness verdict vocabulary.

Pins the values and that the gates now share ONE source (no independent re-declaration), so a
gate and the frame-up that reads its board can never drift apart.
"""

from parts import verdicts


def test_the_verdict_values() -> None:
    assert (verdicts.PASS, verdicts.FAIL, verdicts.WATCH, verdicts.NA) == (
        "pass",
        "fail",
        "watch",
        "n/a",
    )


def test_the_gates_share_the_one_vocabulary() -> None:
    # qualitygate / stewardship / evolution / frameup all bind the SAME constants now.
    from parts import frameup, qualitygate
    from parts.evolution import fitness
    from parts.stewardship import gate

    assert qualitygate.PASS is verdicts.PASS and qualitygate.FAIL is verdicts.FAIL
    assert qualitygate.WATCH is verdicts.WATCH and qualitygate.NA is verdicts.NA
    assert gate.PASS is verdicts.PASS and gate.FAIL is verdicts.FAIL
    assert fitness._PASS is verdicts.PASS and fitness._FAIL is verdicts.FAIL
    assert frameup.WATCH is verdicts.WATCH  # the constant frameup used to re-declare
