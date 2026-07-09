"""Test twin for scripts/mud_client.py -- the telnet-aware client that hides
your password. The regression that matters: an IAC negotiation split across
recv() boundaries must not leak raw bytes to the terminal (the '??' garbage) or
miss the echo toggle that blacks out the secret field."""

import importlib.util
import os
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "scripts" / "mud_client.py"
_spec = importlib.util.spec_from_file_location("mud_client", _SRC)
assert _spec and _spec.loader  # narrow for the type checker
mud_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mud_client)


def _pump(chunks: list[bytes]) -> tuple[bytes, list[str]]:
    """Feed byte chunks through _pump_from_server as separate recv()s, threading
    the leftover. Returns (bytes shown to the terminal, echo toggle calls)."""
    calls: list[str] = []
    read_fd, write_fd = os.pipe()
    leftover = b""
    for chunk in chunks:
        leftover = mud_client._pump_from_server(
            chunk, write_fd, lambda: calls.append("ON"), lambda: calls.append("OFF"), leftover
        )
    os.close(write_fd)
    shown = os.read(read_fd, 4096)
    os.close(read_fd)
    return shown, calls


def test_whole_echo_negotiation_blacks_out_and_is_stripped():
    shown, calls = _pump([b"Password: \xff\xfb\x01"])  # prompt + IAC WILL ECHO
    assert shown == b"Password: "  # the negotiation bytes never reach the terminal
    assert calls == ["OFF"]  # blackout engaged


def test_iac_split_across_recv_never_leaks_or_misses_the_blackout():
    """The bug behind the '??' garbage and the vanished password mask: the
    3-byte IAC WILL ECHO arriving one byte early, split over two reads."""
    shown, calls = _pump([b"Password: \xff", b"\xfb\x01"])
    assert b"\xff" not in shown  # no raw IAC rendered as '??'
    assert shown == b"Password: "
    assert calls == ["OFF"]  # echo still blacked out


def test_wont_echo_restores_the_terminal():
    shown, calls = _pump([b"\xff\xfc\x01done"])  # IAC WONT ECHO
    assert shown == b"done"
    assert calls == ["ON"]


def test_escaped_literal_ff_survives_as_one_byte():
    shown, _ = _pump([b"hi\xff\xffthere"])  # IAC IAC -> a single literal 0xff
    assert shown == b"hi\xffthere"
