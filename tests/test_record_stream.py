"""Test twin for parts/record_stream.py -- the practical adapter for the stream framer."""

from parts.record_stream import RecordStream
from parts.shelf.stream_framer import StreamFramer


def test_consume_collects_records_across_chunks():
    stream = RecordStream()
    records = stream.consume([b"one\ntw", b"o\nthree\n"])
    assert records == ["one", "two", "three"]
    assert stream.records == ["one", "two", "three"]


def test_close_flushes_a_trailing_partial_record():
    stream = RecordStream()
    stream.feed(b"complete\npartial")
    assert stream.records == ["complete"]
    assert stream.close() == "partial"
    assert stream.records == ["complete", "partial"]


def test_close_with_no_tail_returns_none():
    stream = RecordStream()
    stream.feed(b"a\n")
    assert stream.close() is None


def test_one_core_two_adapters_share_the_framer():
    assert isinstance(RecordStream()._framer, StreamFramer)
