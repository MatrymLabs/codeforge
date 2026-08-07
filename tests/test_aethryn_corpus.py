"""Full-world source normalization and reference-closure proof."""

from __future__ import annotations

from pathlib import Path

from kernel.world.aethryn_corpus import audit_world_corpus, format_corpus_audit
from kernel.world.aethryn_models import content_digest

ROOT = Path(__file__).resolve().parents[1]


def test_full_aethryn_corpus_is_reference_closed(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_SEED", "aethryn")
    audit = audit_world_corpus(ROOT)

    assert audit.verdict == "CLEAN"
    assert audit.ir is not None
    assert len(audit.corpus.source_paths) >= 70
    assert audit.corpus.counts["regions"] == 14
    assert audit.corpus.counts["rooms"] >= 1_100
    assert audit.corpus.counts["items"] >= 200
    assert audit.corpus.counts["recipes"] >= 40
    assert audit.ir.source_digest


def test_full_world_digest_and_report_are_deterministic(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_SEED", "aethryn")
    first = audit_world_corpus(ROOT)
    second = audit_world_corpus(ROOT)

    assert first.corpus.source_digest == second.corpus.source_digest
    assert content_digest(first.ir.to_payload()) == content_digest(second.ir.to_payload())
    assert format_corpus_audit(first) == format_corpus_audit(second)
