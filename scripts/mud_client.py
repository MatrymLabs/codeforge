#!/usr/bin/env python3
"""CARD: mud_client -- a telnet-aware client so the front desk can mask your password.

The gateway hides secrets with a telnet trick: it sends `IAC WILL ECHO` before a
password prompt so a real client stops echoing your keystrokes, then `IAC WONT
ECHO` afterward. Plain `nc` ignores that negotiation -- it prints your password
in the clear and dumps the raw IAC bytes as terminal garbage.

This client speaks just enough telnet to honour that signal, using only the
standard library -- no `telnet` binary required. While the server has asked for a
secret it switches the terminal to cbreak mode and echoes a `*` for each
keystroke, so the field is MASKED (you can see how many characters you've typed)
without ever showing the password. Outside a secret it stays in normal line mode,
so backspace and editing work as usual.

Usage:  python3 scripts/mud_client.py [host] [port]   # defaults 127.0.0.1 4000
"""

from __future__ import annotations

import contextlib
import os
import select
import socket
import sys

IAC = 255
WILL, WONT, DO, DONT = 251, 252, 253, 254
ECHO = 1

_ENTER = (0x0D, 0x0A)
_BACKSPACE = (0x7F, 0x08)


def _mask_feed(buffer: bytearray, data: bytes) -> tuple[bytes, bytes | None]:
    """Pure keystroke logic for a masked field. Mutates `buffer` with the real
    characters typed and returns (bytes to echo to the terminal, the completed
    line with a trailing newline once Enter is pressed, else None)."""
    echo = bytearray()
    for byte in data:
        if byte in _ENTER:
            line = bytes(buffer) + b"\n"
            buffer.clear()
            return bytes(echo) + b"\r\n", line
        if byte in _BACKSPACE:
            if buffer:
                buffer.pop()
                echo += b"\b \b"  # rub out one mask character
        elif byte >= 0x20:
            buffer.append(byte)
            echo += b"*"
        # other control characters are ignored
    return bytes(echo), None


class _SecretField:
    """Masks a password field: cbreak the terminal, echo `*` per keystroke, and
    hand the real line to the caller on Enter. On a non-tty (piped input, tests)
    it is a transparent passthrough -- there is nothing to mask."""

    def __init__(self, fd: int, saved: list | None) -> None:
        self._fd = fd
        self._saved = saved  # None when stdin isn't a real terminal
        self._buf = bytearray()
        self.active = False

    def enter(self) -> None:
        """Server asked for a secret (IAC WILL ECHO): enter masked mode."""
        if self.active:
            return
        self.active = True
        self._buf.clear()
        if self._saved is None:
            return
        import termios

        with contextlib.suppress(termios.error, OSError):
            attrs = termios.tcgetattr(self._fd)
            attrs[3] &= ~(termios.ICANON | termios.ECHO)  # no line buffer, no auto-echo
            attrs[6][termios.VMIN] = 1
            attrs[6][termios.VTIME] = 0
            termios.tcsetattr(self._fd, termios.TCSANOW, attrs)

    def exit(self) -> None:
        """Secret done (IAC WONT ECHO): restore normal line mode."""
        if not self.active:
            return
        self.active = False
        self._buf.clear()
        if self._saved is None:
            return
        import termios

        with contextlib.suppress(termios.error, OSError):
            termios.tcsetattr(self._fd, termios.TCSANOW, self._saved)

    def feed(self, out: int, data: bytes) -> bytes:
        """Consume typed bytes. Echoes mask characters to `out`; returns the
        completed password line once Enter is pressed, else b""."""
        if self._saved is None:  # non-tty: cannot mask, forward untouched
            return data
        echo, line = _mask_feed(self._buf, data)
        if echo:
            os.write(out, echo)
        return line if line is not None else b""


def _pump_from_server(chunk: bytes, out: int, echo_on, echo_off, leftover: bytes = b"") -> bytes:
    """Strip IAC sequences for display; act on the ECHO option the gateway uses.

    Returns any trailing bytes that are the START of an IAC sequence split across
    this recv() boundary. The caller feeds them back as `leftover` next time, so a
    fragmented negotiation (e.g. `IAC WILL ECHO` arriving one byte early) never
    leaks its raw bytes to the terminal as garbage, and never misses the echo
    toggle that masks the password field."""
    data = leftover + chunk
    clean = bytearray()
    i, n = 0, len(data)
    while i < n:
        byte = data[i]
        if byte != IAC:
            clean.append(byte)
            i += 1
            continue
        if i + 1 >= n:
            break  # a lone IAC at the edge -- hold it for the next chunk
        command = data[i + 1]
        if command == IAC:  # escaped literal 0xFF
            clean.append(IAC)
            i += 2
        elif command in (WILL, WONT, DO, DONT):
            if i + 2 >= n:
                break  # 3-byte option split here -- wait for the option byte
            if data[i + 2] == ECHO:
                # Server WILL echo -> we take over the field (mask it); WONT -> release.
                (echo_off if command == WILL else echo_on)()
            i += 3
        else:
            i += 2  # some other 2-byte telnet command
    if clean:
        os.write(out, bytes(clean))
    return data[i:]  # partial IAC sequence, carried to the next chunk


def main(argv: list[str]) -> int:
    host = argv[1] if len(argv) > 1 else "127.0.0.1"
    port = int(argv[2]) if len(argv) > 2 else 4000

    stdin_fd = sys.stdin.fileno()
    saved = None
    if os.isatty(stdin_fd):
        import termios

        # Ignore SIGTTOU so tcsetattr works even when we're NOT the terminal's
        # foreground process group -- e.g. the ritual runs us beside a
        # backgrounded server. (Unix-only signal.)
        with contextlib.suppress(ValueError, OSError, AttributeError):
            import signal

            signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        with contextlib.suppress(termios.error, OSError):
            saved = termios.tcgetattr(stdin_fd)
    secret = _SecretField(stdin_fd, saved)

    try:
        sock = socket.create_connection((host, port))
    except OSError as exc:
        print(f"mud_client: cannot reach {host}:{port} ({exc})", file=sys.stderr)
        return 1

    out = sys.stdout.fileno()
    try:
        sock.setblocking(False)
        stdin_open = True
        leftover = b""  # start of an IAC sequence split across a recv() boundary
        while True:
            watch = [sock, stdin_fd] if stdin_open else [sock]
            readable, _, _ = select.select(watch, [], [])
            if sock in readable:
                data = sock.recv(4096)
                if not data:
                    break  # server closed -- the forge banked its coals
                leftover = _pump_from_server(data, out, secret.exit, secret.enter, leftover)
            if stdin_open and stdin_fd in readable:
                typed = os.read(stdin_fd, 4096)
                if not typed:
                    # Local EOF (Ctrl-D / end of a piped script). Stop sending but
                    # keep draining the server's reply until it closes the socket.
                    stdin_open = False
                    with contextlib.suppress(OSError):
                        sock.shutdown(socket.SHUT_WR)
                    continue
                payload = secret.feed(out, typed) if secret.active else typed
                if payload:
                    with contextlib.suppress(OSError):
                        sock.sendall(payload)
    finally:
        secret.exit()  # never leave the terminal in cbreak / no-echo
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
