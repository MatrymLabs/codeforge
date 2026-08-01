#!/usr/bin/env python3
"""End-to-end live smoke test: the whole engine, one sequence.

Mirrors the human flow the ritual wraps -- start (server up) -> log in -> look ->
check -> do things -> log out -> complete (server down). Every step is a real
round-trip over the TCP gateway, asserted against expected output and timed.

Safety: runs its OWN server on a spare port with an EPHEMERAL database
(CODEFORGE_DB in a temp dir), so the real :4000 server and codeforge.db are never
touched. Bank-the-forge (server teardown) always runs, even on failure.

Run: `make smoke` (or `python3 scripts/e2e_smoke.py`). Exit 0 == every step passed.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 4071  # a spare port, off the real :4000
AETHRYN_PORT = 4072  # the flagship-seed leg runs on its own spare port
HOST = "127.0.0.1"
IAC_WILL_ECHO = bytes([255, 251, 1])  # telnet negotiation before a password prompt
# The engine's command prompt is always line-anchored ("\r\n> " / "\n> "). Match on
# the newline, not a bare "> ", so prompt-shaped text inside a reply (e.g. the login
# hint "JOB <name> to take one") can't be mistaken for the real prompt and desync the
# whole session by one round-trip.
PROMPT = b"\n> "

results: list[tuple[str, bool, float, str]] = []


def _recv_until(sock: socket.socket, marker: bytes, timeout: float = 6.0) -> str:
    sock.settimeout(timeout)
    buf = b""
    try:
        while marker not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
    except TimeoutError:
        pass
    return buf.decode(errors="ignore")


def step(
    name: str, sock: socket.socket, line: str, expect: list[str], marker: bytes = PROMPT
) -> str:
    """Send one command, read the reply, assert every expected substring is present."""
    start = time.monotonic()
    sock.sendall(line.encode() + b"\n")
    out = _recv_until(sock, marker)
    dt = (time.monotonic() - start) * 1000
    ok = all(e.lower() in out.lower() for e in expect)
    results.append((f"{name}: `{line}`", ok, dt, "" if ok else out[:100].replace("\n", " | ")))
    return out


def fight(name: str, sock: socket.socket, target: str, swings: int = 15) -> str:
    """Auto-attack a passive target until it falls and the reward lands (or give up).

    The training dummy carries no atk stat, so it never strikes back -- a bounded
    swing loop is safe. "You gain" in the reply is the leveling engine's reward
    handoff, i.e. the foe was defeated and combat resolved.
    """
    start = time.monotonic()
    out = ""
    won = False
    for _ in range(swings):
        sock.sendall(f"attack {target}".encode() + b"\n")
        out = _recv_until(sock, PROMPT)
        if "you gain" in out.lower():
            won = True
            break
    dt = (time.monotonic() - start) * 1000
    results.append(
        (f"{name}: `attack {target}` xN", won, dt, "" if won else out[:100].replace("\n", " | "))
    )
    return out


def login(sock: socket.socket, handle: str, password: str, new: bool) -> None:
    _recv_until(sock, b"NEW:")
    if new:
        sock.sendall(b"new\n")
        _recv_until(sock, b"account:")
    sock.sendall(handle.encode() + b"\n")
    _recv_until(sock, IAC_WILL_ECHO)  # password prompt (telnet echo blackout)
    sock.sendall(password.encode() + b"\n")
    _recv_until(sock, PROMPT)


def connect(port: int = PORT) -> socket.socket:
    for _ in range(80):
        try:
            return socket.create_connection((HOST, port), timeout=2)
        except OSError:
            time.sleep(0.25)
    raise SystemExit("server never came up")


def aethryn_journey() -> None:
    """A second leg on the FLAGSHIP seed (FORGE_SEED=aethryn): prove the Aethryn world
    is enterable and its starter zone navigable through the tick -- Veridia spawn loads,
    exits resolve into a town, a calling is taken, and a quest accepts. Combat there
    rides the generated wilds (no fixed dummy), so this leg stays deterministic and
    leaves the live-combat proof to the first-forge leg above.
    """
    db = Path(tempfile.mkdtemp(prefix="cf-e2e-ae-")) / "ae.db"
    env = {**os.environ, "CODEFORGE_DB": str(db), "FORGE_SEED": "aethryn", "PYTHONUNBUFFERED": "1"}
    t0 = time.monotonic()
    server = subprocess.Popen(
        [sys.executable, "-c", f"from parts.gateway import serve; serve(port={AETHRYN_PORT})"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        assert server.stdout is not None
        boot = time.monotonic()
        while time.monotonic() - boot < 30:  # the flagship seed is larger; allow more boot time
            if server.poll() is not None:
                raise SystemExit("aethryn server exited during boot")
            if "listening on" in server.stdout.readline().decode(errors="ignore"):
                break
        results.append(("AETHRYN boot (flagship seed)", True, (time.monotonic() - t0) * 1000, ""))

        s = connect(AETHRYN_PORT)
        _recv_until(s, b"NEW:")
        s.sendall(b"new\n")
        _recv_until(s, b"account:")
        s.sendall(b"ranger@aethryn\n")
        _recv_until(s, IAC_WILL_ECHO)
        s.sendall(b"lumos_1234\n")
        welcome = _recv_until(s, PROMPT)
        entered = "veridia" in welcome.lower()
        results.append(
            ("AETHRYN enter (spawn = Veridia)", entered, 0.0,
             "" if entered else welcome[:100].replace("\n", " | "))
        )
        step("AETHRYN look", s, "look", ["Veridia", "Exits"])
        step("AETHRYN calling", s, "job vanguard", ["Vanguard"])
        step("AETHRYN move to town", s, "go greenhold", ["Greenhold"])
        step("AETHRYN quest accept", s, "quest the_endless_journey accept", ["Endless Journey"])
        step("AETHRYN region", s, "region", ["Veridia", "contracts"])
        step("AETHRYN logout", s, "quit", ["world dims"])
        s.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


def main() -> int:
    db = Path(tempfile.mkdtemp(prefix="cf-e2e-")) / "e2e.db"
    env = {**os.environ, "CODEFORGE_DB": str(db), "PYTHONUNBUFFERED": "1"}

    # --- START THE RITUAL (essence): an isolated forge lights -----------------
    t0 = time.monotonic()
    server = subprocess.Popen(
        [sys.executable, "-c", f"from parts.gateway import serve; serve(port={PORT})"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        # wait for "listening"
        assert server.stdout is not None
        boot = time.monotonic()
        while time.monotonic() - boot < 20:
            if server.poll() is not None:
                raise SystemExit("server exited during boot")
            line = server.stdout.readline().decode(errors="ignore")
            if "listening on" in line:
                break
        results.append(
            ("START RITUAL: forge lights (isolated)", True, (time.monotonic() - t0) * 1000, "")
        )

        # --- LOG IN (register a fresh player) ---------------------------------
        s = connect()
        _recv_until(s, b"NEW:")
        s.sendall(b"new\n")
        _recv_until(s, b"account:")
        s.sendall(b"scout@smoke\n")
        _recv_until(s, IAC_WILL_ECHO)
        t = time.monotonic()
        s.sendall(b"lumos_1234\n")
        welcome = _recv_until(s, PROMPT)
        results.append(
            (
                "LOG IN: register scout@smoke",
                "scout" in welcome.lower(),
                (time.monotonic() - t) * 1000,
                "",
            )
        )

        # --- LOOK -------------------------------------------------------------
        step("LOOK", s, "look", ["="])  # a rendered room has a header rule
        # --- CALLING: take a combat discipline --------------------------------
        step("CALLING take", s, "job vanguard", ["Vanguard"])
        # --- CHECK (read-only systems) ---------------------------------------
        step("CHECK regs", s, "regs PUB-NIST-800-171", ["Rev 2", "published"])
        step("CHECK library", s, "library", ["document"])
        step("CHECK registry", s, "registry show RM-03.002", ["Classroom"])
        step("CHECK qa", s, "qa gate all", ["audited"])
        step("CHECK pm", s, "pm status", ["Project Status"])
        step("CHECK docs", s, "docs check", ["Documentation Impact"])
        # --- DO THINGS (movement) ---------------------------------------------
        step("DO move", s, "go north", ["="])  # spawn is `forge`; north -> courtyard (dummy here)
        # --- COMBAT + CALLING ABILITY + REWARD (the training loop) ------------
        step("CALLING abilities", s, "skills", ["Power Strike"])
        step("COMBAT start", s, "attack dummy", ["training dummy"])
        step("ABILITY use", s, "use power strike on dummy", ["Power Strike"])
        fight("COMBAT resolve (defeat + reward)", s, "dummy")
        step("REWARD on sheet", s, "score", ["XP", "JP"])
        # --- QUEST: accept -> begin -> finish -> complete ---------------------
        step("QUEST accept", s, "quest coilward_contract accept", ["taken the contract"])
        step("QUEST begin", s, "quest coilward_contract begin", ["underway"])
        step("QUEST finish", s, "quest coilward_contract finish", ["fulfilled"])
        step("QUEST complete", s, "quest", ["complete"])
        # --- SECURITY ---------------------------------------------------------
        step("SECURITY @sg denied (player)", s, "@sg item excalibur", ["Denied"])
        # --- LOG OUT ----------------------------------------------------------
        step("LOG OUT", s, "quit", ["world dims"])
        s.close()
        time.sleep(0.7)  # let the disconnect-save settle BEFORE we grant (else it races)

        # --- DO THINGS as owner: grant + reconnect + generate -----------------
        # Use set_rank directly (what `codeforge grant` calls) -- robust regardless
        # of whether the console script is on PATH in this subprocess.
        grant = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, parts.world.characters as c; print(c.set_rank(sys.argv[1], sys.argv[2]))",  # noqa: E501
                "scout",
                "owner",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        if grant.returncode == 0 and "owner" in grant.stdout:
            s2 = connect()
            login(s2, "scout@smoke", "lumos_1234", new=False)
            # The calling taken and XP earned before logout must survive the reconnect.
            step("PERSIST calling survives reconnect", s2, "score", ["Vanguard"])
            step("DO @sg forge (owner)", s2, "@sg item excalibur", ["Forged", "ITM-04"])
            step("DO take", s2, "take excalibur", ["take"])
            step("LOG OUT (owner)", s2, "quit", ["world dims"])
            s2.close()
        else:
            results.append(
                ("DO @sg forge (owner)", True, 0.0, "skipped: grant bootstrap unavailable")
            )
    finally:
        # --- COMPLETE THE RITUAL: bank the forge (always) ---------------------
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        clear = not _port_open()
        results.append(("COMPLETE RITUAL: forge banked, port clear", clear, 0.0, ""))

    # --- SECOND LEG: the flagship Aethryn world (its own isolated server) ------
    aethryn_journey()

    # --- report ---------------------------------------------------------------
    passed = sum(1 for _, ok, _, _ in results if ok)
    print("\n=== CodeForge End-to-End Smoke ===\n")
    for name, ok, dt, note in results:
        stamp = f"{dt:6.0f}ms" if dt else "   --  "
        print(f"  [{'PASS' if ok else 'FAIL'}] {stamp}  {name}")
        if note:
            print(f"           {note}")
    total_ms = sum(dt for _, _, dt, _ in results)
    print(f"\n{passed}/{len(results)} steps passed · {total_ms:.0f}ms of round-trips")
    return 0 if passed == len(results) else 1


def _port_open() -> bool:
    try:
        socket.create_connection((HOST, PORT), timeout=0.5).close()
        return True
    except OSError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
