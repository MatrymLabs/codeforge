"""CARD: world_cert -- the game adapter for test evidence: a world-readiness certificate.

`certify` records evidence for a world's readiness checks (the seed loaded NPCs and callings) and
reports whether the world is certified, or which checks are missing/failing. It uses an
`EvidenceLedger` (parts/shelf/test_evidence), so a check with no evidence is never a pass. The
SAME evidence core backs a release-readiness gate in a practical app (`parts/release_gate`).
"""

from __future__ import annotations

from parts.shelf.test_evidence import FAILED, PASSED, EvidenceLedger
from parts.world.jobs import JOBS
from parts.world.npcs import NPCS
from parts.world.session import Session


def _certify() -> EvidenceLedger:
    ledger = EvidenceLedger(environment="world", commit="live")
    ledger.expect("npcs_loaded")
    ledger.expect("callings_loaded")
    ledger.record("npcs_loaded", PASSED if NPCS else FAILED)
    ledger.record("callings_loaded", PASSED if JOBS else FAILED)
    return ledger


def certify(session: Session, arg: str = "") -> str:
    """The `certify` verb: an honest readiness certificate for the current world."""
    return _certify().report()
