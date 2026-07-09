#!/usr/bin/env python3
"""CARD: mud_client -- a telnet-aware client so the front desk can hide your password.

The gateway hides secrets with a telnet trick: it sends `IAC WILL ECHO` before a
password prompt so a real client stops echoing your keystrokes, then `IAC WONT
ECHO` afterward. Plain `nc` ignores that negotiation -- it prints your password
in the clear and dumps the raw IAC bytes as terminal garbage.

This client speaks just enough telnet to honour the blackout, using only the
standard library -- no `telnet` binary required. It keeps the terminal in normal
line mode (so backspace and editing work) and only toggles local echo off while
the server has asked for a secret, exactly like `getpass`.

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


def _echo_toggle(fd: int, saved: list | None):
    """Return (echo_on, echo_off) callables. No-ops when stdin isn't a real
    terminal (e.g. piped input in a test) -- there's nothing to blind.

    Every termios call is defensive: toggling echo must NEVER crash the client.
    If we can't dim the terminal, the worst case is a visible password, which
    beats a dropped connection."""
    if saved is None:
        return (lambda: None), (lambda: None)
    import termios

    def _set(on: bool) -> None:
        try:
            attrs = termios.tcgetattr(fd)
            attrs[3] = attrs[3] | termios.ECHO if on else attrs[3] & ~termios.ECHO
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
        except (termios.error, OSError):
            pass

    return (lambda: _set(True)), (lambda: _set(False))


def _pump_from_server(chunk: bytes, out: int, echo_on, echo_off, leftover: bytes = b"") -> bytes:
    """Strip IAC sequences for display; act on the ECHO option the gateway uses.

    Returns any trailing bytes that are the START of an IAC sequence split across
    this recv() boundary. The caller feeds them back as `leftover` next time, so a
    fragmented negotiation (e.g. `IAC WILL ECHO` arriving one byte early) never
    leaks its raw bytes to the terminal as garbage, and never misses the echo
    toggle that blacks out the password field."""
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
                # Server WILL echo -> we go dark (it won't actually echo the
                # secret, so the field stays blank). WONT -> echo returns.
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
        # backgrounded server. Without this, blanking the password echo would
        # raise/kill the client and silently drop the login. (Unix-only signal.)
        with contextlib.suppress(ValueError, OSError, AttributeError):
            import signal

            signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        with contextlib.suppress(termios.error, OSError):
            saved = termios.tcgetattr(stdin_fd)
    echo_on, echo_off = _echo_toggle(stdin_fd, saved)

    try:
        sock = socket.create_connection((host, port))
    except OSError as exc:
        print(f"mud_client: cannot reach {host}:{port} ({exc})", file=sys.stderr)
        return 1

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
                leftover = _pump_from_server(data, sys.stdout.fileno(), echo_on, echo_off, leftover)
            if stdin_open and stdin_fd in readable:
                typed = os.read(stdin_fd, 4096)
                if not typed:
                    # Local EOF (Ctrl-D / end of a piped script). Stop sending but
                    # keep draining the server's reply until it closes the socket.
                    stdin_open = False
                    with contextlib.suppress(OSError):
                        sock.shutdown(socket.SHUT_WR)
                    continue
                try:
                    sock.sendall(typed)
                except OSError:
                    break
    finally:
        echo_on()  # never leave the terminal blind
        if saved is not None:
            import termios

            with contextlib.suppress(termios.error, OSError):
                termios.tcsetattr(stdin_fd, termios.TCSANOW, saved)
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
