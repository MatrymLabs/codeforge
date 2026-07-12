"""Test twin for parts/release_gate.py -- the practical adapter + the one-core proof."""

from parts.release_gate import ReleaseGate
from parts.test_evidence import FAILED, PASSED, EvidenceLedger


def test_a_release_is_ready_only_when_every_required_check_passes():
    gate = ReleaseGate(commit="abc123")
    for check in ("lint", "tests", "coverage", "security"):
        gate.record(check, PASSED)
    assert gate.is_ready() is True
    assert gate.gaps() == []


def test_a_step_that_never_ran_blocks_the_release():
    gate = ReleaseGate(commit="abc123")
    gate.record("lint", PASSED)
    gate.record("tests", PASSED)
    gate.record("coverage", PASSED)
    # 'security' was never recorded: it is missing, so the release is not ready
    assert gate.is_ready() is False
    assert "security" in gate.gaps()


def test_a_failed_check_blocks_the_release():
    gate = ReleaseGate(commit="abc123")
    for check in ("lint", "tests", "coverage"):
        gate.record(check, PASSED)
    gate.record("security", FAILED)
    assert gate.is_ready() is False


def test_one_core_powers_both_the_world_cert_and_the_release_gate():
    import parts.world_cert as game

    gate = ReleaseGate()
    assert isinstance(gate._ledger, EvidenceLedger)  # the release gate uses the core
    assert isinstance(game._certify(), EvidenceLedger)  # the world certificate, same core
