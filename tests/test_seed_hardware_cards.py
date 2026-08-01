"""Stage-7 hardware extraction: the seedlab mechanisms are filed as Hardware Store cards.

Pins the extraction of the proven First-Platform-Proof mechanisms into catalog/parts.yaml: each is
present, cites real seedlab code, is honestly marked `prototype` (not promoted prematurely), and
carries the reuse domains the Hardware Store scores on.
"""

from __future__ import annotations

from parts.hardware import load_catalog, source_gaps

# The mechanisms harvested from the Seed Platform vertical slice -> their citing source file.
_SEED_CARDS = {
    "path-bounded-reader": "parts/seedlab/source_connector.py",
    "provenance-record": "parts/seedlab/project_model.py",
    "file-record-store": "parts/seedlab/model_store.py",
    "lifecycle-state-machine": "parts/seedlab/kernel.py",
    "controlled-tool-runner": "parts/seedlab/tool_runner.py",
    "reproducible-generator": "parts/seedlab/cli_generator.py",
}


def _by_id() -> dict:
    return {p.id: p for p in load_catalog()}


def test_all_seed_cards_are_filed() -> None:
    cards = _by_id()
    assert set(_SEED_CARDS) <= set(cards), (
        "a harvested seedlab mechanism is missing from the catalog"
    )


def test_cards_cite_real_seedlab_code() -> None:
    cards = _by_id()
    for card_id, source in _SEED_CARDS.items():
        assert cards[card_id].source == source
    assert source_gaps() == []  # every catalog card cites code that exists


def test_seed_cards_are_prototype_not_overclaimed() -> None:
    cards = _by_id()
    for card_id in _SEED_CARDS:
        # The directive: do not promote unstable abstractions prematurely.
        assert cards[card_id].maturity == "prototype", f"{card_id} overclaims maturity"


def test_seed_cards_declare_cross_domain_reuse() -> None:
    cards = _by_id()
    for card_id in _SEED_CARDS:
        assert len(cards[card_id].reuse) >= 4  # reuse_score is derived from these domains
