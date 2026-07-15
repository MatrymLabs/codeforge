"""Test twin for parts/hashchain.py -- the general tamper-evident append-only ledger.

Acceptance: records append and read back in order; each link chains to its predecessor; empty and
missing stores read clean. Refusal (the whole point of a tamper-evident log): an edited payload, a
reordered chain, a deleted middle record, a malformed line, and a non-serializable payload all
fail loud with HashChainError rather than returning a dishonest history. Every test uses tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.hashchain import GENESIS, HashChainError, append, content_hash, read, verify


def _ledger(root: Path) -> Path:
    return root / "chain.jsonl"


# --- acceptance --------------------------------------------------------------------------------


def test_append_then_read_round_trips(tmp_path: Path) -> None:
    p = _ledger(tmp_path)
    append(p, {"event": "created", "who": "alice"})
    append(p, {"event": "approved", "who": "bob"})
    links = read(p)
    assert [link.payload["event"] for link in links] == ["created", "approved"]
    assert [link.seq for link in links] == [0, 1]


def test_the_chain_links_each_record_to_its_predecessor(tmp_path: Path) -> None:
    p = _ledger(tmp_path)
    a = append(p, {"n": 1})
    b = append(p, {"n": 2})
    assert a.prior_hash == GENESIS  # nothing precedes the first link
    assert b.prior_hash == a.content_hash  # chained
    assert a.content_hash != b.content_hash


def test_empty_and_missing_stores_read_clean(tmp_path: Path) -> None:
    assert read(_ledger(tmp_path)) == []  # missing file
    p = _ledger(tmp_path)
    p.write_text("\n  \n", encoding="utf-8")  # only blank lines
    assert read(p) == []
    assert verify(p) is True


def test_content_hash_is_canonical_and_order_independent(tmp_path: Path) -> None:
    # Key order in the source dict must not change the hash (sorted-keys canonicalization).
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})


# --- refusal / hostile -------------------------------------------------------------------------


def test_a_non_dict_payload_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(HashChainError, match="must be a JSON object"):
        append(_ledger(tmp_path), ["not", "a", "dict"])  # type: ignore[arg-type]


def test_a_non_serializable_payload_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(HashChainError, match="not JSON-serializable"):
        append(_ledger(tmp_path), {"tags": {1, 2, 3}})  # a set is not JSON-serializable
    assert read(_ledger(tmp_path)) == []  # the bad record never reached disk


def test_a_tampered_payload_is_detected_on_read(tmp_path: Path) -> None:
    p = _ledger(tmp_path)
    append(p, {"amount": 100})
    p.write_text(p.read_text().replace("100", "999"), encoding="utf-8")  # edit without rehashing
    with pytest.raises(HashChainError, match="tampered"):
        read(p)
    assert verify(p) is False


def test_a_reordered_chain_is_detected(tmp_path: Path) -> None:
    p = _ledger(tmp_path)
    append(p, {"n": 1})
    append(p, {"n": 2})
    first, second = p.read_text().splitlines()
    p.write_text(second + "\n" + first + "\n", encoding="utf-8")  # swap the two records
    with pytest.raises(HashChainError, match="out of order|broken chain"):
        read(p)


def test_deleting_a_middle_record_breaks_the_chain(tmp_path: Path) -> None:
    p = _ledger(tmp_path)
    append(p, {"n": 1})
    append(p, {"n": 2})
    append(p, {"n": 3})
    lines = p.read_text().splitlines()
    p.write_text(lines[0] + "\n" + lines[2] + "\n", encoding="utf-8")  # drop the middle record
    with pytest.raises(HashChainError, match="out of order|broken chain"):
        read(p)


def test_a_malformed_line_fails_loud(tmp_path: Path) -> None:
    p = _ledger(tmp_path)
    p.write_text("{not valid json}\n", encoding="utf-8")
    with pytest.raises(HashChainError, match="unreadable JSON"):
        read(p)


def test_a_record_missing_a_field_fails_loud(tmp_path: Path) -> None:
    p = _ledger(tmp_path)
    p.write_text('{"seq": 0, "payload": {}}\n', encoding="utf-8")  # no prior/content hash
    with pytest.raises(HashChainError, match="malformed record"):
        read(p)


def test_append_reads_a_tail_larger_than_the_seek_block(tmp_path: Path) -> None:
    """The tail read walks back in blocks, so a record longer than one block still chains right."""
    p = _ledger(tmp_path)
    append(p, {"blob": "x" * 9000})  # a record well over the 4 KiB backward-read block
    extended = append(p, {"n": 2})
    assert extended.seq == 1 and extended.prior_hash == read(p)[0].content_hash
    assert verify(p) is True


def test_appending_onto_a_tampered_tail_fails_loud(tmp_path: Path) -> None:
    """append chains onto the tail, so a tampered TAIL is caught at once -- we never build on
    garbage. (A tampered EARLIER record is caught on read instead; see the next test.)"""
    p = _ledger(tmp_path)
    append(p, {"n": 1})
    p.write_text(p.read_text().replace('"n": 1', '"n": 2'), encoding="utf-8")
    with pytest.raises(HashChainError, match="tampered"):
        append(p, {"n": 3})


def test_appending_after_an_earlier_record_is_tampered_still_extends_but_verify_catches_it(
    tmp_path: Path,
) -> None:
    """append is O(1) -- it reads only the tail, not the whole ledger -- so tampering a PAST record
    no longer blocks a new append. Integrity is not lost: verify()/read() still catches the break.
    Tamper-evidence is preserved; only eager re-verification on every append is dropped."""
    p = _ledger(tmp_path)
    append(p, {"n": 1})  # the record we will tamper (an EARLIER, non-tail record)
    append(p, {"n": 2})  # the tail, left intact so append can chain onto it
    p.write_text(p.read_text().replace('"n": 1', '"n": 999'), encoding="utf-8")

    extended = append(p, {"n": 3})  # succeeds: it validates only the (untampered) tail
    assert extended.seq == 2
    assert verify(p) is False  # but the whole-chain check still exposes the tampered past record
    with pytest.raises(HashChainError, match="tampered"):
        read(p)
