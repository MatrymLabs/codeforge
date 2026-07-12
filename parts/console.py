"""CARD: console -- the FailsafeRunner: run allowlisted commands safely.

The Workshop can run diagnostics, but the in-MUD terminal is NEVER a raw shell.
Every command goes through this relay: only allowlisted commands run, as argument
LISTS (no shell, no interpolation), in the repo root, under a timeout and an
output cap, and each run is logged. An unknown command is refused and never runs.

This is the FailsafeRunner from docs/proving_ground/SAFETY.md. The v1 allowlist is
entirely READ-ONLY; anything that mutates will need an approval gate (a later
phase). It runs synchronously (it blocks the tick for the command's duration) --
fine for the fast checks below; async execution is a later phase.
"""

from __future__ import annotations

import subprocess  # nosec B404 -- used only for the fixed, shell-free allowlist below
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TIMEOUT = 60.0  # seconds; a hung command is killed
OUTPUT_CAP = 4000  # chars; overflow is truncated (full logs land in reports/ -- Phase 7)

# name -> argv. READ-ONLY only. No shell, no user-supplied arguments ever.
# sys.executable, not "python3": the absolute path to THIS interpreter, so the console
# runs the same Python everywhere (and never whatever PATH happens to resolve).
ALLOWLIST: dict[str, list[str]] = {
    "version": [sys.executable, "--version"],
    "lint": ["ruff", "check", "."],
    "format": ["ruff", "format", "--check", "."],
    "types": ["mypy", "parts", "forge.py"],
    "compile": [sys.executable, "-m", "compileall", "-q", "parts", "forge.py"],
    "tests": ["pytest", "-q", "-m", "not property"],
    "status": ["git", "status", "--short"],
    "diff": ["git", "diff", "--stat"],
    "security": ["bandit", "-c", "pyproject.toml", "-r", "parts", "forge.py", "-q"],
    "audit": ["pip-audit", "--skip-editable"],
}

# The fast, always-safe subset the `diagnostics` command runs as a bundle.
QUICK = ("version", "lint", "status")

_LOG: list[tuple[str, int, float]] = []  # (name, exit_code, duration) - recent runs


@dataclass(frozen=True)
class RunResult:
    name: str
    argv: list[str]
    exit_code: int
    output: str
    duration: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class CommandRefused(ValueError):
    """The requested command is not on the allowlist -- it never ran."""


def run(
    name: str,
    allowlist: dict[str, list[str]] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    cap: int = OUTPUT_CAP,
) -> RunResult:
    """Run one allowlisted command safely. Refuses anything not on the list."""
    table = ALLOWLIST if allowlist is None else allowlist
    argv = table.get(name)
    if argv is None:
        raise CommandRefused(f"'{name}' is not an allowlisted command. Try: console")
    started = time.monotonic()
    try:
        # Safe by construction: argv is a fixed allowlist entry (never user input),
        # run as a list with shell=False in the repo root. B607 (partial path) is
        # accepted -- these are dev tools resolved from PATH by design.
        proc = subprocess.run(  # nosec B603
            argv,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        exit_code, timed_out = proc.returncode, False
    except subprocess.TimeoutExpired:
        output, exit_code, timed_out = "", 124, True
    except FileNotFoundError:
        output, exit_code, timed_out = f"command not found: {argv[0]}", 127, False
    duration = time.monotonic() - started
    if len(output) > cap:
        output = output[:cap] + f"\n… (truncated at {cap} chars)"
    _LOG.append((name, exit_code, duration))
    return RunResult(name, list(argv), exit_code, output.strip(), duration, timed_out)


def available() -> list[str]:
    """The names of the allowlisted commands."""
    return list(ALLOWLIST)


def console_menu() -> str:
    """List what the diagnostic console can run (read-only, allowlisted)."""
    lines = [
        "== Diagnostic Console (read-only, allowlisted) ==",
        "",
        "Run one:  run <name>      Quick bundle:  diagnostics",
        "",
        "Available:",
    ]
    lines += [f"  {name:<10}{' '.join(ALLOWLIST[name])}" for name in available()]
    return "\n".join(lines)


def _summary(result: RunResult) -> str:
    if result.timed_out:
        mark = "⏱ timed out"
    elif result.ok:
        mark = "✓"
    else:
        mark = f"✗ exit {result.exit_code}"
    head = f"[{result.name}] {mark}  ({result.duration:.1f}s)"
    return head if not result.output else f"{head}\n{result.output}"


def run_view(name: str) -> str:
    """Run one allowlisted command and render a summary (the `run` verb)."""
    try:
        return _summary(run(name.strip()))
    except CommandRefused as exc:
        return str(exc)


def diagnostics_view() -> str:
    """Run the quick read-only bundle and summarize each (the `diagnostics` verb)."""
    lines = ["Running quick diagnostics (read-only)…", ""]
    lines += [_summary(run(name)) for name in QUICK]
    return "\n".join(lines)
