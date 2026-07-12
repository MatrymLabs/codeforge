"""Test twin for parts/stream_framer.py -- frame a byte stream, buffering partials."""

import pytest

from parts.stream_framer import StreamFramer


def test_multiple_messages_in_one_chunk():
    assert StreamFramer().feed(b"a\nb\nc\n") == ["a", "b", "c"]


def test_message_split_across_chunks_is_buffered():
    framer = StreamFramer()
    assert framer.feed(b"hel") == []  # partial, held
    assert framer.feed(b"lo\nworld\n") == ["hello", "world"]


def test_crlf_is_trimmed_by_default():
    assert StreamFramer().feed(b"line\r\n") == ["line"]


def test_a_custom_delimiter_frames_records():
    framer = StreamFramer(delimiter=b"||", strip=b"")
    assert framer.feed(b"one||two||thr") == ["one", "two"]
    assert framer.flush() == "thr"


def test_flush_returns_partial_tail_then_clears():
    framer = StreamFramer()
    assert framer.feed(b"Prompt>") == []
    assert framer.flush() == "Prompt>"
    assert framer.flush() is None


def test_empty_delimiter_is_refused():
    with pytest.raises(ValueError):
        StreamFramer(delimiter=b"")


def test_invalid_bytes_are_replaced_not_fatal():
    assert StreamFramer().feed(b"ab\xffcd\n") == ["ab�cd"]
