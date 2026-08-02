"""CARD: tool_runner -- run an ALLOWLISTED build/test command inside an approved source, under a
working-directory boundary, a timeout, an output cap, and secret redaction; record the result as
persistent evidence the Project Hub can surface.

Stage 5 of the Seed Platform directive: controlled tool execution. The Seed is a control plane, so
every run is fenced:

  * Approved command profile -- only a NAMED entry in an allowlist runs, as a fixed shell-free argv
    list (never user-interpolated). An unknown profile is refused; it never executes.
  * Working-directory boundary -- the command runs with cwd = the connected source's resolved root.
  * Timeout + output cap -- a hung or noisy command is bounded, not unbounded.
  * Secret redaction -- captured output is scrubbed of key blocks and `token=`/`password=` values.
  * Evidence -- each run is a `ToolRunResult` (profile, argv, exit, duration, when); a `RunLog`
    persists them per Seed (survives restart) and labels them for the Hub's `builds`/`tests` facets.

HONEST SCOPE / SECURITY: running a build/test executes code from the approved source (its conftest,
its build). The controls above fence it; stronger isolation (containers, namespaces) is future
hardening the directive names as "sandboxing where practical". Tests here only ever run fixed,
harmless argv (e.g. `python --version`). Reuses the FailsafeRunner pattern, binding cwd to the
source. No `kernel/world/` coupling. Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404 -- fixed allowlisted argv, shell=False; the whole point is controlled exec
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from parts.seedlab.source_connector import LocalSource

DEFAULT_TIMEOUT = 120.0
OUTPUT_CAP = 20_000

# The default approved command profile: build/test tools as fixed, shell-free argv. Only a NAMED
# entry here can run; a caller may pass its own allowlist. NEVER built from user input.
DEFAULT_PROFILE: dict[str, list[str]] = {
    "pytest": ["python", "-m", "pytest", "-q"],
    "python-build": ["python", "-m", "build"],
    "ruff": ["ruff", "check", "."],
    "python-version": ["python", "--version"],
}

# Patterns scrubbed from captured output before it is stored or shown.
_REDACTIONS = (
    re.compile(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", re.S),
    re.compile(r"(?i)\b(token|secret|password|passwd|api[_-]?key)\b\s*[=:]\s*\S+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def redact(text: str) -> str:
    """Scrub key blocks and secret-shaped assignments from captured output."""
    for pattern in _REDACTIONS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


class CommandRefused(ValueError):
    """The requested profile is not on the approved allowlist -- it never ran."""


class RunLogError(Exception):
    """A persisted run record is corrupt. Fails loud."""


@dataclass(frozen=True)
class ToolRunResult:
    """The evidence of one controlled run: what ran, where, its exit, timing, and output."""

    seed_id: str
    kind: str  # "build" | "test" | "run" -- the caller's declared intent, for the Hub facet
    profile: str
    argv: list[str]
    exit_code: int
    output: str  # captured, redacted, capped
    duration: float
    timed_out: bool
    cwd: str
    when: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ToolRunResult:
        try:
            return cls(
                seed_id=data["seed_id"],
                kind=data["kind"],
                profile=data["profile"],
                argv=list(data["argv"]),
                exit_code=int(data["exit_code"]),
                output=data.get("output", ""),
                duration=float(data.get("duration", 0.0)),
                timed_out=bool(data.get("timed_out", False)),
                cwd=data.get("cwd", ""),
                when=data.get("when", ""),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RunLogError(f"malformed run record: {exc}") from exc


def run_tool(
    source: LocalSource,
    profile: str,
    *,
    seed_id: str,
    kind: str = "run",
    allowlist: dict[str, list[str]] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    cap: int = OUTPUT_CAP,
    clock: Callable[[], str] = _utcnow,
) -> ToolRunResult:
    """Run one approved command inside `source`, bounded and captured. Refuses an unlisted profile;
    returns a ToolRunResult (never raises on a failing command -- a non-zero exit IS the result)."""
    table = allowlist if allowlist is not None else DEFAULT_PROFILE
    argv = table.get(profile)
    if argv is None:
        raise CommandRefused(f"{profile!r} is not an approved command profile")
    root = Path(source.root)  # the connector already resolved + bounded this
    started = time.monotonic()
    try:
        proc = subprocess.run(  # nosec B603 -- fixed allowlisted argv, shell=False, cwd-bounded
            argv, cwd=root, capture_output=True, text=True, timeout=timeout, check=False
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        exit_code, timed_out = proc.returncode, False
    except subprocess.TimeoutExpired:
        output, exit_code, timed_out = "", 124, True
    except FileNotFoundError:
        output, exit_code, timed_out = f"command not found: {argv[0]}", 127, False
    duration = time.monotonic() - started
    output = redact(output)
    if len(output) > cap:
        output = output[:cap] + f"\n... (truncated at {cap} chars)"
    return ToolRunResult(
        seed_id=seed_id,
        kind=kind,
        profile=profile,
        argv=list(argv),
        exit_code=exit_code,
        output=output.strip(),
        duration=duration,
        timed_out=timed_out,
        cwd=str(root),
        when=clock(),
    )


def render_run(result: ToolRunResult) -> str:
    """A human view of a run (the output visible in the Seed)."""
    verdict = (
        "OK"
        if result.ok
        else (
            f"TIMED OUT ({int(result.duration)}s)"
            if result.timed_out
            else f"FAILED (exit {result.exit_code})"
        )
    )
    return "\n".join(
        [
            f"== {result.kind}:{result.profile} -- {verdict} ==",
            f"argv: {' '.join(result.argv)}",
            f"cwd:  {result.cwd}",
            f"when: {result.when}  ({result.duration:.2f}s)",
            "--- output ---",
            result.output or "(no output)",
        ]
    )


@dataclass
class InMemoryRunLog:
    """A volatile run log for tests. Does not survive restart, by design."""

    _runs: list[ToolRunResult] = field(default_factory=list)

    def append(self, result: ToolRunResult) -> None:
        self._runs.append(result)

    def for_seed(self, seed_id: str) -> list[ToolRunResult]:
        return [r for r in self._runs if r.seed_id == seed_id]


@dataclass
class FileRunLog:
    """A durable, append-only run log: one JSONL file per Seed under `root`. Survives restart."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, seed_id: str) -> Path:
        return self.root / f"{seed_id}.jsonl"

    def append(self, result: ToolRunResult) -> None:
        with self._path(result.seed_id).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result.to_dict()) + "\n")

    def for_seed(self, seed_id: str) -> list[ToolRunResult]:
        path = self._path(seed_id)
        if not path.is_file():
            return []
        out: list[ToolRunResult] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(ToolRunResult.from_dict(json.loads(line)))
                except json.JSONDecodeError as exc:
                    raise RunLogError(f"corrupt run log line in {path}: {exc}") from exc
        return out


def run_and_record(
    log: InMemoryRunLog | FileRunLog,
    source: LocalSource,
    profile: str,
    *,
    seed_id: str,
    kind: str = "run",
    **kw: object,
) -> ToolRunResult:
    """Run a command and persist its evidence in one call. Returns the result."""
    result = run_tool(source, profile, seed_id=seed_id, kind=kind, **kw)  # type: ignore[arg-type]
    log.append(result)
    return result


def run_labels(log: InMemoryRunLog | FileRunLog, seed_id: str, kind: str) -> tuple[str, ...]:
    """The `builds`/`tests` facet the Hub renders: one label per persisted run of `kind`."""
    return tuple(
        f"{r.profile} exit={r.exit_code} ({r.duration:.1f}s) @ {r.when}"
        for r in log.for_seed(seed_id)
        if r.kind == kind
    )
